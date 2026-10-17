"""PostgreSQL : repas Pulse — brouillon, validation, décompte du stock (doc 40 §10.1–§10.3)."""
from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("pulse meals DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_pulse_meals as meal_routes  # noqa: E402
from app.api.v1.routes import imperium_pulse_stock as routes  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402

BASE = "/api/imperium/pulse/food-stock"
MEALS = "/api/imperium/pulse/meals"


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
        {"id": str(user_id), "email": f"meal-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/imperium/pulse")
    app.include_router(meal_routes.router, prefix="/api/imperium/pulse")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def _stock(client, name, quantity, unit="piece") -> dict:
    return client.post(BASE, headers=_key(), json={"name": name, "quantity": quantity, "unit": unit}).json()


def _draft(client, description, **extra) -> dict:
    response = client.post(f"{MEALS}/drafts", headers=_key(), json={"description": description, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def _stock_by_id(client) -> dict:
    return {i["id"]: i for i in client.get(BASE, params={"include_inactive": True}).json()["items"]}


def test_draft_proposes_decrements_without_touching_the_stock(db) -> None:
    client = _client(db, _user(db))
    rice = _stock(client, "Riz basmati", 1, "kg")
    eggs = _stock(client, "Oeufs", 6)
    draft = _draft(client, "J'ai mangé 200 g de riz basmati avec 2 œufs")
    assert draft["status"] == "draft" and draft["label"] == "J'ai mangé 200 g de riz basmati avec 2 œufs"
    lines = [(line["name"], line["stock_item_id"], line["used_in_stock_unit"], line["confidence"], line["checked"]) for line in draft["stock_lines"]]
    assert lines == [("riz basmati", rice["id"], "0.200", "high", True), ("œufs", eggs["id"], "2", "high", True)]
    assert draft["calories"] is None
    assert "Macros non estimées automatiquement : saisis-les pour le suivi." in draft["warnings"]
    assert {i["quantity"] for i in _stock_by_id(client).values()} == {"1.000", "6.000"}


def test_uncertain_lines_are_unchecked_and_missing_products_reported(db) -> None:
    client = _client(db, _user(db))
    _stock(client, "Riz basmati", 1, "kg")
    _stock(client, "Lait", 1, "l")
    draft = _draft(client, "100 g de riz, du poulet et 1 lait", calories=650)
    by_name = {line["name"]: line for line in draft["stock_lines"]}
    assert (by_name["riz"]["confidence"], by_name["riz"]["checked"]) == ("low", False)
    assert by_name["poulet"]["stock_item_id"] is None and by_name["poulet"]["checked"] is False
    assert (by_name["lait"]["used_in_stock_unit"], by_name["lait"]["checked"]) == (None, False)  # pièce ≠ litre
    assert "« poulet » n'est pas dans le stock." in draft["warnings"]
    assert draft["calories"] == "650.0"
    assert not any(w.startswith("Macros") for w in draft["warnings"])


def test_insufficient_stock_is_a_warning_in_the_draft(db) -> None:
    client = _client(db, _user(db))
    _stock(client, "Pâtes", 200, "g")
    line = _draft(client, "250 g de pâtes")["stock_lines"][0]
    assert line["insufficient"] is True
    assert "Stock insuffisant pour « Pâtes » (reste 200.000 g)." in _draft(client, "250 g de pâtes")["warnings"]


def test_confirmation_logs_the_meal_and_decrements_once(db) -> None:
    user = _user(db)
    client = _client(db, user)
    rice = _stock(client, "Riz basmati", 1, "kg")
    eggs = _stock(client, "Oeufs", 6)
    draft = _draft(client, "200 g de riz basmati et 2 oeufs")
    payload = {"label": "Riz aux œufs", "calories": 520, "protein_g": 22, "carbs_g": 80, "fat_g": 12.5,
               "stock_lines": [{"stock_item_id": rice["id"], "quantity": 200, "unit": "g"},
                               {"stock_item_id": eggs["id"], "quantity": 2, "unit": "piece"}]}
    first = client.post(f"{MEALS}/{draft['id']}/confirm", headers={"Idempotency-Key": "c1"}, json=payload)
    assert first.status_code == 200, first.text
    body = first.json()
    assert (body["status"], body["label"], body["calories"], body["fat_g"], body["stock_decrement_applied"]) == (
        "confirmed", "Riz aux œufs", "520.0", "12.5", True)
    stock = _stock_by_id(client)
    assert (stock[rice["id"]]["quantity"], stock[rice["id"]]["version"]) == ("0.800", 2)
    assert (stock[eggs["id"]]["quantity"], stock[eggs["id"]]["status"]) == ("4.000", "active")
    again = client.post(f"{MEALS}/{draft['id']}/confirm", headers={"Idempotency-Key": "c1"}, json=payload)
    assert again.status_code == 200 and again.json() == body
    assert _stock_by_id(client)[rice["id"]]["quantity"] == "0.800"
    assert client.post(f"{MEALS}/{draft['id']}/confirm", headers={"Idempotency-Key": "c2"}, json=payload).status_code == 409
    changed = {**payload, "calories": 600}
    assert client.post(f"{MEALS}/{draft['id']}/confirm", headers={"Idempotency-Key": "c1"}, json=changed).status_code == 409
    types = [e.event_type for e in db.scalars(select(Event).where(Event.user_id == user.id, Event.payload["meal_id"].astext == draft["id"]))]
    assert sorted(types) == ["pulse.food_stock.updated", "pulse.meal.logged"]


def test_finishing_a_line_needs_explicit_confirmation(db) -> None:
    client = _client(db, _user(db))
    pasta = _stock(client, "Pâtes", 200, "g")
    bread = _stock(client, "Pain", 1)
    draft = _draft(client, "250 g de pâtes")
    lines = [{"stock_item_id": bread["id"], "quantity": 1, "unit": "piece", "finish": True},
             {"stock_item_id": pasta["id"], "quantity": 250, "unit": "g"}]
    refused = client.post(f"{MEALS}/{draft['id']}/confirm", headers=_key(), json={"stock_lines": lines})
    assert refused.status_code == 409 and refused.json()["code"] == "STOCK_INSUFFICIENT"
    assert refused.json()["current"]["id"] == pasta["id"]
    assert _stock_by_id(client)[bread["id"]]["status"] == "active"  # rien n'est écrit
    assert client.get(f"{MEALS}/{draft['id']}").json()["status"] == "draft"
    lines[1]["finish"] = True
    done = client.post(f"{MEALS}/{draft['id']}/confirm", headers=_key(), json={"stock_lines": lines})
    assert done.status_code == 200
    stock = _stock_by_id(client)
    assert (stock[pasta["id"]]["status"], stock[pasta["id"]]["quantity"]) == ("consumed", "200.000")
    assert stock[bread["id"]]["status"] == "consumed"


def test_incompatible_units_and_foreign_rows_are_rejected(db) -> None:
    owner, other = _user(db), _user(db)
    client = _client(db, owner)
    milk = _stock(client, "Lait", 1, "l")
    draft = _draft(client, "un verre de lait")
    bad_unit = client.post(f"{MEALS}/{draft['id']}/confirm", headers=_key(),
                           json={"stock_lines": [{"stock_item_id": milk["id"], "quantity": 2, "unit": "piece"}]})
    assert bad_unit.status_code == 422
    foreign = _client(db, other)
    assert foreign.get(f"{MEALS}/{draft['id']}").status_code == 404
    other_draft = _draft(foreign, "pâtes")
    stolen = foreign.post(f"{MEALS}/{other_draft['id']}/confirm", headers=_key(),
                          json={"stock_lines": [{"stock_item_id": milk["id"], "quantity": 0.2, "unit": "l"}]})
    assert stolen.status_code == 404
    assert _stock_by_id(client)[milk["id"]]["quantity"] == "1.000"


def test_meal_without_stock_lines_and_cancel(db) -> None:
    client = _client(db, _user(db))
    kept = _draft(client, "Salade au restaurant")
    confirmed = client.post(f"{MEALS}/{kept['id']}/confirm", headers=_key(), json={"calories": 400})
    assert confirmed.status_code == 200 and confirmed.json()["stock_decrement_applied"] is False
    dropped = _draft(client, "Tartine")
    assert client.post(f"{MEALS}/{dropped['id']}/cancel").json()["status"] == "cancelled"
    assert client.post(f"{MEALS}/{dropped['id']}/confirm", headers=_key(), json={}).status_code == 409
    assert client.post(f"{MEALS}/{kept['id']}/cancel").status_code == 409


def test_draft_idempotency(db) -> None:
    client = _client(db, _user(db))
    assert client.post(f"{MEALS}/drafts", json={"description": "Pâtes"}).status_code == 400
    first = client.post(f"{MEALS}/drafts", headers={"Idempotency-Key": "m1"}, json={"description": "Pâtes"})
    again = client.post(f"{MEALS}/drafts", headers={"Idempotency-Key": "m1"}, json={"description": "Pâtes"})
    other = client.post(f"{MEALS}/drafts", headers={"Idempotency-Key": "m1"}, json={"description": "Riz"})
    assert first.status_code == 201 and again.status_code == 200 and again.json()["id"] == first.json()["id"]
    assert other.status_code == 409
    assert client.post(f"{MEALS}/drafts", headers=_key(), json={"description": "  "}).status_code == 422
    assert client.post(f"{MEALS}/drafts", headers=_key(), json={"description": "x", "calories": -1}).status_code == 422


def test_day_list_uses_the_paris_day_and_sums_macros(db) -> None:
    client = _client(db, _user(db))
    for description, eaten_at, calories in [("Petit-déjeuner", "2026-10-16T22:30:00+00:00", 300),  # 17/10 à Paris
                                            ("Déjeuner", "2026-10-17T11:00:00+00:00", 700),
                                            ("Veille", "2026-10-16T12:00:00+00:00", 900)]:
        draft = _draft(client, description, eaten_at=eaten_at)
        client.post(f"{MEALS}/{draft['id']}/confirm", headers=_key(), json={"calories": calories, "protein_g": 10})
    _draft(client, "Brouillon non validé", eaten_at="2026-10-17T12:00:00+00:00")
    noon = _draft(client, "Sans macros", eaten_at="2026-10-17T18:00:00+00:00")
    client.post(f"{MEALS}/{noon['id']}/confirm", headers=_key(), json={})
    day = client.get(MEALS, params={"day": "2026-10-17"}).json()
    assert [m["label"] for m in day["meals"]] == ["Petit-déjeuner", "Déjeuner", "Sans macros"]
    assert day["totals"] == {"calories": "1000.0", "protein_g": "20.0", "carbs_g": "0.0", "fat_g": "0.0"}
    assert day["meals_without_macros"] == 1
