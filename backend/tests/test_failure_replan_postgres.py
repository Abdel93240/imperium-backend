"""PostgreSQL : mission ratée → replan selon replan_on_failure_urgent / _other (doc 43 §3.1, §15)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("failure replan DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium, imperium_settings  # noqa: E402
from app.models import ai  # noqa: E402,F401 - tâche IA créée par le replan
from app.models.auth import User  # noqa: E402
from app.models.imperium import ImperiumMission, PlanningDay, PlanningReplanEvent  # noqa: E402


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


def _user(db, *, open_day=True) -> User:
    user_id = uuid4()
    db.execute(
        text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) VALUES (:id, :email, FALSE, now(), now())"),
        {"id": str(user_id), "email": f"failreplan-{user_id}@example.test"},
    )
    if open_day:
        started = datetime.now(UTC) - timedelta(hours=1)
        db.add(PlanningDay(user_id=user_id, started_at=started, start_local_date=started.date(), timezone="Europe/Paris",
                           felt_energy=3, idempotency_key=uuid4().hex))
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/api/imperium")
    app.include_router(imperium_settings.router, prefix="/api/imperium")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _active(db, user, deadline_in_hours=None) -> ImperiumMission:
    now = datetime.now(UTC)
    mission = ImperiumMission(user_id=user.id, title="Mission", status="active", started_at=now - timedelta(minutes=30),
                              deadline_at=now + timedelta(hours=deadline_in_hours) if deadline_in_hours is not None else None)
    db.add(mission)
    db.commit()
    return mission


def _fail(client, mission, key=None):
    response = client.post(f"/api/imperium/missions/{mission.id}/fail", headers={"Idempotency-Key": key or uuid4().hex},
                           json={"failure_reason_code": "too_tired"})
    assert response.status_code == 200, response.text
    return response.json()


def test_urgent_failure_requests_a_replan(db) -> None:
    user = _user(db)
    client = _client(db, user)
    mission = _active(db, user, deadline_in_hours=3)
    key = uuid4().hex
    body = _fail(client, mission, key)
    replan = body["replan"]
    assert (body["mission"]["status"], replan["action"], replan["urgent"], replan["status"]) == ("failed", "replan", True, "requested")
    row = db.get(PlanningReplanEvent, replan["replan_id"])
    assert (row.trigger, row.hook_type, row.status) == ("hook", "mission_failed", "requested")
    assert _fail(client, mission, key) == body  # rejeu : même réponse, pas de second replan
    assert len(list(db.scalars(select(PlanningReplanEvent).where(PlanningReplanEvent.user_id == user.id)))) == 1


def test_other_failure_asks_and_settings_change_it(db) -> None:
    user = _user(db)
    client = _client(db, user)
    body = _fail(client, _active(db, user))
    assert (body["replan"]["action"], body["replan"]["urgent"], body["replan"]["status"]) == ("ask", False, "suggested")
    assert body["replan"]["message"] == "Mission ratée : veux-tu replanifier ta journée ?"
    assert db.scalar(select(PlanningReplanEvent).where(PlanningReplanEvent.user_id == user.id)) is None
    client.patch("/api/imperium/settings", json={"replan_on_failure_other": "replan", "replan_on_failure_urgent": "ask"})
    first = _fail(client, _active(db, user, deadline_in_hours=48))
    assert (first["replan"]["action"], first["replan"]["status"]) == ("replan", "requested")
    second = _fail(client, _active(db, user))
    assert (second["replan"]["status"], second["mission"]["status"]) == ("already_open", "failed")
    urgent = _fail(client, _active(db, user, deadline_in_hours=1))
    assert (urgent["replan"]["action"], urgent["replan"]["urgent"]) == ("ask", True)


def test_failure_without_open_day_is_kept(db) -> None:
    user = _user(db, open_day=False)
    client = _client(db, user)
    mission = _active(db, user, deadline_in_hours=2)
    body = _fail(client, mission)
    assert (body["replan"]["status"], body["replan"]["message"]) == ("no_open_day", "Journée non démarrée : pas de replan.")
    db.expire_all()
    assert db.get(ImperiumMission, mission.id).status == "failed"
