"""PostgreSQL : relais Vector → Imperium après la clôture d'une session VTC (VEC-11, doc 43 §3.1)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("vector session replan DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_vector  # noqa: E402
from app.models import ai  # noqa: E402,F401 - tâche IA créée par le replan
from app.models.auth import User  # noqa: E402
from app.models.imperium import PlanningDay, PlanningReplanEvent  # noqa: E402

BASE = "/api/imperium/vector/sessions"


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
        {"id": str(user_id), "email": f"vecreplan-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_vector.router, prefix="/api/imperium/vector")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def _open_day(db, user) -> None:
    now = datetime.now(UTC)
    db.add(PlanningDay(user_id=user.id, started_at=now - timedelta(hours=2), start_local_date=date.today(),
                       timezone="Europe/Paris", felt_energy=3, idempotency_key=uuid4().hex))
    db.commit()


def _session(client) -> dict:
    created = client.post(BASE, headers=_key(), json={"target_ca_cents": 20000})
    assert created.status_code == 201, created.text
    return created.json()


def test_replan_after_a_completed_session(db) -> None:
    user = _user(db)
    client = _client(db, user)
    _open_day(db, user)
    session = _session(client)
    early = client.post(f"{BASE}/{session['id']}/replan")
    assert (early.status_code, early.json()["code"]) == (409, "RIDES_SESSION_STATE")  # session encore en cours
    done = client.post(f"{BASE}/{session['id']}/complete", headers=_key(), json={}).json()
    assert done["replan_event_id"] is None
    first = client.post(f"{BASE}/{session['id']}/replan")
    assert first.status_code == 201, first.text
    body = first.json()
    assert (body["replan"]["hook_type"], body["replan"]["status"]) == ("vector_session_ended", "requested")
    assert body["session"]["replan_event_id"] == body["replan"]["id"]
    again = client.post(f"{BASE}/{session['id']}/replan")
    assert (again.status_code, again.json()["replan"]["id"]) == (200, body["replan"]["id"])
    row = db.scalar(select(PlanningReplanEvent).where(PlanningReplanEvent.user_id == user.id))
    assert (row.trigger, row.hook_type) == ("hook", "vector_session_ended")
    assert client.get(f"{BASE}/{session['id']}").json()["replan_event_id"] == body["replan"]["id"]


def test_replan_refusals(db) -> None:
    user = _user(db)
    client = _client(db, user)
    session = _session(client)
    client.post(f"{BASE}/{session['id']}/complete", headers=_key(), json={})
    no_day = client.post(f"{BASE}/{session['id']}/replan")
    assert (no_day.status_code, no_day.json()["code"]) == (409, "DAY_NOT_STARTED")
    assert _client(db, _user(db)).post(f"{BASE}/{session['id']}/replan").status_code == 404
    assert client.post(f"{BASE}/{uuid4()}/replan").status_code == 404
