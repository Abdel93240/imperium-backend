"""PostgreSQL : hydratation Pulse — appuis rapides et décompte de l'eau du stock (doc 40 §12)."""
from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("pulse hydration DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_pulse_hydration as hydration_routes  # noqa: E402
from app.api.v1.routes import imperium_pulse_stock as routes  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402

BASE = "/api/imperium/pulse/food-stock"
LOGS = "/api/imperium/pulse/hydration-logs"


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    with Session(engine) as session:
        yield session
        session.rollback()


def _user(db) -> User:
    user_id = uuid4()
    db.execute(
        text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) VALUES (:id, :email, FALSE, now(), now())"),
        {"id": str(user_id), "email": f"hydra-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/imperium/pulse")
    app.include_router(hydration_routes.router, prefix="/api/imperium/pulse")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def _stock(client, name, quantity, unit="l", expiry=None) -> dict:
    payload = {"name": name, "quantity": quantity, "unit": unit}
    if expiry:
        payload.update(expiry_type="DDM", expiry_date=expiry)
    return client.post(BASE, headers=_key(), json=payload).json()


def _stock_by_id(client) -> dict:
    return {i["id"]: i for i in client.get(BASE, params={"include_inactive": True}).json()["items"]}


def test_quick_log_decrements_the_water_stock(db) -> None:
    user = _user(db)
    client = _client(db, user)
    water = _stock(client, "Eau minérale", 6, "l")
    juice = _stock(client, "Jus d'orange", 1, "l")
    logged = client.post(LOGS, headers=_key(), json={"amount_ml": 500})
    assert logged.status_code == 201, logged.text
    body = logged.json()
    assert (body["log"]["amount_ml"], body["log"]["source"], body["log"]["stock_decrement_applied"]) == (500, "quick", True)
    assert [(i["id"], i["quantity"], i["version"]) for i in body["stock_items"]] == [(water["id"], "5.500", 2)]
    assert body["warnings"] == []
    assert _stock_by_id(client)[juice["id"]]["quantity"] == "1.000"
    events = {e.event_type: e.payload for e in db.scalars(select(Event).where(Event.user_id == user.id, Event.event_type.like("pulse.%")))}
    assert events["pulse.hydration.logged"]["amount_ml"] == 500
    assert events["pulse.food_stock.updated"]["source"] == "hydration"


def test_water_is_taken_from_the_earliest_dated_line_then_the_next(db) -> None:
    client = _client(db, _user(db))
    late = _stock(client, "Eau", 1, "l", expiry="2027-06-01")
    early = _stock(client, "Bouteille d'eau", 50, "cl", expiry="2027-01-01")
    body = client.post(LOGS, headers=_key(), json={"amount_ml": 1000}).json()
    stock = _stock_by_id(client)
    assert (stock[early["id"]]["status"], stock[early["id"]]["quantity"]) == ("consumed", "50.000")
    assert (stock[late["id"]]["status"], stock[late["id"]]["quantity"]) == ("active", "0.500")
    assert [i["id"] for i in body["stock_items"]] == [early["id"], late["id"]]


def test_not_enough_water_still_logs_and_warns(db) -> None:
    client = _client(db, _user(db))
    water = _stock(client, "Eau", 250, "ml")
    body = client.post(LOGS, headers=_key(), json={"amount_ml": 1000}).json()
    assert body["log"]["amount_ml"] == 1000
    assert _stock_by_id(client)[water["id"]]["status"] == "consumed"
    assert body["warnings"] == ["Stock d'eau épuisé : 750 ml non décomptés."]


def test_no_water_stock_or_bottles_only(db) -> None:
    client = _client(db, _user(db))
    assert client.post(LOGS, headers=_key(), json={"amount_ml": 250}).json()["warnings"] == [
        "Pas d'eau en stock : rien n'est décompté."]
    bottles = _stock(client, "Eau gazeuse", 6, "piece")
    body = client.post(LOGS, headers=_key(), json={"amount_ml": 250}).json()
    assert body["log"]["stock_decrement_applied"] is False
    assert body["warnings"] == ["Eau comptée en pièces : décompte le stock à la main."]
    assert _stock_by_id(client)[bottles["id"]]["quantity"] == "6.000"


def test_decrement_can_be_turned_off(db) -> None:
    client = _client(db, _user(db))
    water = _stock(client, "Eau", 1, "l")
    body = client.post(LOGS, headers=_key(), json={"amount_ml": 500, "decrement_stock": False, "source": "manual"}).json()
    assert body["stock_items"] == [] and body["warnings"] == []
    assert _stock_by_id(client)[water["id"]]["quantity"] == "1.000"


def test_same_key_dedupes_distinct_keys_add_up(db) -> None:
    client = _client(db, _user(db))
    water = _stock(client, "Eau", 2, "l")
    assert client.post(LOGS, json={"amount_ml": 250}).status_code == 400
    first = client.post(LOGS, headers={"Idempotency-Key": "h1"}, json={"amount_ml": 250, "logged_at": "2026-10-17T08:00:00+00:00"})
    again = client.post(LOGS, headers={"Idempotency-Key": "h1"}, json={"amount_ml": 250, "logged_at": "2026-10-17T08:00:00+00:00"})
    other = client.post(LOGS, headers={"Idempotency-Key": "h1"}, json={"amount_ml": 500})
    assert first.status_code == 201 and again.status_code == 200 and again.json() == first.json()
    assert other.status_code == 409
    client.post(LOGS, headers=_key(), json={"amount_ml": 250, "logged_at": "2026-10-17T09:00:00+00:00"})
    assert _stock_by_id(client)[water["id"]]["quantity"] == "1.500"
    day = client.get(LOGS, params={"day": "2026-10-17"}).json()
    assert (day["total_ml"], len(day["logs"])) == (500, 2)


@pytest.mark.parametrize("payload", [{"amount_ml": 0}, {"amount_ml": 5001}, {"amount_ml": 250, "source": "robot"},
                                     {"amount_ml": 1.5}, {}])
def test_invalid_logs_are_rejected(db, payload) -> None:
    assert _client(db, _user(db)).post(LOGS, headers=_key(), json=payload).status_code == 422


def test_day_view_uses_the_paris_day_and_has_no_target_yet(db) -> None:
    client = _client(db, _user(db))
    for logged_at, amount in [("2026-10-16T22:30:00+00:00", 250), ("2026-10-17T12:00:00+00:00", 1000),
                              ("2026-10-17T22:30:00+00:00", 500)]:
        client.post(LOGS, headers=_key(), json={"amount_ml": amount, "logged_at": logged_at})
    day = client.get(LOGS, params={"day": "2026-10-17"}).json()
    assert day["total_ml"] == 1250
    assert [log["amount_ml"] for log in day["logs"]] == [250, 1000]
    assert day["target"] is None
    assert day["target_message"] == "Objectif personnalisé pas encore calculé."


def test_other_drink_is_logged_but_never_takes_water_from_the_stock(db) -> None:
    client = _client(db, _user(db))
    water = _stock(client, "Eau", 1, "l")
    body = client.post(LOGS, headers=_key(), json={"amount_ml": 250, "drink": "  Thé à la menthe "}).json()
    assert (body["log"]["drink"], body["log"]["stock_decrement_applied"], body["stock_items"]) == ("Thé à la menthe", False, [])
    assert _stock_by_id(client)[water["id"]]["quantity"] == "1.000"
    plain = client.post(LOGS, headers=_key(), json={"amount_ml": 250}).json()
    assert plain["log"]["drink"] is None and plain["log"]["stock_decrement_applied"] is True
