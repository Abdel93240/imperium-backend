"""PostgreSQL : replan demandé depuis une mission annulée ou ratée (doc 43 §3.1, hook « annulée »)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("mission replan DB tests")

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
        {"id": str(user_id), "email": f"misreplan-{user_id}@example.test"},
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


def _cancel(client, mission):
    response = client.post(f"/api/imperium/missions/{mission.id}/cancel", headers={"Idempotency-Key": uuid4().hex},
                           json={"reason": "Rendez-vous déplacé"})
    assert response.status_code == 200, response.text
    return response.json()


def test_cancelled_active_mission_suggests_then_requests_a_replan(db) -> None:
    user = _user(db)
    client = _client(db, user)
    mission = _active(db, user)
    body = _cancel(client, mission)
    assert (body["replan"]["action"], body["replan"]["status"]) == ("ask", "suggested")
    assert body["replan"]["message"] == "Mission annulée : veux-tu replanifier ta journée ?"
    assert db.scalar(select(PlanningReplanEvent).where(PlanningReplanEvent.user_id == user.id)) is None
    first = client.post(f"/api/imperium/missions/{mission.id}/replan")
    assert first.status_code == 201, first.text
    replan = first.json()["replan"]
    assert (replan["hook_type"], replan["status"]) == ("mission_cancelled", "requested")
    assert first.json()["mission"]["replan_event_id"] == replan["id"]
    again = client.post(f"/api/imperium/missions/{mission.id}/replan")
    assert (again.status_code, again.json()["replan"]["id"]) == (200, replan["id"])


def test_backlog_cancel_suggests_nothing(db) -> None:
    user = _user(db)
    client = _client(db, user)
    mission = ImperiumMission(user_id=user.id, title="Plus tard", status="backlog", started_at=datetime.now(UTC))
    db.add(mission)
    db.commit()
    assert _cancel(client, mission)["replan"] is None


def test_failed_mission_with_ask_then_accepted(db) -> None:
    user = _user(db)
    client = _client(db, user)
    mission = _active(db, user)
    failed = client.post(f"/api/imperium/missions/{mission.id}/fail", headers={"Idempotency-Key": uuid4().hex},
                         json={"failure_reason_code": "too_tired"}).json()
    assert failed["replan"]["status"] == "suggested"
    accepted = client.post(f"/api/imperium/missions/{mission.id}/replan")
    assert (accepted.status_code, accepted.json()["replan"]["hook_type"]) == (201, "mission_failed")


def test_automatic_failure_replan_is_linked(db) -> None:
    user = _user(db)
    client = _client(db, user)
    mission = _active(db, user, deadline_in_hours=2)
    failed = client.post(f"/api/imperium/missions/{mission.id}/fail", headers={"Idempotency-Key": uuid4().hex},
                         json={"failure_reason_code": "too_tired"}).json()
    again = client.post(f"/api/imperium/missions/{mission.id}/replan")
    assert (again.status_code, again.json()["replan"]["id"]) == (200, failed["replan"]["replan_id"])


def test_mission_replan_refusals(db) -> None:
    user = _user(db)
    client = _client(db, user)
    mission = _active(db, user)
    still_active = client.post(f"/api/imperium/missions/{mission.id}/replan")
    assert (still_active.status_code, still_active.json()["code"]) == (409, "MISSION_NOT_ENDED")
    assert _client(db, _user(db)).post(f"/api/imperium/missions/{mission.id}/replan").status_code == 404
    lonely = _user(db, open_day=False)
    lonely_client = _client(db, lonely)
    other = _active(db, lonely)
    _cancel(lonely_client, other)
    no_day = lonely_client.post(f"/api/imperium/missions/{other.id}/replan")
    assert (no_day.status_code, no_day.json()["code"]) == (409, "DAY_NOT_STARTED")
