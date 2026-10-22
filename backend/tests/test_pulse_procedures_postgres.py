"""PostgreSQL : catalogue P1-P10, runner de procédures, P1 en essai à blanc et propositions (spec Pulse §3.3,
§7, §8, §12 ; suite ACT-PLS-15)."""
from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("pulse procedures DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_pulse_signals  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.imperium import ImperiumCalendarEvent, PulseWorkout  # noqa: E402
from app.models.pulse import (  # noqa: E402
    PulseDispatchLog,
    PulseProcedure,
    PulseProcedureRun,
    PulseProposal,
    PulseRedFlagEvent,
    PulseRedFlagRule,
)
from app.models.toolbox import AISlotTransition  # noqa: E402
from app.services.params import set_parameter  # noqa: E402
from app.services.pulse import procedures, sentinel  # noqa: E402
from app.services.runner.engine import RunContext, Window  # noqa: E402

P = "/api/imperium/pulse"
PARIS = ZoneInfo("Europe/Paris")
AT = datetime(2026, 10, 21, 5, 30, tzinfo=UTC)  # 07:30 à Paris
CODES = ("adapt_training_session", "diet_change_assessment", "exploration_pass", "injury_or_pain",
         "medical_document_ingest", "missing_sheet", "monthly_revision", "new_training_program",
         "scientific_review", "weekly_reconciliation")


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    # Les routes committent : transaction externe annulée, rien ne fuit (procédures réactivées comprises).
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
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"pproc-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _workout(db, user, at: datetime, *, intensity: str | None = None, minutes: int = 60) -> PulseWorkout:
    workout = PulseWorkout(user_id=user.id, title="Séance jambes", status="planned", planned_at=at,
                           duration_minutes=minutes, intensity=intensity, idempotency_key=str(uuid4()),
                           request_hash="h")
    db.add(workout)
    db.commit()
    return workout


def _paris(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=PARIS)


def _activate(db, *codes: str) -> None:
    db.execute(text("UPDATE pulse_procedures SET active = true WHERE code = ANY(:c)"), {"c": list(codes)})
    db.commit()


def _queue(db, user, code: str, *, dry_run: bool = True, **inputs) -> PulseProcedureRun:
    procedure = db.scalar(select(PulseProcedure).where(PulseProcedure.code == code))
    run = PulseProcedureRun(user_id=user.id, procedure_id=procedure.id, procedure_version=1, inputs=inputs,
                            dry_run=dry_run, status="queued", steps_log=[], created_at=AT)
    db.add(run)
    db.commit()
    return run


def _menu(db, user, workout, now) -> dict:
    return {move["code"]: move for move in procedures.legal_menu(db, user=user, workout=workout, now=now)}


def test_seeds(db) -> None:
    rows = db.scalars(select(PulseProcedure).order_by(PulseProcedure.code)).all()
    assert [row.code for row in rows] == list(CODES) and not any(row.active for row in rows)
    p1 = next(row for row in rows if row.code == "adapt_training_session")
    assert [step["type"] for step in p1.steps] == ["code", "code", "llm_slot", "code", "user_gate", "code"]
    slots = {row.slot_code: row.tier for row in db.scalars(select(AISlotTransition).where(
        AISlotTransition.domain == "pulse"))}
    assert len(slots) == 17 and slots["pulse.p1.choose_move"] == "local_default"  # + diète (0131), analyses (0132)
    assert (slots["pulse.p2.synthesis"], slots["pulse.p3.design"]) == ("routed", "cloud_forced")
    job = db.execute(text("SELECT enabled FROM job_definitions WHERE code = 'pulse.procedure_runner'")).scalar()
    assert job is False and procedures.proposals_enabled(db) is False


def test_dry_run_chain_from_pre_session_to_hidden_proposal(db) -> None:
    db.execute(text("UPDATE pulse_sentinel_rules SET active = true WHERE code = 'S6_pre_session'"))
    _activate(db, "adapt_training_session")
    user = _user(db)
    workout = _workout(db, user, AT + timedelta(hours=2))  # 09:30 à Paris
    assert sentinel.tick(db, current_user=user, now=AT).queued == 1
    sentinel.run_dispatches(db, now=AT)
    dispatch = db.scalar(select(PulseDispatchLog).where(PulseDispatchLog.user_id == user.id))
    assert (dispatch.outcome, dispatch.procedures_named, dispatch.valid) == (
        "procedures_run", ["adapt_training_session"], True)
    stats = procedures.run_queued(db, now=AT)
    db.commit()
    assert (stats.processed, stats.completed) == (1, 1)
    run = db.scalar(select(PulseProcedureRun).where(PulseProcedureRun.user_id == user.id))
    assert run.status == "completed" and run.dry_run is True and run.dispatch_id == dispatch.id
    assert [step["ref"] for step in run.steps_log] == [
        "p1.load", "p1.legal_menu", "pulse.p1.choose_move", "p1.validate", "p1.proposal", "p1.apply"]
    assert run.steps_log[2]["model_used"] == "dry_run" and run.steps_log[5]["status"] == "skipped"
    proposal = db.scalar(select(PulseProposal).where(PulseProposal.procedure_run_id == run.id))
    assert proposal.dry_run is True and proposal.presented_at is None and proposal.applied is False
    assert proposal.payload["move_code"] == "shift_time" and proposal.payload["parameters"] == {"new_time": "08:00"}
    assert proposal.summary_fr == "Décaler la séance « Séance jambes » à 08:00 le même jour."
    db.refresh(workout)
    assert workout.planned_at == AT + timedelta(hours=2) and workout.version == 1  # rien d'appliqué
    events = {e.event_type: e for e in db.scalars(select(Event).where(Event.user_id == user.id))}
    triggered, completed = events["pulse.sentinel.triggered"], events["pulse.dispatch.completed"]
    started, done = events["pulse.procedure.started"], events["pulse.procedure.completed"]
    assert started.causation_id == completed.event_id and done.causation_id == started.event_id
    assert {completed.correlation_id, started.correlation_id, done.correlation_id} == {triggered.correlation_id}
    assert done.depth == triggered.depth + 3 and done.payload["status"] == "completed"
    assert "pulse.proposal.presented" not in events
    set_parameter(db, code="pulse.proposals_enabled", value=True, origin="user", rationale_fr="Test.")
    db.commit()
    assert procedures.list_pending(db, current_user=user).items == []


def test_legal_menu_gates(db, monkeypatch) -> None:
    user = _user(db)
    day = date(2026, 10, 22)
    workout = _workout(db, user, _paris(day, 18), intensity="high")
    now = _paris(day, 7)
    db.add(ImperiumCalendarEvent(user_id=user.id, event_type="event", title="RDV", starts_at=_paris(day, 9),
                                 ends_at=_paris(day, 20, 30), blocks_time=True))
    _workout(db, user, _paris(day + timedelta(days=1), 18))  # jour J+1 déjà pris
    _workout(db, user, _paris(day + timedelta(days=3), 7), intensity="high")  # J+2 et J+4 voisins d'un jour high
    db.commit()
    menu = _menu(db, user, workout, now)
    assert menu["shift_time"]["options"] == ["07:30", "08:00", "20:30", "21:00"]  # RDV de 09:00 à 20:30
    assert menu["reschedule"]["options"] == [(day + timedelta(days=n)).isoformat() for n in (5, 6)]
    assert all(not menu[code]["legal"] and menu[code]["reasons"] == ["no_program"] for code in procedures.PROGRAM_MOVES)
    monkeypatch.setattr(procedures.fasting, "window_fast",
                        lambda db, user, at: SimpleNamespace(suhoor_at=_paris(day, 5)) if at.date() == day else None)
    assert _menu(db, user, workout, now)["shift_time"]["options"] == ["07:30", "08:00"]  # jeûne > 12 h dès 17:00
    choice = {"move_code": "reschedule", "parameters": {"target_date": day.isoformat()}}
    assert procedures.validate_choice(choice, procedures.legal_menu(db, user=user, workout=workout, now=now)) == [
        "reschedule:target_date"]
    assert procedures.validate_choice({"move_code": "deload_week"}, list(_menu(db, user, workout, now).values())) == [
        "illegal_move:deload_week"]


def test_runner_aborts_and_guards(db, monkeypatch) -> None:
    user = _user(db)
    workout = _workout(db, user, AT + timedelta(hours=2))
    pain = _queue(db, user, "injury_or_pain")
    gone = _queue(db, user, "adapt_training_session", workout_id=str(uuid4()))
    monkeypatch.setattr(procedures, "get_settings", lambda: SimpleNamespace(real_ai_enabled=True))
    with pytest.raises(procedures.RealSlotNotCodedError):
        procedures.run_queued(db, now=AT)
    monkeypatch.undo()
    rule_id = db.scalar(select(PulseRedFlagRule.id).where(PulseRedFlagRule.code == "RF_severe_pain"))
    db.add(PulseRedFlagEvent(user_id=user.id, rule_id=rule_id, subject_ref="pain:x", severity="urgent", raised_at=AT,
                             evidence={}))
    blocked = _queue(db, user, "adapt_training_session", workout_id=str(workout.id))
    stats = procedures.run_queued(db, now=AT)
    db.commit()
    assert stats.aborted == 3
    assert [db.get(PulseProcedureRun, run.id).result["reason"] for run in (pain, gone, blocked)] == [
        "not_coded", "session_unavailable", "red_flag_block"]
    assert db.scalar(select(PulseProposal).where(PulseProposal.user_id == user.id)) is None


def _presented(db, user, workout) -> PulseProposal:
    run = _queue(db, user, "adapt_training_session", dry_run=False, workout_id=str(workout.id))
    procedures.run_queued(db, now=datetime.now(UTC))
    db.commit()
    assert db.get(PulseProcedureRun, run.id).status == "waiting_user"
    return db.scalar(select(PulseProposal).where(PulseProposal.procedure_run_id == run.id))


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_pulse_signals.router, prefix=P)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def test_decisions_apply_only_after_acceptance(db) -> None:
    user = _user(db)
    client = _client(db, user)
    day = datetime.now(UTC).astimezone(PARIS).date() + timedelta(days=2)
    workout = _workout(db, user, _paris(day, 10))
    proposal = _presented(db, user, workout)
    assert client.get(f"{P}/proposals").json()["code"] == "PULSE_PROPOSALS_DISABLED"
    set_parameter(db, code="pulse.proposals_enabled", value=True, origin="user", rationale_fr="Test.")
    db.commit()
    [item] = client.get(f"{P}/proposals").json()["items"]
    assert item["id"] == str(proposal.id) and item["payload"]["parameters"] == {"new_time": "06:00"}
    decide = f"{P}/proposals/{proposal.id}/decision"
    assert client.post(decide, json={"decision": "refused"}).status_code == 409  # explication obligatoire
    assert client.post(decide, json={"decision": "modified"}).status_code == 422
    modified = client.post(decide, json={"decision": "modified", "user_explanation": "Plutôt demain",
                                         "modified_payload": {"move_code": "reschedule",
                                                              "parameters": {"target_date": (day + timedelta(days=1)).isoformat()}}})
    assert modified.status_code == 200, modified.text
    assert (modified.json()["decision"], modified.json()["applied"]) == ("modified", True)
    db.refresh(workout)
    assert workout.planned_at == _paris(day + timedelta(days=1), 10) and workout.version == 2
    assert client.post(decide, json={"decision": "accepted"}).status_code == 409  # déjà décidée
    decided = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "pulse.proposal.decided"))
    assert decided.payload == {"proposal_id": str(proposal.id), "kind": "session_adaptation", "decision": "modified",
                               "has_explanation": True}

    other = _workout(db, user, _paris(day + timedelta(days=3), 10))
    refused_proposal = _presented(db, user, other)
    refused = client.post(f"{P}/proposals/{refused_proposal.id}/decision",
                          json={"decision": "refused", "user_explanation": "Je préfère garder l'heure"})
    assert refused.json()["applied"] is False
    db.refresh(other)
    assert other.version == 1

    stale_workout = _workout(db, user, _paris(day + timedelta(days=4), 10))
    stale = _presented(db, user, stale_workout)
    stale_workout.version = 2  # la séance a changé depuis la proposition
    db.commit()
    response = client.post(f"{P}/proposals/{stale.id}/decision", json={"decision": "accepted"})
    assert response.status_code == 409 and response.json()["detail"]["code"] == "PROPOSAL_STALE"
    db.refresh(stale)
    assert (stale.decision, stale.applied) == ("expired", False)
    stranger = _client(db, _user(db))
    assert stranger.post(f"{P}/proposals/{refused_proposal.id}/decision",
                         json={"decision": "accepted"}).status_code == 404


def test_runner_job(db) -> None:
    job = db.execute(text("SELECT * FROM job_definitions WHERE code = 'pulse.procedure_runner'")).one()
    ctx = RunContext(db=db, job=job, run_id=uuid4(), trigger="cron", trigger_ref=None)
    procedures.runner_job(ctx, Window(from_ts=AT - timedelta(minutes=5), to_ts=AT))
    assert ctx.detail["model_used"] == "dry_run"
