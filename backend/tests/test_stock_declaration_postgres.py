"""PostgreSQL : ajout au stock par le chatbot — proposition puis validation (doc 40 §11.1, doc 72 §5)."""
from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("stock declaration DB tests")

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
DECL = f"{BASE}/declarations"


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
        {"id": str(user_id), "email": f"decl-{user_id}@example.test"},
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


def test_preview_writes_nothing_and_points_at_existing_stock(db) -> None:
    user = _user(db)
    client = _client(db, user)
    rice = client.post(BASE, headers=_key(), json={"name": "Riz basmati", "quantity": 1, "unit": "kg"}).json()
    preview = client.post(f"{DECL}/preview", json={"text": "J'ai acheté 2kg de riz basmati et du pain"})
    assert preview.status_code == 200
    lines = preview.json()["lines"]
    assert [(line["name"], line["quantity"], line["unit"], line["quantity_assumed"]) for line in lines] == [
        ("riz basmati", "2", "kg", False), ("pain", "1", "piece", True),
    ]
    assert lines[0]["in_stock"] == {"stock_item_id": rice["id"], "name": "Riz basmati", "quantity": "1.000", "unit": "kg"}
    assert lines[1]["in_stock"] is None
    assert len(client.get(BASE).json()["items"]) == 1


def test_preview_rejects_empty_or_huge_text(db) -> None:
    client = _client(db, _user(db))
    assert client.post(f"{DECL}/preview", json={"text": "  "}).status_code == 422
    assert client.post(f"{DECL}/preview", json={"text": "riz " * 600}).status_code == 422


def test_validation_adds_kept_lines_with_chatbot_source(db) -> None:
    user = _user(db)
    client = _client(db, user)
    created = client.post(DECL, headers=_key(), json={"lines": [
        {"name": "Riz", "quantity": "2", "unit": "kg"},
        {"name": "Yaourts", "quantity": 4, "expiry_type": "DLC", "expiry_date": "2026-10-20"},
    ]})
    assert created.status_code == 201
    body = created.json()
    items = body["stock_items"]
    assert [(i["name"], i["quantity"], i["unit"], i["source"], i["version"]) for i in items] == [
        ("Riz", "2.000", "kg", "chatbot", 1), ("Yaourts", "4.000", "piece", "chatbot", 1),
    ]
    assert [i["source_ref"] for i in items] == [f"chat:{body['declaration_id']}:0", f"chat:{body['declaration_id']}:1"]
    assert {i["name"] for i in client.get(BASE).json()["items"]} == {"Riz", "Yaourts"}
    events = list(db.scalars(select(Event).where(Event.user_id == user.id, Event.event_type == "pulse.food_stock.updated")))
    assert [(e.payload["source"], e.payload["items_added"]) for e in events] == [("chatbot", 2)]


def test_purchase_never_merges_into_an_existing_line(db) -> None:
    user = _user(db)
    client = _client(db, user)
    client.post(BASE, headers=_key(), json={"name": "Lait", "quantity": 1, "unit": "l"})
    client.post(DECL, headers=_key(), json={"lines": [{"name": "Lait", "quantity": 2, "unit": "l"}]})
    assert sorted(i["quantity"] for i in client.get(BASE).json()["items"]) == ["1.000", "2.000"]


def test_validation_is_idempotent(db) -> None:
    user = _user(db)
    client = _client(db, user)
    assert client.post(DECL, json={"lines": [{"name": "Riz", "quantity": 1}]}).status_code == 400
    first = client.post(DECL, headers={"Idempotency-Key": "d1"}, json={"lines": [{"name": "Riz", "quantity": 1}]})
    again = client.post(DECL, headers={"Idempotency-Key": "d1"}, json={"lines": [{"name": "Riz", "quantity": 1}]})
    other = client.post(DECL, headers={"Idempotency-Key": "d1"}, json={"lines": [{"name": "Pâtes", "quantity": 1}]})
    assert first.status_code == 201 and again.status_code == 200
    assert again.json() == first.json()
    assert other.status_code == 409
    assert len(client.get(BASE).json()["items"]) == 1


@pytest.mark.parametrize("payload", [{"lines": []}, {"lines": [{"name": "Riz", "quantity": 0}]},
                                     {"lines": [{"name": "Riz", "quantity": 1, "unit": "sac"}]},
                                     {"lines": [{"name": "Riz", "quantity": 1}] * 51}])
def test_invalid_validations_are_rejected(db, payload) -> None:
    assert _client(db, _user(db)).post(DECL, headers=_key(), json=payload).status_code == 422
