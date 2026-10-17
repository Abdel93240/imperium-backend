"""PostgreSQL : journal des douleurs Pulse sous consentement « pain » (doc 40 §16, doc 08 PULSE-004)."""
from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("pulse pain DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_pulse_dashboard, imperium_pulse_workouts  # noqa: E402
from app.api.v1.routes import imperium_pulse_health as routes  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402

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


def _user(db) -> User:
    user_id = uuid4()
    db.execute(
        text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) VALUES (:id, :email, FALSE, now(), now())"),
        {"id": str(user_id), "email": f"pain-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    for router in (routes.router, imperium_pulse_dashboard.router, imperium_pulse_workouts.router):
        app.include_router(router, prefix="/api/imperium/pulse")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def _consent(client) -> None:
    version = next(c for c in client.get(f"{P}/consents").json()["items"] if c["domain"] == "pain")["text_version"]
    assert client.post(f"{P}/consents/pain", json={"text_version": version}).status_code == 200


def _log(client, **extra) -> dict:
    payload = {"body_zone": "knee", "side": "left", "severity": 4, "noted_at": "2026-10-17T08:00:00+00:00", **extra}
    response = client.post(PAIN, headers=_key(), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_writing_needs_the_pain_consent(db) -> None:
    client = _client(db, _user(db))
    refused = client.post(PAIN, headers=_key(), json={"body_zone": "knee", "severity": 4})
    assert refused.status_code == 403 and refused.json() == {
        "detail": "Consent required for pain data.", "code": "CONSENT_REQUIRED", "domain": "pain"}
    body_only = client.get(f"{P}/consents").json()["items"][0]["text_version"]
    client.post(f"{P}/consents/body", json={"text_version": body_only})
    assert client.post(PAIN, headers=_key(), json={"body_zone": "knee", "severity": 4}).status_code == 403


def test_log_list_and_events_without_details(db) -> None:
    user = _user(db)
    client = _client(db, user)
    _consent(client)
    log = _log(client, pain_type="Pincement", limitation_notes="Mal en descendant les escaliers", workout_impact=True)
    assert (log["body_zone"], log["side"], log["severity"], log["workout_impact"], log["resolved_at"]) == (
        "knee", "left", 4, True, None)
    assert log["suggest_replan"] is False and log["replan_message"] is None
    _log(client, body_zone="lower_back", side=None, severity=2, noted_at="2026-10-16T08:00:00+00:00")
    assert [p["body_zone"] for p in client.get(PAIN).json()["items"]] == ["knee", "lower_back"]
    event = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "pulse.pain.logged"))
    assert set(event.payload) == {"pain_log_id"} and event.privacy_level == "high"


def test_high_severity_suggests_a_replan_without_acting(db) -> None:
    client = _client(db, _user(db))
    _consent(client)
    log = _log(client, severity=9)
    assert log["suggest_replan"] is True
    assert log["replan_message"] == "Douleur forte : veux-tu replanifier ta journée ?"


def test_linked_workout_must_be_the_users(db) -> None:
    owner, other = _user(db), _user(db)
    client = _client(db, owner)
    _consent(client)
    workout = client.post(f"{P}/workouts", headers=_key(), json={"title": "Squats", "planned_at": "2026-10-17T17:00:00+00:00"}).json()
    assert _log(client, workout_id=workout["id"])["workout_id"] == workout["id"]
    stranger = _client(db, other)
    _consent(stranger)
    assert stranger.post(PAIN, headers=_key(), json={"body_zone": "knee", "severity": 3, "workout_id": workout["id"]}).status_code == 404


@pytest.mark.parametrize("payload", [{"body_zone": "nez", "severity": 3}, {"body_zone": "knee", "severity": 11},
                                     {"body_zone": "knee", "severity": -1}, {"body_zone": "knee", "side": "haut", "severity": 2},
                                     {"body_zone": "knee", "severity": 2, "photo": "x"}])
def test_invalid_logs_are_rejected(db, payload) -> None:
    client = _client(db, _user(db))
    _consent(client)
    assert client.post(PAIN, headers=_key(), json=payload).status_code == 422


def test_resolve_hides_from_the_open_list(db) -> None:
    client = _client(db, _user(db))
    _consent(client)
    log = _log(client)
    resolved = client.post(f"{PAIN}/{log['id']}/resolve")
    assert resolved.status_code == 200 and resolved.json()["resolved_at"] is not None
    assert client.post(f"{PAIN}/{log['id']}/resolve").json()["resolved_at"] == resolved.json()["resolved_at"]
    assert client.get(PAIN).json()["items"] == []
    assert len(client.get(PAIN, params={"include_resolved": True}).json()["items"]) == 1


def test_idempotency_and_deletion(db) -> None:
    from app.models.imperium import PulsePainLog

    user = _user(db)
    client = _client(db, user)
    _consent(client)
    payload = {"body_zone": "wrist", "side": "right", "severity": 5}
    first = client.post(PAIN, headers={"Idempotency-Key": "p1"}, json=payload)
    again = client.post(PAIN, headers={"Idempotency-Key": "p1"}, json=payload)
    other = client.post(PAIN, headers={"Idempotency-Key": "p1"}, json={**payload, "severity": 6})
    assert first.status_code == 201 and again.status_code == 200 and other.status_code == 409
    client.delete(f"{P}/consents/pain")
    assert client.delete(f"{PAIN}/{first.json()['id']}").status_code == 204
    _consent(client)
    _log(client)
    _log(client)
    assert client.delete(PAIN).status_code == 422
    assert client.delete(PAIN, params={"confirm": True}).json() == {"deleted": 2}
    db.expire_all()
    assert db.scalars(select(PulsePainLog).where(PulsePainLog.user_id == user.id)).all() == []


def test_dashboard_shows_open_pain_without_details(db) -> None:
    client = _client(db, _user(db))
    _consent(client)
    _log(client, severity=8)
    _log(client, severity=3)
    banners = {b["kind"]: b for b in client.get(f"{P}/dashboard", params={"day": "2026-10-17"}).json()["banners"]}
    assert banners["pain_open"] == {"kind": "pain_open", "level": "warning", "message": "2 douleurs en cours, dont 1 forte."}
