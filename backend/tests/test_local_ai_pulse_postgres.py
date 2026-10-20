"""PostgreSQL : slots IA locaux de la chaîne Pulse (interprète, choix du coup de P1), modes shadow et live,
garde-fous (bouclage, tier local, liste blanche), nouvel essai et repli. Exécuteur simulé."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("local AI Pulse DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models.auth import User  # noqa: E402
from app.models.imperium import PulseWorkout  # noqa: E402
from app.models.pulse import PulseDispatchLog, PulseProcedureRun, PulseProposal  # noqa: E402
from app.services.ai import local_executor  # noqa: E402
from app.services.params import set_parameter  # noqa: E402
from app.services.pulse import ai_slots, procedures, sentinel  # noqa: E402

AT = datetime(2026, 10, 21, 5, 30, tzinfo=UTC)  # 07:30 à Paris
LOOPBACK = "http://127.0.0.1:8081"


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


class FakeExecutor:
    """Répond par slot (nom du schéma) depuis des files de sorties ; garde chaque requête."""

    def __init__(self) -> None:
        self.outputs: dict[str, list] = {"pulse_interpreter": [], "pulse_p1_choose_move": []}
        self.requests: list[dict] = []
        self.logged: list[dict] = []

    def post(self, url: str, payload: dict, timeout: int) -> dict:
        assert url == LOOPBACK + "/v1/chat/completions"
        self.requests.append(payload)
        item = self.outputs[payload["response_format"]["json_schema"]["name"]].pop(0)
        if isinstance(item, Exception):
            raise item
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(item)}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20}}


@pytest.fixture()
def fake(monkeypatch) -> FakeExecutor:
    executor = FakeExecutor()
    monkeypatch.setattr(local_executor, "_http_post", executor.post)
    monkeypatch.setattr(local_executor, "get_settings",
                        lambda: SimpleNamespace(local_executor_url=LOOPBACK, local_executor_timeout_seconds=5))
    monkeypatch.setattr(local_executor.call_log, "record", lambda **row: executor.logged.append(row))
    return executor


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"lai-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _modes(db, **modes) -> None:
    set_parameter(db, code="ai.local_slot_modes", value={k.replace("__", "."): v for k, v in modes.items()},
                  origin="user", rationale_fr="Test.")
    db.commit()


def _interpretation(**extra) -> dict:
    return {"procedures": [], "signals_used": [], "confidence": "high", "escalate": False, "none_needed": True,
            "rationale_fr": "Rien à faire.", **extra}


def _move(code: str = "maintain", **parameters) -> dict:
    return {"move_code": code, "parameters": parameters, "fallback_move_code": None, "condition_fr": None,
            "rationale_fr": "Séance tenable.", "confidence": "high"}


def _wake(db, user) -> PulseWorkout:
    """Réveil S6 sur une séance à 09:30 (Paris) avec P1 active ; un réveil en file."""
    db.execute(text("UPDATE pulse_sentinel_rules SET active = true WHERE code = 'S6_pre_session'"))
    db.execute(text("UPDATE pulse_procedures SET active = true WHERE code = 'adapt_training_session'"))
    workout = PulseWorkout(user_id=user.id, title="Séance jambes privée", status="planned",
                           planned_at=AT + timedelta(hours=2), duration_minutes=60, idempotency_key=str(uuid4()),
                           request_hash="h")
    db.add(workout)
    db.commit()
    assert sentinel.tick(db, current_user=user, now=AT).queued == 1
    return workout


def _dispatch(db, user) -> PulseDispatchLog:
    return db.scalar(select(PulseDispatchLog).where(PulseDispatchLog.user_id == user.id))


def test_guards(db, fake, monkeypatch) -> None:
    assert local_executor.slot_mode(db, "pulse.interpreter") == "off"  # semé vide
    _modes(db, pulse__interpreter="shadow", pulse__p3__design="live", pulse__p1__choose_move="bof")
    assert local_executor.slot_mode(db, "pulse.interpreter") == "shadow"
    assert local_executor.slot_mode(db, "pulse.p3.design") == "off"  # slot cloud : jamais servi en local
    assert local_executor.slot_mode(db, "pulse.p1.choose_move") == "off"
    monkeypatch.setattr(local_executor, "get_settings",
                        lambda: SimpleNamespace(local_executor_url="http://10.0.0.5:8081", local_executor_timeout_seconds=5))
    assert local_executor.slot_mode(db, "pulse.interpreter") == "off"  # rien ne quitte la machine
    with pytest.raises(local_executor.LocalExecutorError):
        local_executor.structured(slot_code="pulse.interpreter", app_name="pulse", system="s", user="u", schema={})
    assert fake.requests == []
    with pytest.raises(ai_slots.AssemblerError):
        ai_slots.assemble(board="x", device_samples="brut")
    assert len(ai_slots.assemble(board="x" * 20000)) == ai_slots.MAX_INPUT_CHARS


def test_interpreter_shadow_keeps_the_dry_run_outcome(db, fake) -> None:
    _modes(db, pulse__interpreter="shadow")
    user = _user(db)
    _wake(db, user)
    fake.outputs["pulse_interpreter"].append(_interpretation())
    sentinel.run_dispatches(db, now=AT)
    dispatch = _dispatch(db, user)
    assert (dispatch.outcome, dispatch.model_used, dispatch.procedures_named) == (
        "procedures_run", "dry_run", ["adapt_training_session"])
    local = dispatch.output["local"]
    assert (local["mode"], local["valid"], local["attempts"], local["output"]["none_needed"]) == ("shadow", True, 1, True)
    request = fake.requests[0]
    assert request["temperature"] == 0 and request["chat_template_kwargs"] == {"enable_thinking": False}
    schema = request["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["procedures"]["items"]["properties"]["code"]["enum"] == ["adapt_training_session"]
    prompt = request["messages"][1]["content"]
    assert "adapt_training_session" in prompt and "séance imminente" in prompt
    assert "Séance jambes privée" not in prompt  # aucun texte libre saisi
    assert fake.logged[0]["task_type"] == "pulse.interpreter" and fake.logged[0]["model_tier"] == "local"


def test_interpreter_live_retry_fallback_and_escalation(db, fake) -> None:
    _modes(db, pulse__interpreter="live")
    user = _user(db)
    _wake(db, user)
    bad = _interpretation(procedures=[{"code": "inconnue", "urgency": "today"}], none_needed=False)
    fake.outputs["pulse_interpreter"] += [bad, _interpretation(
        procedures=[{"code": "adapt_training_session", "urgency": "today"}], none_needed=False)]
    sentinel.run_dispatches(db, now=AT)
    dispatch = _dispatch(db, user)
    assert (dispatch.outcome, dispatch.model_used, dispatch.valid) == ("procedures_run", "local_executor", True)
    assert dispatch.output["local"]["attempts"] == 2 and dispatch.prompt_tokens == 200
    assert "rappel" in fake.requests[1]["messages"][1]["content"]
    run = db.scalar(select(PulseProcedureRun).where(PulseProcedureRun.user_id == user.id))
    assert run.inputs["workout_id"] and run.dry_run is True  # choix du coup pas en live : rien de présenté

    for outputs, outcome in (([bad, bad], "invalid_fallback"),
                             ([local_executor.LocalExecutorError("down")], "invalid_fallback"),
                             ([_interpretation(escalate=True, none_needed=False)], "escalated"),
                             ([_interpretation(confidence="low")], "escalated")):
        other = _user(db)
        _wake(db, other)
        fake.outputs["pulse_interpreter"] += outputs
        sentinel.run_dispatches(db, now=AT)
        assert _dispatch(db, other).outcome == outcome
        assert db.scalar(select(PulseProcedureRun).where(PulseProcedureRun.user_id == other.id)) is None


def test_choose_move_shadow_then_live(db, fake) -> None:
    _modes(db, pulse__p1__choose_move="shadow")
    user = _user(db)
    _wake(db, user)
    sentinel.run_dispatches(db, now=AT)
    fake.outputs["pulse_p1_choose_move"].append(_move())
    procedures.run_queued(db, now=AT)
    run = db.scalar(select(PulseProcedureRun).where(PulseProcedureRun.user_id == user.id))
    step = run.steps_log[2]
    assert (step["model_used"], step["local"]["mode"], step["local"]["output"]["move_code"]) == (
        "dry_run", "shadow", "maintain")
    proposal = db.scalar(select(PulseProposal).where(PulseProposal.procedure_run_id == run.id))
    assert proposal.dry_run is True and proposal.payload["move_code"] == "shift_time"  # le factice sert encore
    prompt = fake.requests[0]["messages"][1]["content"]
    assert "shift_time — options" in prompt and "Séance jambes privée" not in prompt

    _modes(db, pulse__p1__choose_move="live")
    other = _user(db)
    _wake(db, other)
    sentinel.run_dispatches(db, now=AT)
    fake.outputs["pulse_p1_choose_move"].append(_move("reschedule", target_date="2026-10-22", new_time="99:99"))
    procedures.run_queued(db, now=AT)
    db.commit()
    run = db.scalar(select(PulseProcedureRun).where(PulseProcedureRun.user_id == other.id))
    proposal = db.scalar(select(PulseProposal).where(PulseProposal.procedure_run_id == run.id))
    assert run.status == "waiting_user" and proposal.dry_run is False and proposal.presented_at is not None
    assert proposal.payload["move_code"] == "reschedule" and proposal.payload["parameters"] == {"target_date": "2026-10-22"}
    assert proposal.payload["rationale_fr"] == "Séance tenable." and run.steps_log[2]["model_used"] == "local_executor"

    third = _user(db)
    _wake(db, third)
    sentinel.run_dispatches(db, now=AT)
    fake.outputs["pulse_p1_choose_move"] += [_move("deload_week", percent=50), _move("shift_time", new_time="03:00")]
    procedures.run_queued(db, now=AT)
    run = db.scalar(select(PulseProcedureRun).where(PulseProcedureRun.user_id == third.id))
    proposal = db.scalar(select(PulseProposal).where(PulseProposal.procedure_run_id == run.id))
    assert run.steps_log[2]["status"] == "fallback" and proposal.payload["move_code"] == "maintain"
    assert proposal.payload["rationale_fr"].startswith("Repli")
