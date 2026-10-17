"""PostgreSQL : matériel possédé Pulse (doc 40 §13-EQUIP)."""
from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("pulse equipment DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_pulse_equipment as routes  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402

BASE = "/api/imperium/pulse/equipment"


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
        {"id": str(user_id), "email": f"equip-{user_id}@example.test"},
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


def test_add_list_and_remove(db) -> None:
    user = _user(db)
    client = _client(db, user)
    board = client.post(BASE, json={"name": "  Planche à pompes avec poignées ", "notes": "Salon"})
    assert board.status_code == 201
    assert (board.json()["name"], board.json()["notes"]) == ("Planche à pompes avec poignées", "Salon")
    client.post(BASE, json={"name": "Haltère 20 kg"})
    assert [i["name"] for i in client.get(BASE).json()["items"]] == ["Haltère 20 kg", "Planche à pompes avec poignées"]
    removed = client.delete(f"{BASE}/{board.json()['id']}")
    assert removed.status_code == 200 and removed.json()["status"] == "removed"
    assert [i["name"] for i in client.get(BASE).json()["items"]] == ["Haltère 20 kg"]
    assert client.delete(f"{BASE}/{board.json()['id']}").status_code == 200  # déjà retiré : même réponse
    events = [e.payload["action"] for e in db.scalars(
        select(Event).where(Event.user_id == user.id, Event.event_type == "pulse.equipment.updated").order_by(Event.created_at))]
    assert events == ["added", "added", "removed"]


def test_same_name_is_not_added_twice(db) -> None:
    client = _client(db, _user(db))
    first = client.post(BASE, json={"name": "Élastiques"})
    again = client.post(BASE, json={"name": "elastiques"})
    assert first.status_code == 201 and again.status_code == 200 and again.json()["id"] == first.json()["id"]
    client.delete(f"{BASE}/{first.json()['id']}")
    back = client.post(BASE, json={"name": "Élastiques"})
    assert back.status_code == 201 and back.json()["id"] != first.json()["id"]


@pytest.mark.parametrize("payload", [{"name": " "}, {"name": "x" * 121}, {"name": "Barre", "extra": 1}, {}])
def test_invalid_equipment_is_rejected(db, payload) -> None:
    assert _client(db, _user(db)).post(BASE, json=payload).status_code == 422


def test_other_users_equipment_is_not_found(db) -> None:
    owner, other = _user(db), _user(db)
    item = _client(db, owner).post(BASE, json={"name": "Kettlebell"}).json()
    assert _client(db, other).delete(f"{BASE}/{item['id']}").status_code == 404
    assert _client(db, other).get(BASE).json()["items"] == []
