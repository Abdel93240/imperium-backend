"""PostgreSQL : programme d'entraînement, cibles, dette de volume et coups de programme de P1 (spec Pulse §3.6, §8)."""
from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("pulse training DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_pulse_signals, imperium_pulse_training  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.imperium import PulseWorkout  # noqa: E402
from app.models.pulse import PulseProcedure, PulseProcedureRun, PulseProposal, PulseVolumeDebt  # noqa: E402
from app.schemas.pulse_workouts import WorkoutCompleteRequest, WorkoutCreate, WorkoutSkipRequest  # noqa: E402
from app.services.params import set_parameter  # noqa: E402
from app.services.pulse import procedures, training, workouts  # noqa: E402

P = "/api/imperium/pulse"
PARIS = ZoneInfo("Europe/Paris")
LEGS = [{"name": "Squat", "sets": 4, "muscle_group": "legs"}, {"name": "Fentes", "sets": 3, "muscle_group": "legs"}]


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    # Les routes committent : transaction externe annulée, rien ne fuit.
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"ptrain-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_pulse_training.router, prefix=P)
    app.include_router(imperium_pulse_signals.router, prefix=P)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _enable(db) -> None:
    for code in ("programs_enabled", "proposals_enabled"):
        set_parameter(db, code=f"pulse.{code}", value=True, origin="user", rationale_fr="Test.")
    db.commit()


def _program(client, name: str = "Force") -> dict:
    response = client.post(f"{P}/programs", headers={"Idempotency-Key": str(uuid4())},
                           json={"name": name, "mesocycle": {"phase": "accumulation", "week_current": 1, "weeks_total": 4}})
    assert response.status_code == 201, response.text
    return response.json()


def _day() -> date:
    """Mardi ou mercredi prochain à au moins deux jours : même semaine pour la séance et J+1."""
    today = datetime.now(UTC).astimezone(PARIS).date()
    day = today + timedelta(days=2)
    while day.weekday() not in (1, 2):
        day += timedelta(days=1)
    return day


def _workout(db, user, program_id, day: date, exercises=LEGS, **extra) -> PulseWorkout:
    read, _ = workouts.create_workout(db, current_user=user, idempotency_key=str(uuid4()), payload=WorkoutCreate(
        title="Jambes", planned_at=datetime.combine(day, time(10), tzinfo=PARIS), duration_minutes=60,
        exercises=exercises, program_id=program_id, session_type="strength", **extra))
    return db.get(PulseWorkout, read.id)


def _menu(db, user, workout) -> dict:
    return {m["code"]: m for m in procedures.legal_menu(db, user=user, workout=workout, now=datetime.now(UTC))}


def _decide(db, client, user, workout, move: dict) -> dict:
    procedure = db.scalar(select(PulseProcedure).where(PulseProcedure.code == procedures.P1))
    run = PulseProcedureRun(user_id=user.id, procedure_id=procedure.id, procedure_version=1,
                            inputs={"workout_id": str(workout.id)}, dry_run=False, status="queued", steps_log=[],
                            created_at=datetime.now(UTC))
    db.add(run)
    db.commit()
    procedures.run_queued(db, now=datetime.now(UTC))
    db.commit()
    proposal = db.scalar(select(PulseProposal).where(PulseProposal.procedure_run_id == run.id))
    response = client.post(f"{P}/proposals/{proposal.id}/decision",
                           json={"decision": "modified", "user_explanation": "Choix du coup", "modified_payload": move})
    assert response.status_code == 200, response.text
    db.refresh(workout)
    return response.json()


def test_seeds_and_program_routes(db) -> None:
    moves = db.execute(text("SELECT code, active FROM pulse_legal_moves ORDER BY code")).all()
    assert len(moves) == 8 and all(move.active for move in moves)
    user = _user(db)
    client = _client(db, user)
    assert client.get(f"{P}/programs/current").json()["code"] == "PULSE_PROGRAMS_DISABLED"
    _enable(db)
    assert client.get(f"{P}/programs/current").json()["program"] is None
    body = {"name": "Force", "mesocycle": {"phase": "accumulation", "week_current": 1, "weeks_total": 4}}
    first = client.post(f"{P}/programs", json=body, headers={"Idempotency-Key": "k1"})
    assert first.status_code == 201 and client.post(f"{P}/programs", json=body, headers={"Idempotency-Key": "k1"}).status_code == 200
    assert client.post(f"{P}/programs", json={**body, "name": "Autre"}, headers={"Idempotency-Key": "k1"}).status_code == 409
    second = _program(client, "Hypertrophie")
    assert client.get(f"{P}/programs/current").json()["program"]["id"] == second["id"]
    assert client.post(f"{P}/programs/{first.json()['id']}/status", json={"status": "active"}).status_code == 409
    assert client.post(f"{P}/programs/{second['id']}/status", json={"status": "paused"}).json()["status"] == "paused"
    assert client.post(f"{P}/programs/{second['id']}/status", json={"status": "active"}).json()["status"] == "active"
    day = _day()
    _workout(db, user, second["id"], day)
    targets = client.put(f"{P}/programs/{second['id']}/targets",
                         json={"week_start": day.isoformat(), "targets": [{"muscle_group": "legs", "target_sets": 10}]})
    assert targets.json() == [{"muscle_group": "legs", "target_sets": 10, "tolerance_sets": 2, "planned_sets": 7}]
    stored = db.execute(text("SELECT week_start FROM pulse_program_targets WHERE program_id = :p"), {"p": second["id"]}).scalar()
    assert stored == training.week_start_of(day) and stored.weekday() == 0
    stranger = _user(db)
    with pytest.raises(workouts.WorkoutNotFoundError):
        _workout(db, stranger, second["id"], day)
    assert db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "pulse.program.created"))


def test_reduce_volume_creates_debt_under_the_cap(db) -> None:
    _enable(db)
    user = _user(db)
    client = _client(db, user)
    program = _program(client)
    day = _day()
    loose = _workout(db, user, None, day + timedelta(days=1))
    assert _menu(db, user, loose)["reduce_volume"]["reasons"] == ["no_program"]
    workout = _workout(db, user, program["id"], day)
    menu = _menu(db, user, workout)
    assert menu["reduce_volume"]["options"] == [50, 60, 70]  # 80 % ne retire rien
    assert menu["swap_modality"]["options"] == ["technique", "mobility", "cardio"]
    assert (menu["split_session"]["reasons"], menu["deload_week"]["reasons"]) == (["not_coded"], ["no_doctrine"])
    assert menu["repay_debt"]["reasons"] == ["no_repayable_debt"]
    _decide(db, client, user, workout, {"move_code": "reduce_volume", "parameters": {"percent": 50}})
    assert [e["sets"] for e in workout.exercises] == [2, 2] and workout.version == 2
    [debt] = db.scalars(select(PulseVolumeDebt).where(PulseVolumeDebt.user_id == user.id)).all()
    assert (debt.muscle_group, debt.debt_sets, debt.status, debt.origin_workout_id) == ("legs", 3, "open", workout.id)
    adapted = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "pulse.program.adapted"))
    assert adapted.payload == {"program_id": program["id"], "move_code": "reduce_volume", "session_id": str(workout.id)}
    set_parameter(db, code="pulse.max_debt_sets_group", value=4, origin="user", rationale_fr="Test.")
    db.commit()
    other = _workout(db, user, program["id"], day + timedelta(days=1))
    capped = _menu(db, user, other)
    assert capped["reduce_volume"]["options"] == [70]  # 3 + 1 <= 4 ; 50 % et 60 % dépasseraient
    assert capped["swap_modality"]["reasons"] == ["debt_max"]


def test_repay_then_complete_or_skip(db) -> None:
    _enable(db)
    user = _user(db)
    client = _client(db, user)
    program = _program(client)
    day = _day()
    first = _workout(db, user, program["id"], day)
    _decide(db, client, user, first, {"move_code": "swap_modality", "parameters": {"new_session_type": "mobility"}})
    assert (first.exercises, first.session_type, first.systemic_load, first.intensity) == ([], "mobility", 3, "low")
    [debt] = db.scalars(select(PulseVolumeDebt).where(PulseVolumeDebt.user_id == user.id)).all()
    assert debt.debt_sets == 7
    client.put(f"{P}/programs/{program['id']}/targets",
               json={"week_start": day.isoformat(), "targets": [{"muscle_group": "legs", "target_sets": 8}]})
    second = _workout(db, user, program["id"], day + timedelta(days=1))
    assert _menu(db, user, second)["repay_debt"]["options"] == [str(debt.id)]
    _decide(db, client, user, second, {"move_code": "repay_debt", "parameters": {"debt_id": str(debt.id)}})
    assert [e["sets"] for e in second.exercises] == [7, 3]  # 8 + 2 − 7 = 3 séries ajoutées au premier exercice
    debts = {d.status: d for d in db.scalars(select(PulseVolumeDebt).where(PulseVolumeDebt.user_id == user.id))}
    assert (debts["open"].debt_sets, debts["scheduled"].debt_sets) == (4, 3)
    assert debts["scheduled"].repayment_workout_id == second.id
    workouts.skip_workout(db, current_user=user, workout_id=second.id, payload=WorkoutSkipRequest(reason="Fatigue"),
                          idempotency_key=str(uuid4()))
    db.refresh(debts["scheduled"])
    assert (debts["scheduled"].status, debts["scheduled"].repayment_workout_id) == ("open", None)
    third = _workout(db, user, program["id"], day + timedelta(days=2))
    option = _menu(db, user, third)["repay_debt"]["options"][0]
    _decide(db, client, user, third, {"move_code": "repay_debt", "parameters": {"debt_id": option}})
    workouts.complete_workout(db, current_user=user, workout_id=third.id, payload=WorkoutCompleteRequest(),
                              idempotency_key=str(uuid4()))
    repaid = db.scalar(select(PulseVolumeDebt).where(PulseVolumeDebt.repayment_workout_id == third.id))
    assert repaid.status == "repaid" and repaid.resolved_at is not None
    current = client.get(f"{P}/programs/current").json()
    assert {d["status"] for d in current["debts"]} == {"open"}


def test_inactive_move_is_never_legal(db) -> None:
    _enable(db)
    user = _user(db)
    program = _program(_client(db, user))
    workout = _workout(db, user, program["id"], _day())
    db.execute(text("UPDATE pulse_legal_moves SET active = false WHERE code IN ('shift_time', 'reduce_volume')"))
    menu = _menu(db, user, workout)
    assert (menu["shift_time"]["legal"], menu["shift_time"]["reasons"]) == (False, ["inactive"])
    assert menu["reduce_volume"]["reasons"] == ["inactive"] and menu["maintain"]["legal"] is True
