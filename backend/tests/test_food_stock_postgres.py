"""PostgreSQL : stock alimentaire Pulse — ajout et modification manuels (doc 40 §8, §11)."""
from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("food stock DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_pulse_stock as routes  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402

BASE = "/api/imperium/pulse/food-stock"


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
        {"id": str(user_id), "email": f"stock-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/imperium/pulse")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def test_manual_add_then_list(db) -> None:
    user = _user(db)
    client = _client(db, user)
    created = client.post(BASE, headers=_key(), json={"name": "  Riz basmati ", "quantity": "2", "unit": "kg",
                                                      "expiry_type": "DDM", "expiry_date": "2027-06-01"})
    assert created.status_code == 201
    body = created.json()
    assert (body["name"], body["quantity"], body["unit"], body["source"], body["version"]) == ("Riz basmati", "2.000", "kg", "manual", 1)
    assert [item["name"] for item in client.get(BASE).json()["items"]] == ["Riz basmati"]
    events = list(db.scalars(select(Event).where(Event.user_id == user.id, Event.event_type == "pulse.food_stock.updated")))
    assert [event.payload["action"] for event in events] == ["created"]


def test_add_requires_a_key_and_replays_are_idempotent(db) -> None:
    user = _user(db)
    client = _client(db, user)
    assert client.post(BASE, json={"name": "Lait", "quantity": 1}).status_code == 400
    first = client.post(BASE, headers={"Idempotency-Key": "a1"}, json={"name": "Lait", "quantity": 1})
    again = client.post(BASE, headers={"Idempotency-Key": "a1"}, json={"name": "Lait", "quantity": 1})
    other = client.post(BASE, headers={"Idempotency-Key": "a1"}, json={"name": "Beurre", "quantity": 1})
    assert first.status_code == 201 and again.status_code == 200 and again.json()["id"] == first.json()["id"]
    assert other.status_code == 409
    assert len(client.get(BASE).json()["items"]) == 1


@pytest.mark.parametrize("payload", [{"name": "Riz", "quantity": 0}, {"name": "  ", "quantity": 1},
                                     {"name": "Riz", "quantity": 1, "unit": "sac"}, {"name": "Riz", "quantity": -1}])
def test_invalid_adds_are_rejected(db, payload) -> None:
    assert _client(db, _user(db)).post(BASE, headers=_key(), json=payload).status_code == 422


def test_update_with_the_read_version_bumps_it(db) -> None:
    user = _user(db)
    client = _client(db, user)
    item = client.post(BASE, headers=_key(), json={"name": "Oeufs", "quantity": 12}).json()
    patched = client.patch(f"{BASE}/{item['id']}", headers=_key(),
                           json={"version": 1, "quantity": "6", "expiry_type": "DLC", "expiry_date": "2026-10-25"})
    assert patched.status_code == 200
    assert (patched.json()["quantity"], patched.json()["expiry_date"], patched.json()["version"]) == ("6.000", "2026-10-25", 2)


def test_stale_version_is_a_conflict_with_the_current_row(db) -> None:
    user = _user(db)
    client = _client(db, user)
    item = client.post(BASE, headers=_key(), json={"name": "Yaourt", "quantity": 4}).json()
    client.patch(f"{BASE}/{item['id']}", headers=_key(), json={"version": 1, "quantity": 3})
    stale = client.patch(f"{BASE}/{item['id']}", headers=_key(), json={"version": 1, "quantity": 2})
    assert stale.status_code == 409 and stale.json()["code"] == "STOCK_VERSION_CONFLICT"
    assert stale.json()["current"]["quantity"] == "3.000" and stale.json()["current"]["version"] == 2


def test_patch_replay_returns_the_stored_result_instead_of_a_conflict(db) -> None:
    user = _user(db)
    client = _client(db, user)
    item = client.post(BASE, headers=_key(), json={"name": "Pommes", "quantity": 6}).json()
    first = client.patch(f"{BASE}/{item['id']}", headers={"Idempotency-Key": "p1"}, json={"version": 1, "quantity": 5})
    again = client.patch(f"{BASE}/{item['id']}", headers={"Idempotency-Key": "p1"}, json={"version": 1, "quantity": 5})
    assert first.status_code == again.status_code == 200 and again.json()["version"] == 2


def test_consumed_and_removed_lines_leave_the_active_list(db) -> None:
    user = _user(db)
    client = _client(db, user)
    milk = client.post(BASE, headers=_key(), json={"name": "Lait", "quantity": 1}).json()
    typo = client.post(BASE, headers=_key(), json={"name": "Lati", "quantity": 1}).json()
    client.patch(f"{BASE}/{milk['id']}", headers=_key(), json={"version": 1, "status": "consumed"})
    client.patch(f"{BASE}/{typo['id']}", headers=_key(), json={"version": 1, "status": "removed"})
    assert client.get(BASE).json()["items"] == []
    everything = {i["name"]: i["status"] for i in client.get(BASE, params={"include_inactive": True}).json()["items"]}
    assert everything == {"Lait": "consumed", "Lati": "removed"}
    actions = {e.payload["action"] for e in db.scalars(select(Event).where(Event.user_id == user.id))}
    assert {"created", "consumed", "removed"} <= actions


@pytest.mark.parametrize("payload", [{"version": 1}, {"version": 1, "quantity": 0}, {"version": 1, "name": " "},
                                     {"version": 1, "unit": None}, {"version": 0, "quantity": 1}])
def test_invalid_updates_are_rejected(db, payload) -> None:
    user = _user(db)
    client = _client(db, user)
    item = client.post(BASE, headers=_key(), json={"name": "Riz", "quantity": 1}).json()
    assert client.patch(f"{BASE}/{item['id']}", headers=_key(), json=payload).status_code == 422


def test_other_users_rows_are_not_found(db) -> None:
    owner, other = _user(db), _user(db)
    item = _client(db, owner).post(BASE, headers=_key(), json={"name": "Riz", "quantity": 1}).json()
    response = _client(db, other).patch(f"{BASE}/{item['id']}", headers=_key(), json={"version": 1, "quantity": 2})
    assert response.status_code == 404
