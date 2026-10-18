"""PostgreSQL : replan de la journée accepté depuis une douleur (PUL-09, doc 43 §3.1, DECISION_demarrage_journee)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("pulse pain replan DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_pulse_health as routes  # noqa: E402
from app.models import ai  # noqa: E402,F401 - tâche IA créée par le replan
from app.models.auth import User  # noqa: E402
from app.models.imperium import PlanningDay, PlanningReplanEvent  # noqa: E402

P = "/api/imperium/pulse"
PAIN = f"{P}/pain-logs"


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
        {"id": str(user_id), "email": f"painreplan-{user_id}@example.test"},
    )
    if open_day:
        started = datetime.now(UTC) - timedelta(hours=2)
        db.add(PlanningDay(user_id=user_id, started_at=started, start_local_date=started.date(), timezone="Europe/Paris",
                           felt_energy=3, idempotency_key=uuid4().hex))
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(routes.router, prefix=P)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _consented(db, **user_kwargs):
    user = _user(db, **user_kwargs)
    client = _client(db, user)
    version = next(c for c in client.get(f"{P}/consents").json()["items"] if c["domain"] == "pain")["text_version"]
    client.post(f"{P}/consents/pain", json={"text_version": version})
    return user, client


def _log(client, severity=9) -> dict:
    response = client.post(PAIN, headers={"Idempotency-Key": uuid4().hex},
                           json={"body_zone": "lower_back", "severity": severity, "noted_at": datetime.now(UTC).isoformat()})
    assert response.status_code == 201, response.text
    return response.json()


def test_accepting_the_replan_from_a_strong_pain(db) -> None:
    user, client = _consented(db)
    log = _log(client)
    assert (log["suggest_replan"], log["replan_event_id"]) == (True, None)
    created = client.post(f"{PAIN}/{log['id']}/replan")
    assert created.status_code == 201, created.text
    body = created.json()
    assert (body["replan"]["trigger"], body["replan"]["hook_type"], body["replan"]["status"]) == ("hook", "pain", "requested")
    assert (body["pain_log"]["replan_event_id"], body["pain_log"]["suggest_replan"]) == (body["replan"]["id"], False)
    again = client.post(f"{PAIN}/{log['id']}/replan")
    assert (again.status_code, again.json()["replan"]["id"]) == (200, body["replan"]["id"])
    other = _log(client, severity=3)  # toute douleur en cours, après accord
    busy = client.post(f"{PAIN}/{other['id']}/replan")
    assert (busy.status_code, busy.json()["code"]) == (409, "REPLAN_ALREADY_OPEN")
    db.execute(text("UPDATE planning_replan_events SET status = 'cancelled' WHERE id = :id"), {"id": body["replan"]["id"]})
    db.commit()
    cooldown = client.post(f"{PAIN}/{other['id']}/replan")
    assert (cooldown.status_code, cooldown.json()["code"]) == (409, "REPLAN_COOLDOWN")
    assert db.get(PlanningReplanEvent, body["replan"]["id"]).user_id == user.id


def test_replan_refusals(db) -> None:
    _, client = _consented(db, open_day=False)
    log = _log(client)
    closed = client.post(f"{PAIN}/{log['id']}/replan")
    assert (closed.status_code, closed.json()["code"]) == (409, "DAY_NOT_STARTED")
    client.post(f"{PAIN}/{log['id']}/resolve")
    resolved = client.post(f"{PAIN}/{log['id']}/replan")
    assert (resolved.status_code, resolved.json()["code"]) == (409, "PAIN_RESOLVED")
    client.delete(f"{P}/consents/pain")
    assert client.post(f"{PAIN}/{log['id']}/replan").json()["code"] == "CONSENT_REQUIRED"
    _, stranger = _consented(db)
    assert stranger.post(f"{PAIN}/{log['id']}/replan").status_code == 404
