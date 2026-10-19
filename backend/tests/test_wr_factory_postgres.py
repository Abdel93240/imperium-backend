"""PostgreSQL : usine du WR — ordre des workers, curseurs, échec, déclencheurs (spec WR §3.2, §4, §14.2)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("wr factory DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, delete, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models import ai  # noqa: E402,F401 - FK de la session WR vers ai_tasks
from app.models.auth import User  # noqa: E402
from app.models.enums import PrivacyLevel, SourceApp  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.toolbox import JobDefinition  # noqa: E402
from app.models.wr import WrWorkerCursor, WrWorkerRun  # noqa: E402
from app.services.events.emitter import build_event  # noqa: E402
from app.services.runner.engine import RunContext, Window  # noqa: E402
from app.services.wr import docket, factory, metrics  # noqa: E402
from app.services.wr.factory import WorkerOutcome  # noqa: E402

NOW = datetime(2026, 10, 14, 16, 0, tzinfo=UTC)  # mercredi, 18:00 à Paris (heure d'été)


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


def _cleanup(session: Session) -> None:
    session.execute(delete(WrWorkerRun))
    session.execute(delete(WrWorkerCursor))
    session.commit()


@pytest.fixture()
def db(engine):
    with Session(engine) as session:
        _cleanup(session)
        yield session
        session.rollback()
        _cleanup(session)


@pytest.fixture(autouse=True)
def all_workers_enabled(monkeypatch):
    real = factory.get_parameter

    def fake(db, code, default=None):
        return list(factory.WORKER_ORDER) if code == "wr.factory_workers_enabled" else real(db, code, default=default)

    monkeypatch.setattr(factory, "get_parameter", fake)


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"factory-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _fake_workers(monkeypatch, calls: list, *, failing: str | None = None) -> None:
    def make(name):
        def worker(_db, _user, window_from, window_to):
            calls.append((name, window_from, window_to))
            if name == failing:
                raise ValueError("boom")
            return WorkerOutcome(items_in=1, items_out=1)
        return worker

    monkeypatch.setattr(factory, "WORKERS", {
        "w1_rollups": make("w1_rollups"), "w4_anomalies": make("w4_anomalies"), "w2_causal": None,
        "w3_learning": make("w3_learning"), "w5_docket": make("w5_docket"),
    })


def _cursor(db, worker: str):
    db.expire_all()
    cursor = db.get(WrWorkerCursor, worker)
    return cursor.last_processed_event_ts if cursor else None


def test_jobs_are_seeded_disabled(db) -> None:
    jobs = {job.code: job for job in db.scalars(select(JobDefinition).where(JobDefinition.code.like("wr.factory%")))}
    assert set(jobs) == {"wr.factory_on_session_end", "wr.factory_fallback"}
    assert not any(job.enabled for job in jobs.values())
    assert jobs["wr.factory_on_session_end"].event_types == ["rides.session.ended"]
    assert jobs["wr.factory_fallback"].schedule == "30 21,22 * * *"


def test_workers_run_in_order_and_cursors_leave_no_hole(db, monkeypatch) -> None:
    user = _user(db)
    calls: list = []
    _fake_workers(monkeypatch, calls)
    summary = factory.run_factory(db, user=user, trigger="manual", now=NOW)
    db.commit()
    assert [name for name, *_ in calls] == ["w1_rollups", "w4_anomalies", "w3_learning", "w5_docket"]
    assert summary == {"completed": ["w1_rollups", "w4_anomalies", "w3_learning", "w5_docket"],
                       "not_coded": ["w2_causal"], "disabled": [], "failed": None}
    day_start = datetime(2026, 10, 13, 22, 0, tzinfo=UTC)  # minuit à Paris
    assert all(window_from == day_start for _, window_from, _ in calls)
    assert _cursor(db, "w5_docket") == NOW and _cursor(db, "w2_causal") is None

    calls.clear()
    later = NOW + timedelta(hours=2)
    factory.run_factory(db, user=user, trigger="manual", now=later)
    db.commit()
    assert all((window_from, window_to) == (NOW, later) for _, window_from, window_to in calls)  # ]NOW, later]
    events = db.scalars(select(Event).where(Event.user_id == user.id,
                                            Event.event_type == "planning.factory.run_completed")).all()
    assert len(events) == 8 and {event.payload["status"] for event in events} == {"completed"}


def test_failed_worker_keeps_its_cursor_and_stops_the_chain(db, monkeypatch) -> None:
    user = _user(db)
    calls: list = []
    _fake_workers(monkeypatch, calls)
    factory.run_factory(db, user=user, trigger="manual", now=NOW)
    db.commit()
    calls.clear()
    _fake_workers(monkeypatch, calls, failing="w4_anomalies")
    later = NOW + timedelta(hours=1)
    summary = factory.run_factory(db, user=user, trigger="manual", now=later)
    db.commit()
    assert [name for name, *_ in calls] == ["w1_rollups", "w4_anomalies"]
    assert summary["failed"] == "w4_anomalies"
    assert (_cursor(db, "w1_rollups"), _cursor(db, "w4_anomalies"), _cursor(db, "w5_docket")) == (later, NOW, NOW)
    failed = db.scalar(select(WrWorkerRun).where(WrWorkerRun.status == "failed"))
    assert (failed.worker, failed.detail) == ("w4_anomalies", {"error": "ValueError"})
    calls.clear()
    _fake_workers(monkeypatch, calls)
    factory.run_factory(db, user=user, trigger="manual", now=later + timedelta(hours=1))
    db.commit()
    w4 = next(call for call in calls if call[0] == "w4_anomalies")
    assert w4[1] == NOW  # le lot échoué est repris


def test_w5_reprioritizes_open_docket_items(db) -> None:
    user = _user(db)
    item = docket.create_item(db, current_user=user, item_type="anomaly", domain="vault", title_fr="Écart",
                              payload={}, evidence_refs={}, impact_estimate=4, source_worker="w4",
                              now=NOW - timedelta(days=14))
    db.commit()
    before = float(item.priority)
    summary = factory.run_factory(db, user=user, trigger="manual", now=NOW)
    db.commit()
    db.refresh(item)
    assert "w5_docket" in summary["completed"] and float(item.priority) == pytest.approx(before / 2.718281828, rel=1e-3)
    run = db.scalar(select(WrWorkerRun).where(WrWorkerRun.worker == "w5_docket"))
    assert run.items_out >= 1 and run.llm_calls == 0


def test_triggers_fallback_and_session_end(db, monkeypatch) -> None:
    user = _user(db)
    monkeypatch.setattr(factory, "_job_user", lambda _db: user)
    _fake_workers(monkeypatch, [])

    def ctx(trigger="cron", trigger_ref=None):
        return RunContext(db=db, job=None, run_id=uuid4(), trigger=trigger, trigger_ref=trigger_ref)

    at_22 = datetime(2026, 10, 14, 20, 30, tzinfo=UTC)  # 22:30 à Paris
    off_hour = ctx()
    factory.factory_fallback_job(off_hour, Window(from_ts=None, to_ts=at_22))
    assert off_hour.detail == {"skipped": "not_fallback_hour"}
    at_23 = datetime(2026, 10, 14, 21, 30, tzinfo=UTC)
    first = ctx()
    factory.factory_fallback_job(first, Window(from_ts=None, to_ts=at_23))
    assert first.items_out == 4
    assert {run.trigger for run in db.scalars(select(WrWorkerRun))} == {"fallback_cron"}
    again = ctx()
    factory.factory_fallback_job(again, Window(from_ts=None, to_ts=at_23 + timedelta(minutes=5)))
    assert again.detail == {"skipped": "already_ran_today"}

    session_id = uuid4()
    ended = build_event(db, user_id=user.id, event_type="rides.session.ended", payload={"session_id": str(session_id)},
                        idempotency_key=f"test.rides.session.ended.{session_id}", source_app=SourceApp.imperium,
                        privacy_level=PrivacyLevel.high, occurred_at=at_23 + timedelta(minutes=10))
    db.add(ended)
    db.commit()
    on_end = ctx(trigger="event", trigger_ref=ended.id)
    factory.factory_on_session_end_job(on_end, Window(from_ts=None, to_ts=at_23 + timedelta(minutes=20)))
    runs = db.scalars(select(WrWorkerRun).where(WrWorkerRun.trigger == "session_end")).all()
    assert len(runs) == 4 and {run.session_ref for run in runs} == {session_id}
    caused = db.scalars(select(Event).where(Event.event_type == "planning.factory.run_completed",
                                            Event.causation_id == ended.event_id)).all()
    assert len(caused) == 4
    assert on_end.cursor_ts == at_23 + timedelta(minutes=20)

    week = metrics.compute_week(db, current_user=user, week_start=date(2026, 10, 12), now=at_23 + timedelta(hours=1))
    assert week.factory_runs == 2  # deux passages (fallback, fin de session)


def test_only_enabled_workers_run(db, monkeypatch) -> None:
    user = _user(db)
    calls: list = []
    _fake_workers(monkeypatch, calls)
    monkeypatch.setattr(factory, "get_parameter", lambda _db, code, default=None: ["w5_docket"])
    summary = factory.run_factory(db, user=user, trigger="manual", now=NOW)
    db.commit()
    assert [name for name, *_ in calls] == ["w5_docket"]
    assert summary["disabled"] == ["w1_rollups", "w4_anomalies", "w3_learning"]
    assert _cursor(db, "w1_rollups") is None and _cursor(db, "w5_docket") == NOW
    # Valeur semée : aucun worker.
    monkeypatch.setattr(factory, "get_parameter", _seeded_get_parameter)
    assert factory.run_factory(db, user=user, trigger="manual", now=NOW + timedelta(hours=1))["completed"] == []


def _seeded_get_parameter(db, code, default=None):
    from app.services.params import get_parameter

    return get_parameter(db, code, default=default)
