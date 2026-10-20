"""PostgreSQL : métriques quotidiennes Pulse, slot `pulse.interpreter` et rollup (spec Pulse §3.9, §13, §14 ;
ACT-PLS-27)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("pulse metrics DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_pulse_signals  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.pulse import PulseMetricsDaily, PulseRedFlagEvent, PulseRedFlagRule, PulseSentinelRule  # noqa: E402
from app.models.toolbox import AIAuditSample, AISlotTransition  # noqa: E402
from app.schemas.pulse_signals import BoardRead, BoardSignalRead  # noqa: E402
from app.services.params import set_parameter  # noqa: E402
from app.services.pulse import metrics, sentinel  # noqa: E402
from app.services.runner.engine import RunContext, Window  # noqa: E402

P = "/api/imperium/pulse"
DAY = date(2026, 10, 21)
AT = datetime(2026, 10, 21, 8, 0, tzinfo=UTC)  # 10:00 à Paris


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
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"pmet-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _board(**bands: str) -> BoardRead:
    rows = [BoardSignalRead(code=f"pulse.{code}", label_fr=None, unit=None, state="fresh", value=1.0, band=band,
                            flag=band != "green") for code, band in bands.items()]
    return BoardRead(generated_at=AT, red_flags=[], signals=rows, flags_count=0, max_band="green")


def _rule(db, code: str) -> PulseSentinelRule:
    return db.scalar(select(PulseSentinelRule).where(PulseSentinelRule.code == code))


def _fill_day(db, user) -> None:
    """Deux réveils traités (un annoté utile, un manqué), une passe verte gratuite, un red flag, deux contre-lectures."""
    severe, am = _rule(db, "S2_severe_signal"), _rule(db, "S4_scheduled_am")
    first = sentinel.wake(db, user=user, rule=severe, now=AT, board=_board(a="orange"))
    second = sentinel.wake(db, user=user, rule=severe, now=AT + timedelta(hours=2), board=_board(a="red"))
    sentinel.wake(db, user=user, rule=am, now=AT - timedelta(hours=2), subject_ref=DAY.isoformat(),
                  board=_board(a="green"))
    sentinel.wake(db, user=user, rule=severe, now=AT + timedelta(days=1), board=_board(b="orange"))  # lendemain
    sentinel.run_dispatches(db, now=AT + timedelta(hours=3))
    sentinel.react(db, current_user=user, dispatch_id=first.dispatch_id, reaction="useful")
    sentinel.react(db, current_user=user, dispatch_id=second.dispatch_id, reaction="missed")
    rule_id = db.scalar(select(PulseRedFlagRule.id).where(PulseRedFlagRule.code == "RF_severe_pain"))
    db.add(PulseRedFlagEvent(user_id=user.id, rule_id=rule_id, subject_ref=f"pain:{uuid4()}", severity="urgent",
                             raised_at=AT, evidence={}))
    for agreed in (True, True, False):
        db.add(AIAuditSample(slot_code="pulse.interpreter", run_ref=uuid4(), local_output={}, cloud_output={},
                             cloud_model="cloud-role", agreement=agreed, created_at=AT))
    db.commit()


def test_seeds(db) -> None:
    slot = db.scalar(select(AISlotTransition).where(AISlotTransition.slot_code == "pulse.interpreter"))
    assert (slot.domain, slot.tier, slot.audit_sample_pct, slot.agreement_target_pct) == ("pulse", "local_default", 100, 92)
    job = db.execute(text("SELECT enabled, schedule FROM job_definitions WHERE code = 'pulse.metrics_rollup'")).one()
    assert tuple(job) == (False, "45 0 * * *")


def test_day_counts_match_the_dispatch_log(db) -> None:
    user = _user(db)
    _fill_day(db, user)
    values = metrics.compute_day(db, current_user=user, day=DAY)
    assert {key: values[key] for key in metrics.COUNTS} == {
        "dispatches": 2, "skipped_passes": 1, "dispatches_useful": 1, "dispatches_useless": 0, "missed_reports": 1,
        "escalations": 0, "invalid_fallbacks": 0, "red_flags": 1}
    assert values["agreement_by_slot"] == {"pulse.interpreter": 66.7}
    assert metrics.compute_day(db, current_user=_user(db), day=DAY)["dispatches"] == 0
    empty = metrics.compute_day(db, current_user=user, day=DAY - timedelta(days=1))
    assert empty["agreement_by_slot"] is None and empty["dispatches"] == 0


def test_rollup_job_writes_closed_days_idempotently(db, monkeypatch) -> None:
    user = _user(db)
    _fill_day(db, user)
    monkeypatch.setattr("app.services.wr.metrics._job_user", lambda db: user)
    job = db.execute(text("SELECT * FROM job_definitions WHERE code = 'pulse.metrics_rollup'")).one()
    now = datetime(2026, 10, 22, 22, 45, tzinfo=UTC)  # 00:45 à Paris le 23
    for _ in range(2):
        ctx = RunContext(db=db, job=job, run_id=uuid4(), trigger="cron", trigger_ref=None)
        metrics.rollup_job(ctx, Window(from_ts=now - timedelta(days=1), to_ts=now))
    assert ctx.detail == {"days": ["2026-10-21", "2026-10-22"]}
    rows = db.scalars(select(PulseMetricsDaily).where(PulseMetricsDaily.user_id == user.id)
                      .order_by(PulseMetricsDaily.metric_date)).all()
    assert [(row.metric_date, row.dispatches, row.proposals) for row in rows] == [
        (DAY, 2, None), (DAY + timedelta(days=1), 1, None)]


def test_summary_route(db) -> None:
    user = _user(db)
    app = FastAPI()
    app.include_router(imperium_pulse_signals.router, prefix=P)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    assert client.get(f"{P}/metrics/summary").json()["code"] == "PULSE_BOARD_DISABLED"
    set_parameter(db, code="pulse.board_enabled", value=True, origin="user", rationale_fr="Test.")
    db.commit()
    yesterday = datetime.now(UTC).astimezone(metrics.PARIS).date() - timedelta(days=1)
    metrics.upsert_day(db, current_user=user, day=yesterday, now=datetime.now(UTC))
    db.commit()
    body = client.get(f"{P}/metrics/summary", params={"days": 3}).json()
    assert [day["metric_date"] for day in body["days"]] == [yesterday.isoformat()]
    assert body["today"]["dispatches"] == 0 and body["today"]["proposals"] is None
    slots = {slot["slot_code"]: slot for slot in body["slots"]}
    assert "pulse.interpreter" in slots and not any(slot["decay_proposed"] for slot in slots.values())
    assert client.get(f"{P}/metrics/summary", params={"days": 0}).status_code == 422
