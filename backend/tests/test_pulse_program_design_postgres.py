"""PostgreSQL : programme d'entraînement conçu par le cerveau (P3) — demande, relecture, acceptation, séances."""
from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from uuid import UUID, uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("pulse program design DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_pulse_equipment, imperium_pulse_training  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.imperium import PulsePainLog, PulseWorkout  # noqa: E402
from app.models.pulse import PulseProgram, PulseProgramTarget  # noqa: E402
from app.services.params import set_parameter  # noqa: E402
from app.services.pulse import program_design, training  # noqa: E402
from app.services.pulse.expiry import PARIS  # noqa: E402

P = "/api/imperium/pulse"
REQUEST = {"goal": "Renforcer le dos et perdre un peu de ventre", "level": "beginner", "days": ["MO", "WE", "FR"],
           "session_minutes": 40, "preferred_time": "18:30", "note": "Pas de saut, voisins en dessous."}


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


@pytest.fixture()
def enabled(db):
    set_parameter(db, code="pulse.programs_enabled", value=True, origin="user", rationale_fr="Test.")
    db.commit()
    yield
    set_parameter(db, code="pulse.programs_enabled", value=False, origin="user", rationale_fr="Test.")
    db.commit()


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"p3-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_pulse_training.router, prefix=P)
    app.include_router(imperium_pulse_equipment.router, prefix=P)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def _exercise(name, group, sets=3, reps=12, equipment=(), duration=None):
    return {"name": name, "muscle_group": group, "sets": sets, "reps": None if duration else reps,
            "duration_seconds": duration, "rest_seconds": 75, "equipment": list(equipment),
            "notes": "Dos droit, mouvement lent."}


def _design(**changes) -> dict:
    design = {
        "name": "Dos solide", "phase": "fondations", "weeks_total": 4,
        "progression_fr": "Une répétition de plus chaque semaine.", "recovery_fr": "48 h entre deux séances de dos.",
        "rationale_fr": "Trois séances courtes, sans saut, centrées sur le dos et la sangle abdominale.",
        "sessions": [
            {"weekday": "MO", "title": "Dos et gainage", "session_type": "strength", "duration_minutes": 35,
             "intensity": "medium", "systemic_load": 5,
             "exercises": [_exercise("Rowing à l'élastique", "back", equipment=["élastique"]),
                           _exercise("Planche", "core", duration=40)]},
            {"weekday": "WE", "title": "Mobilité", "session_type": "mobility", "duration_minutes": 25, "intensity": "low",
             "systemic_load": 2, "exercises": [_exercise("Chat-vache", None, sets=2, reps=10)]},
            {"weekday": "FR", "title": "Dos et jambes", "session_type": "strength", "duration_minutes": 40,
             "intensity": "medium", "systemic_load": 6,
             "exercises": [_exercise("Tirage élastique", "back", sets=4, equipment=["Elastique"]),
                           _exercise("Squat", "quads")]},
        ],
    }
    design.update(changes)
    return design


def _fake(outputs):
    calls = []

    def call(system, prompt, schema):
        calls.append(prompt)
        return outputs[min(len(calls), len(outputs)) - 1], "cloud", {"model": "fake"}
    call.calls = calls
    return call


def _requested(client) -> dict:
    response = client.post(f"{P}/programs/requests", headers=_key(), json=REQUEST)
    assert response.status_code == 202, response.text
    return response.json()


def test_routes_closed_until_enabled(db):
    client = _client(db, _user(db))
    assert client.post(f"{P}/programs/requests", headers=_key(), json=REQUEST).json()["code"] == "PULSE_PROGRAMS_DISABLED"
    assert client.get(f"{P}/programs/requests/latest").status_code == 409


def test_design_is_checked_retried_and_proposed(db, enabled):
    user = _user(db)
    client = _client(db, user)
    client.post(f"{P}/equipment", json={"name": "Élastique"})
    db.add(PulsePainLog(user_id=user.id, body_zone="other", location="Genou gauche", severity=4, workout_impact=True,
                        noted_at=datetime.now(UTC), idempotency_key="pain", request_hash="h"))
    db.commit()
    requested = _requested(client)
    assert client.post(f"{P}/programs/requests", headers=_key(), json=REQUEST).status_code == 409  # une à la fois
    bad = _design(sessions=[{**_design()["sessions"][0], "weekday": "TU", "duration_minutes": 60,
                             "exercises": [*[_exercise("Développé couché", "chest", sets=10, equipment=["barre"])] * 3,
                                           {**_exercise("Planche", "core"), "reps": None}]}])
    fake = _fake([bad, _design()])
    program_design.generate(db, UUID(requested["id"]), call=fake)
    assert len(fake.calls) == 2
    retry = fake.calls[1]
    for expected in ("jour non disponible", "60 min", "« barre », absent", "plus que 25", "des répétitions OU une durée"):
        assert expected in retry, expected
    assert "Genou gauche : 4/10 ; gêne le sport" in fake.calls[0] and "- Élastique" in fake.calls[0]
    latest = client.get(f"{P}/programs/requests/latest").json()["request"]
    assert latest["id"] == requested["id"] and latest["status"] == "proposed"
    assert latest["weekly_sets"] == {"back": 7, "core": 3, "quads": 3}
    # Matériel ramené au nom exact de la liste de l'utilisateur.
    assert latest["design"]["sessions"][2]["exercises"][0]["equipment"] == ["Élastique"]


def test_without_a_brain_the_request_fails_honestly(db, enabled):
    client = _client(db, _user(db))
    requested = _requested(client)
    program_design.generate(db, UUID(requested["id"]))
    latest = client.get(f"{P}/programs/requests/latest").json()["request"]
    assert latest["status"] == "failed" and "Aucun cerveau" in latest["error"]
    assert client.post(f"{P}/programs/requests/{requested['id']}/reject").json()["status"] == "rejected"
    assert client.get(f"{P}/programs/requests/latest").json() == {"request": None}


def test_accepting_creates_the_program_targets_and_sessions(db, enabled):
    user = _user(db)
    client = _client(db, user)
    client.post(f"{P}/equipment", json={"name": "Élastique"})
    old = PulseProgram(id=uuid4(), user_id=user.id, name="Ancien", objective_weights={},
                       mesocycle={"phase": "x", "week_current": 1, "weeks_total": 4}, status="active", version=1,
                       idempotency_key="old", request_hash="h")
    db.add(old)
    db.flush()
    future = datetime.now(UTC) + timedelta(days=30)
    db.add(PulseWorkout(user_id=user.id, title="Ancienne séance", status="planned", planned_at=future, program_id=old.id,
                        idempotency_key="old-w", request_hash="h"))
    db.commit()
    requested = _requested(client)
    program_design.generate(db, UUID(requested["id"]), call=_fake([_design()]))
    today = datetime.now(PARIS).date()
    monday = today - timedelta(days=today.weekday()) + timedelta(days=7)
    accepted = program_design.accept(db, current_user=user, request_id=requested["id"],
                                     now=datetime.combine(monday, time(6), tzinfo=PARIS))
    assert accepted.status == "accepted"
    assert client.post(f"{P}/programs/requests/{requested['id']}/accept").json()["status"] == "accepted"  # rejouer
    program = db.get(PulseProgram, accepted.program_id)
    assert program.status == "active" and program.mesocycle["weeks_total"] == 4 and program.mesocycle["phase"] == "fondations"
    db.refresh(old)
    assert old.status == "superseded"
    workouts = list(db.scalars(select(PulseWorkout).where(PulseWorkout.user_id == user.id).order_by(PulseWorkout.planned_at)))
    assert "Ancienne séance" not in [w.title for w in workouts]
    assert len(workouts) == 12  # 3 séances × 4 semaines, à partir du lundi
    first = workouts[0]
    assert first.planned_at.astimezone(PARIS).time() == time(18, 30) and first.program_id == program.id
    assert first.exercises[0]["rest_seconds"] == 75 and first.equipment == ["Élastique"]
    weeks = {row.week_start for row in db.scalars(select(PulseProgramTarget).where(PulseProgramTarget.program_id == program.id))}
    assert len(weeks) == 4 and monday in weeks  # les 4 semaines du programme
    current = training.current(db, current_user=user, now=datetime.combine(monday, time(7), tzinfo=PARIS))
    back = next(t for t in current.targets if t.muscle_group == "back")
    assert (back.target_sets, back.planned_sets) == (7, 7)
