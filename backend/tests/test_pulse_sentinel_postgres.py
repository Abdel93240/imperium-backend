"""PostgreSQL : sentinelle Pulse S1-S7, boards figés et runner de dispatch en essai à blanc (spec Pulse
§3.2, §5, §6 ; ACT-PLS-10, ACT-PLS-11, ACT-PLS-12, ACT-PLS-13, ACT-PLS-14, ACT-PLS-15)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("pulse sentinel DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, func, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_pulse_health, imperium_pulse_signals  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.imperium import PulseWorkout  # noqa: E402
from app.models.pulse import PulseBoardSnapshot, PulseDispatchLog, PulseSentinelRule, PulseSubjectiveReport  # noqa: E402
from app.models.toolbox import Notification  # noqa: E402
from app.schemas.pulse_signals import BoardRead, BoardSignalRead  # noqa: E402
from app.services.params import set_parameter  # noqa: E402
from app.services.pulse import sentinel, signals  # noqa: E402
from app.services.runner.engine import RunContext, Window  # noqa: E402

P = "/api/imperium/pulse"
AT = datetime(2026, 10, 21, 5, 30, tzinfo=UTC)  # 07:30 à Paris (heure d'été jusqu'au 25 octobre)
RULES = ("S1_multi_flags", "S2_severe_signal", "S3_user_report", "S4_scheduled_am", "S5_scheduled_pm",
         "S6_pre_session", "S7_meta_guard")


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    # Les routes committent : transaction externe annulée, rien ne fuit (règles réactivées comprises).
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
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"psen-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _turn_on(db, *rules: str) -> None:
    db.execute(text("UPDATE pulse_sentinel_rules SET active = true WHERE code = ANY(:codes)"), {"codes": list(rules)})
    db.execute(text("UPDATE signal_definitions SET active = true WHERE code LIKE 'pulse.%'"))
    for code in ("board_enabled", "reports_enabled"):
        set_parameter(db, code=f"pulse.{code}", value=True, origin="user", rationale_fr="Test.")
    db.commit()


def _rule(db, code: str) -> PulseSentinelRule:
    return db.scalar(select(PulseSentinelRule).where(PulseSentinelRule.code == code))


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_pulse_signals.router, prefix=P)
    app.include_router(imperium_pulse_health.router, prefix=P)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _report(client, kind: str, level: int):
    response = client.post(f"{P}/reports", json={"kind": kind, "level": level}, headers={"Idempotency-Key": str(uuid4())})
    assert response.status_code == 201, response.text
    return response.json()


def _dispatches(db, user) -> list[PulseDispatchLog]:
    return list(db.scalars(select(PulseDispatchLog).where(PulseDispatchLog.user_id == user.id)
                           .order_by(PulseDispatchLog.created_at)))


def _board(**bands: str) -> BoardRead:
    rows = [BoardSignalRead(code=f"pulse.{code}", label_fr=None, unit=None, state="fresh", value=1.0, band=band,
                            flag=band != "green") for code, band in bands.items()]
    return BoardRead(generated_at=AT, red_flags=[], signals=rows, flags_count=sum(r.flag for r in rows), max_band="green")


def test_pure_rules() -> None:
    config = {"cron": "30 7 * * *", "timezone": "Europe/Paris", "grace_minutes": 60}
    assert sentinel.scheduled_due(config, AT) == "2026-10-21"
    assert sentinel.scheduled_due(config, AT + timedelta(minutes=59)) == "2026-10-21"
    assert sentinel.scheduled_due(config, AT + timedelta(minutes=60)) is None
    assert sentinel.scheduled_due(config, AT - timedelta(minutes=1)) is None
    assert sentinel.same_flags({"a": "yellow"}, {"a": "orange"}) is True
    assert sentinel.same_flags({"a": "red"}, {"a": "orange"}) is False  # montée de bande
    assert sentinel.same_flags({"a": "yellow", "b": "yellow"}, {"a": "yellow"}) is False
    good = sentinel.dry_run_output({"pulse.x": "orange"})
    assert sentinel.validate_output(good, catalogue=set()) == []
    named = {**good, "procedures": [{"code": "adapt_training_session", "urgency": "today"}]}
    assert sentinel.validate_output(named, catalogue=set()) == ["procedures:unknown_code:adapt_training_session"]
    assert sentinel.validate_output(named, catalogue={"adapt_training_session"}) == []
    assert sentinel.validate_output({**good, "rationale_fr": "x" * 401}, catalogue=set()) == ["rationale_fr"]
    assert sentinel.validate_output({"procedures": []}, catalogue=set())[0] == "missing:signals_used"


def test_seeded_off(db) -> None:
    rows = db.execute(text("SELECT code, active FROM pulse_sentinel_rules ORDER BY code")).all()
    assert [row.code for row in rows] == list(RULES) and not any(row.active for row in rows)
    jobs = db.execute(text("SELECT code, enabled FROM job_definitions WHERE code IN "
                           "('pulse.sentinel_tick', 'pulse.dispatch_runner')")).all()
    assert len(jobs) == 2 and not any(job.enabled for job in jobs)
    _turn_on(db)  # signaux et routes allumés, aucune règle
    user = _user(db)
    _report(_client(db, user), "fatigue", 5)
    assert _dispatches(db, user) == []
    assert sentinel.tick(db, current_user=user).rules == 0


def test_user_report_wakes_once_with_causation_and_dedup(db) -> None:
    _turn_on(db, "S3_user_report", "S7_meta_guard")
    user = _user(db)
    client = _client(db, user)
    _report(client, "fatigue", 2)
    assert _dispatches(db, user) == []  # vert : sous le seuil
    report = _report(client, "fatigue", 4)
    [dispatch] = _dispatches(db, user)
    assert (dispatch.triggered_by, dispatch.subject_ref, dispatch.status) == (
        "S3_user_report", f"report:{report['id']}", "queued")
    assert dispatch.flag_set == {"pulse.fatigue_reported": "orange"}
    snapshot = db.get(PulseBoardSnapshot, dispatch.board_snapshot_id)
    assert (snapshot.reason, snapshot.flags_count, snapshot.max_severity) == ("S3_user_report", 1, "orange")
    assert all("detail" not in signal for signal in snapshot.board["signals"])
    logged = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "pulse.report.logged",
                                           Event.payload["report_id"].astext == report["id"]))
    triggered = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "pulse.sentinel.triggered"))
    assert triggered.causation_id == logged.event_id and triggered.depth == logged.depth + 1
    assert triggered.payload == {"rule_code": "S3_user_report", "snapshot_id": str(snapshot.id), "flags_count": 1,
                                 "dispatch_id": str(dispatch.id)}
    _report(client, "fatigue", 4)  # mêmes drapeaux dans la fenêtre : dédup S7
    assert len(_dispatches(db, user)) == 1
    _report(client, "stress", 5)  # nouveau drapeau
    assert len(_dispatches(db, user)) == 2


def test_dispatch_runner_is_a_dry_run_that_proposes_nothing(db, monkeypatch) -> None:
    _turn_on(db, "S3_user_report")
    user = _user(db)
    _report(_client(db, user), "mood", 5)
    monkeypatch.setattr(sentinel, "get_settings", lambda: SimpleNamespace(real_ai_enabled=True))
    with pytest.raises(sentinel.RealInterpreterNotCodedError):
        sentinel.run_dispatches(db)
    assert _dispatches(db, user)[0].status == "queued"
    monkeypatch.undo()
    notified = db.scalar(select(func.count()).select_from(Notification))
    assert sentinel.run_dispatches(db) >= 1
    db.commit()
    [dispatch] = _dispatches(db, user)
    assert (dispatch.status, dispatch.model_used, dispatch.outcome, dispatch.valid) == ("done", "dry_run", "dry_run", True)
    assert dispatch.output["dry_run"] is True and dispatch.procedures_named == [] and dispatch.prompt_tokens is None
    completed = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "pulse.dispatch.completed"))
    assert completed.causation_id == dispatch.trigger_event_id and completed.payload["outcome"] == "dry_run"
    assert db.scalar(select(func.count()).select_from(Notification)) == notified  # rien n'est proposé ni notifié


def test_scheduled_pass_skips_for_free_when_green_and_runs_once_a_day(db) -> None:
    _turn_on(db, "S4_scheduled_am", "S5_scheduled_pm")
    user = _user(db)
    stats = sentinel.tick(db, current_user=user, now=AT)
    [skip] = _dispatches(db, user)
    assert stats.skipped_green == 1 and stats.queued == 0
    assert (skip.subject_ref, skip.status, skip.model_used, skip.outcome) == ("2026-10-21", "done", "skipped",
                                                                               "none_needed")
    assert db.get(PulseBoardSnapshot, skip.board_snapshot_id).max_severity == "green"
    assert sentinel.tick(db, current_user=user, now=AT + timedelta(minutes=15)).held == {"already": 1}
    assert sentinel.tick(db, current_user=user, now=AT + timedelta(hours=3)).rules == 2  # rien de dû
    assert len(_dispatches(db, user)) == 1
    evening = datetime(2026, 10, 21, 16, 40, tzinfo=UTC)  # 18:40 à Paris
    db.add(PulseSubjectiveReport(user_id=user.id, kind="stress", level=4, reported_at=evening - timedelta(minutes=5),
                                 idempotency_key=str(uuid4()), request_hash="h"))
    signals.refresh(db, current_user=user, now=evening)
    assert sentinel.tick(db, current_user=user, now=evening).queued == 1
    assert _dispatches(db, user)[-1].triggered_by == "S5_scheduled_pm"


def test_cooldown_daily_cap_and_dedup(db) -> None:
    _turn_on(db, "S2_severe_signal")
    db.execute(text("UPDATE pulse_sentinel_rules SET config = config || '{\"max_dispatch_per_day\": 3}'::jsonb "
                    "WHERE code = 'S7_meta_guard'"))  # S7 inactive : la garde s'applique quand même
    user = _user(db)
    severe = _rule(db, "S2_severe_signal")

    def wake(minutes: int, **bands):
        return sentinel.wake(db, user=user, rule=severe, now=AT + timedelta(minutes=minutes), board=_board(**bands)).reason

    assert wake(0, a="orange") == "queued"
    assert wake(30, a="red") == "cooldown"  # 60 min
    assert wake(70, a="orange") == "dedup"  # mêmes drapeaux dans les 90 min
    assert wake(71, a="red") == "queued"  # montée de bande
    assert wake(200, a="red") == "queued"  # hors fenêtre de dédup
    assert wake(300, b="orange") == "daily_cap"
    green = sentinel.wake(db, user=user, rule=_rule(db, "S4_scheduled_am"), now=AT + timedelta(minutes=301),
                          subject_ref="2026-10-21", board=_board(a="green"))
    assert green.reason == "all_green"  # une passe gratuite ne compte pas et n'est jamais bloquée
    assert wake(24 * 60, b="orange") == "queued"  # nouveau jour de Paris


def test_tick_flag_rules_and_pre_session(db) -> None:
    _turn_on(db, "S1_multi_flags", "S6_pre_session")
    user = _user(db)
    db.add(PulseSubjectiveReport(user_id=user.id, kind="fatigue", level=3, reported_at=AT - timedelta(minutes=5),
                                 idempotency_key=str(uuid4()), request_hash="h"))
    signals.refresh(db, current_user=user, now=AT)
    assert sentinel.tick(db, current_user=user, now=AT).queued == 0  # un seul drapeau
    db.add(PulseSubjectiveReport(user_id=user.id, kind="mood", level=3, reported_at=AT - timedelta(minutes=4),
                                 idempotency_key=str(uuid4()), request_hash="h"))
    signals.refresh(db, current_user=user, now=AT)
    assert sentinel.tick(db, current_user=user, now=AT).queued == 1
    soon = PulseWorkout(user_id=user.id, title="Séance", status="planned", planned_at=AT + timedelta(hours=2),
                        idempotency_key=str(uuid4()), request_hash="h")
    later = PulseWorkout(user_id=user.id, title="Séance", status="planned", planned_at=AT + timedelta(hours=5),
                         idempotency_key=str(uuid4()), request_hash="h")
    db.add_all([soon, later])
    db.flush()
    now = AT + timedelta(hours=1, minutes=50)  # hors cooldown S1 ; dédup tombée (fenêtre 90 min)
    assert sentinel.tick(db, current_user=user, now=now).queued == 1
    subjects = [d.subject_ref for d in _dispatches(db, user) if d.triggered_by == "S6_pre_session"]
    assert subjects == [f"workout:{soon.id}"]
    assert sentinel.tick(db, current_user=user, now=now + timedelta(minutes=5)).held == {"already": 1}


def test_routes_reaction_and_real_deletion(db) -> None:
    _turn_on(db, "S3_user_report")
    user = _user(db)
    client = _client(db, user)
    _report(client, "stress", 4)
    items = client.get(f"{P}/sentinel/dispatches").json()["items"]
    assert len(items) == 1 and items[0]["status"] == "queued"
    reacted = client.post(f"{P}/sentinel/dispatches/{items[0]['id']}/reaction", json={"reaction": "useless"})
    assert reacted.status_code == 200 and reacted.json()["user_reaction"] == "useless"
    assert client.post(f"{P}/sentinel/dispatches/{items[0]['id']}/reaction", json={"reaction": "bof"}).status_code == 422
    stranger = _client(db, _user(db))
    assert stranger.post(f"{P}/sentinel/dispatches/{items[0]['id']}/reaction",
                         json={"reaction": "useful"}).status_code == 404
    set_parameter(db, code="pulse.board_enabled", value=False, origin="user", rationale_fr="Test.")
    db.commit()
    assert client.get(f"{P}/sentinel/dispatches").json()["code"] == "PULSE_BOARD_DISABLED"
    assert client.delete(f"{P}/sentinel/history").json() == {"deleted": 1}
    assert _dispatches(db, user) == []
    assert db.scalar(select(func.count()).select_from(PulseBoardSnapshot).where(PulseBoardSnapshot.user_id == user.id)) == 0


def test_jobs(db, monkeypatch) -> None:
    _turn_on(db, "S4_scheduled_am")
    user = _user(db)
    monkeypatch.setattr("app.services.wr.metrics._job_user", lambda db: user)
    for code, handler in (("pulse.sentinel_tick", sentinel.tick_job), ("pulse.dispatch_runner", sentinel.dispatch_job)):
        job = db.execute(text("SELECT * FROM job_definitions WHERE code = :c"), {"c": code}).one()
        ctx = RunContext(db=db, job=job, run_id=uuid4(), trigger="cron", trigger_ref=None)
        handler(ctx, Window(from_ts=AT - timedelta(minutes=15), to_ts=AT))
        if code == "pulse.sentinel_tick":
            assert ctx.detail["skipped_green"] == 1 and ctx.items_out == 0
        else:
            assert ctx.detail["model_used"] == "dry_run"
