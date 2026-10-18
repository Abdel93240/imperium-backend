"""PostgreSQL : annulation d'une mission (doc 43 §5 « annulée » : définitive, raison obligatoire)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("mission cancel DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.imperium import ImperiumMission  # noqa: E402

BASE = "/api/imperium/missions"


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
        {"id": str(user_id), "email": f"cancel-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/api/imperium")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _mission(db, user, title, status, **extra) -> ImperiumMission:
    mission = ImperiumMission(user_id=user.id, title=title, status=status,
                              started_at=datetime.now(UTC) - timedelta(hours=1), **extra)
    db.add(mission)
    db.commit()
    return mission


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def test_cancel_the_active_mission_with_a_reason(db) -> None:
    user = _user(db)
    client = _client(db, user)
    carrier = _mission(db, user, "Réviser le code de la route", "active")
    annex = _mission(db, user, "Répondre au mail", "backlog", annex_of_mission_id=carrier.id, estimated_minutes=10)
    key = _key()
    response = client.post(f"{BASE}/{carrier.id}/cancel", headers=key, json={"reason": "  Examen reporté  "})
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["status"], body["mission"]["status"]) == ("cancelled", "cancelled")
    db.expire_all()
    row = db.get(ImperiumMission, carrier.id)
    assert (row.completion_note, row.failure_reason, row.ended_at is not None) == ("Examen reporté", None, True)
    assert (db.get(ImperiumMission, annex.id).status, db.get(ImperiumMission, annex.id).annex_of_mission_id) == ("backlog", None)
    event = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "planning.mission.aborted"))
    assert (event.payload["reason"], event.payload["previous_status"], event.payload["cancellation_reason"]) == (
        "cancelled", "active", "Examen reporté",
    )
    assert client.post(f"{BASE}/{carrier.id}/cancel", headers=key, json={"reason": "Examen reporté"}).json() == body
    assert client.post(f"{BASE}/{carrier.id}/cancel", headers=key, json={"reason": "Autre"}).status_code == 409
    assert client.post(f"{BASE}/{carrier.id}/cancel", headers=_key(), json={"reason": "Encore"}).status_code == 409


def test_cancel_a_backlog_mission_clears_its_slot(db) -> None:
    user = _user(db)
    client = _client(db, user)
    planned = _mission(db, user, "Vidange", "backlog", planned_start_at=datetime.now(UTC) + timedelta(hours=2))
    body = client.post(f"{BASE}/{planned.id}/cancel", headers=_key(), json={"reason": "Faite au garage hier"}).json()
    assert body["mission"]["status"] == "cancelled"
    db.expire_all()
    assert db.get(ImperiumMission, planned.id).planned_start_at is None


def test_cancel_needs_a_reason_a_key_and_an_open_mission(db) -> None:
    user = _user(db)
    client = _client(db, user)
    done = _mission(db, user, "Déjà faite", "completed", ended_at=datetime.now(UTC))
    backlog = _mission(db, user, "En attente", "backlog")
    assert client.post(f"{BASE}/{backlog.id}/cancel", headers=_key(), json={"reason": "   "}).status_code == 422
    assert client.post(f"{BASE}/{backlog.id}/cancel", headers=_key(), json={}).status_code == 422
    assert client.post(f"{BASE}/{backlog.id}/cancel", json={"reason": "x"}).status_code == 400
    assert client.post(f"{BASE}/{done.id}/cancel", headers=_key(), json={"reason": "x"}).status_code == 409
    assert client.post(f"{BASE}/{uuid4()}/cancel", headers=_key(), json={"reason": "x"}).status_code == 404
    other = _client(db, _user(db))
    assert other.post(f"{BASE}/{backlog.id}/cancel", headers=_key(), json={"reason": "x"}).status_code == 404
