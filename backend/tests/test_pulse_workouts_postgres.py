"""PostgreSQL : séances de sport Pulse — planifier, démarrer, terminer, sauter (doc 40 §13.1–§13.2)."""
from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("pulse workouts DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_pulse_workouts as routes  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402

BASE = "/api/imperium/pulse/workouts"


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
        {"id": str(user_id), "email": f"workout-{user_id}@example.test"},
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


PLAN = {
    "title": "Haut du corps", "planned_at": "2026-10-17T16:00:00+00:00", "duration_minutes": 45, "intensity": "medium",
    "exercises": [{"name": "Pompes", "sets": 4, "reps": 12}, {"name": "Halo haltère", "sets": 3, "reps": 10, "weight_kg": 20},
                  {"name": "Gainage", "sets": 3, "duration_seconds": 60}],
    "equipment": ["Planche à pompes", "Haltère 20 kg"],
}


def _plan(client, **extra) -> dict:
    response = client.post(BASE, headers=_key(), json={**PLAN, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_plan_then_list_by_paris_day(db) -> None:
    client = _client(db, _user(db))
    workout = _plan(client)
    assert (workout["status"], workout["version"], workout["intensity"]) == ("planned", 1, "medium")
    assert [e["name"] for e in workout["exercises"]] == ["Pompes", "Halo haltère", "Gainage"]
    assert workout["exercises"][1]["weight_kg"] == "20" and workout["equipment"] == ["Planche à pompes", "Haltère 20 kg"]
    _plan(client, title="Course", planned_at="2026-10-18T22:30:00+00:00", exercises=[])  # 19/10 à Paris
    listed = client.get(BASE, params={"from_day": "2026-10-17", "to_day": "2026-10-18"}).json()["items"]
    assert [w["title"] for w in listed] == ["Haut du corps"]
    assert len(client.get(BASE, params={"from_day": "2026-10-17", "to_day": "2026-10-19"}).json()["items"]) == 2


def test_plan_idempotency_and_validation(db) -> None:
    client = _client(db, _user(db))
    assert client.post(BASE, json=PLAN).status_code == 400
    first = client.post(BASE, headers={"Idempotency-Key": "w1"}, json=PLAN)
    again = client.post(BASE, headers={"Idempotency-Key": "w1"}, json=PLAN)
    other = client.post(BASE, headers={"Idempotency-Key": "w1"}, json={**PLAN, "title": "Jambes"})
    assert first.status_code == 201 and again.status_code == 200 and again.json()["id"] == first.json()["id"]
    assert other.status_code == 409
    for bad in [{"title": " "}, {"intensity": "extreme"}, {"duration_minutes": 0}, {"exercises": [{"name": "X", "sets": 0}]},
                {"exercises": [{"name": "X"}] * 51}, {"source_mission_id": str(uuid4())}]:
        assert client.post(BASE, headers=_key(), json={**PLAN, **bad}).status_code in (404, 422), bad


def test_edit_needs_the_read_version(db) -> None:
    client = _client(db, _user(db))
    workout = _plan(client)
    edited = client.patch(f"{BASE}/{workout['id']}", headers=_key(), json={"version": 1, "duration_minutes": 30})
    assert edited.status_code == 200 and (edited.json()["duration_minutes"], edited.json()["version"]) == (30, 2)
    stale = client.patch(f"{BASE}/{workout['id']}", headers=_key(), json={"version": 1, "title": "Autre"})
    assert stale.status_code == 409 and stale.json()["code"] == "WORKOUT_VERSION_CONFLICT"
    assert stale.json()["current"]["version"] == 2


def test_start_then_complete_with_results(db) -> None:
    user = _user(db)
    client = _client(db, user)
    workout = _plan(client)
    started = client.post(f"{BASE}/{workout['id']}/start", json={"body_state": "Un peu fatigué"})
    assert started.status_code == 200 and started.json()["status"] == "in_progress"
    assert started.json()["started_at"] is not None and started.json()["body_state_at_start"] == "Un peu fatigué"
    assert client.post(f"{BASE}/{workout['id']}/start", json={}).json()["started_at"] == started.json()["started_at"]
    payload = {"intensity_score": 7, "duration_minutes": 50, "notes": "Bonne séance",
               "results": [{"index": 0, "done_sets": 4, "done_reps": [12, 12, 10, 8]},
                           {"index": 2, "skipped": True, "skip_reason": "Douleur au poignet"}]}
    done = client.post(f"{BASE}/{workout['id']}/complete", headers={"Idempotency-Key": "c1"}, json=payload)
    assert done.status_code == 200, done.text
    body = done.json()
    assert (body["status"], body["intensity_score"], body["actual_duration_minutes"], body["notes_post_workout"]) == (
        "completed", 7, 50, "Bonne séance")
    assert body["exercises"][0]["done_sets"] == 4 and body["exercises"][0]["done_reps"] == [12, 12, 10, 8]
    assert body["exercises"][1]["done_sets"] is None  # pas de résultat envoyé
    assert (body["exercises"][2]["skipped"], body["exercises"][2]["skip_reason"]) == (True, "Douleur au poignet")
    assert client.post(f"{BASE}/{workout['id']}/complete", headers={"Idempotency-Key": "c1"}, json=payload).json() == body
    assert client.post(f"{BASE}/{workout['id']}/complete", headers={"Idempotency-Key": "c2"}, json=payload).status_code == 409
    assert client.patch(f"{BASE}/{workout['id']}", headers=_key(), json={"version": body["version"], "title": "x"}).status_code == 409
    event = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "pulse.workout.completed"))
    assert event.payload["exercises_skipped"] == 1 and event.payload["intensity_score"] == 7


def test_complete_without_start_and_bad_results(db) -> None:
    client = _client(db, _user(db))
    workout = _plan(client)
    assert client.post(f"{BASE}/{workout['id']}/complete", headers=_key(),
                       json={"results": [{"index": 9, "done_sets": 1}]}).status_code == 422
    assert client.post(f"{BASE}/{workout['id']}/complete", headers=_key(),
                       json={"results": [{"index": 0, "skipped": True}]}).status_code == 422  # raison obligatoire
    done = client.post(f"{BASE}/{workout['id']}/complete", headers=_key(), json={"intensity_score": 5})
    assert done.status_code == 200 and done.json()["started_at"] is None and done.json()["completed_at"] is not None


def test_skip_with_reason(db) -> None:
    user = _user(db)
    client = _client(db, user)
    workout = _plan(client)
    assert client.post(f"{BASE}/{workout['id']}/skip", headers=_key(), json={"reason": " "}).status_code == 422
    skipped = client.post(f"{BASE}/{workout['id']}/skip", headers={"Idempotency-Key": "s1"}, json={"reason": "Trop fatigué"})
    assert skipped.status_code == 200 and (skipped.json()["status"], skipped.json()["skip_reason"]) == ("skipped", "Trop fatigué")
    again = client.post(f"{BASE}/{workout['id']}/skip", headers={"Idempotency-Key": "s1"}, json={"reason": "Trop fatigué"})
    assert again.status_code == 200
    assert client.post(f"{BASE}/{workout['id']}/start", json={}).status_code == 409
    assert client.post(f"{BASE}/{workout['id']}/complete", headers=_key(), json={}).status_code == 409
    event = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "pulse.workout.skipped"))
    assert event.payload["reason"] == "Trop fatigué"


def test_other_users_workouts_are_not_found(db) -> None:
    owner, other = _user(db), _user(db)
    workout = _plan(_client(db, owner))
    stranger = _client(db, other)
    assert stranger.get(f"{BASE}/{workout['id']}").status_code == 404
    assert stranger.post(f"{BASE}/{workout['id']}/start", json={}).status_code == 404
    assert stranger.get(BASE, params={"from_day": "2026-10-17", "to_day": "2026-10-17"}).json()["items"] == []
