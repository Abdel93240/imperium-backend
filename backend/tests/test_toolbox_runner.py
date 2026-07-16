"""§13.1 runner locks: advisory lock, cursor, dry-run, timeout (spec socle)."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import toolbox_runner_handlers as handlers
from _postgres import require_test_database_url

pytest.importorskip("psycopg")

from app.models.toolbox import JobCursor, JobDefinition, JobRun  # noqa: E402
from app.services.runner.engine import Window, execute_job  # noqa: E402


@pytest.fixture(scope="module")
def engine():
    engine = create_engine(require_test_database_url("toolbox runner tests"), future=True)
    yield engine
    engine.dispose()


@pytest.fixture()
def runner_enabled(monkeypatch):
    from types import SimpleNamespace

    from app.services.runner import engine as engine_module

    monkeypatch.setattr(
        engine_module, "get_settings", lambda: SimpleNamespace(runner_enabled=True)
    )


def _create_job(db: Session, *, handler: str, timeout_s: int = 30, enabled: bool = True) -> str:
    code = f"test.job_{uuid4().hex[:10]}"
    db.add(
        JobDefinition(
            id=uuid4(),
            code=code,
            kind="manual",
            handler_ref=f"toolbox_runner_handlers:{handler}",
            enabled=enabled,
            singleton=True,
            timeout_s=timeout_s,
        )
    )
    db.commit()
    return code


def _runs(db: Session, code: str) -> list[JobRun]:
    return list(
        db.scalars(select(JobRun).where(JobRun.job_code == code).order_by(JobRun.created_at))
    )


def test_concurrent_launches_yield_one_run_and_one_lock_skip(engine, runner_enabled) -> None:
    with Session(engine) as db:
        code = _create_job(db, handler="blocking")

    handlers.release_event.clear()
    handlers.started_event.clear()
    results = {}

    def first_launch():
        with Session(engine) as db:
            results["first"] = execute_job(db, job_code=code, trigger="manual").status

    thread = threading.Thread(target=first_launch)
    thread.start()
    assert handlers.started_event.wait(timeout=5), "first run never started"

    with Session(engine) as db:
        second = execute_job(db, job_code=code, trigger="manual")
        assert second.status == "skipped"
        assert second.skip_reason == "lock_held"

    handlers.release_event.set()
    thread.join(timeout=10)
    assert results["first"] == "completed"

    with Session(engine) as db:
        statuses = sorted(run.status for run in _runs(db, code))
        assert statuses == ["completed", "skipped"]


def test_failed_run_does_not_advance_cursor_no_hole_no_double(engine, runner_enabled) -> None:
    with Session(engine) as db:
        code = _create_job(db, handler="advance_cursor")
        window_1_end = datetime.now(UTC) - timedelta(minutes=10)
        run_1 = execute_job(
            db, job_code=code, trigger="manual", window=Window(from_ts=None, to_ts=window_1_end)
        )
        assert run_1.status == "completed"
        cursor = db.get(JobCursor, code)
        assert cursor is not None
        assert cursor.last_processed_event_ts == window_1_end

        # Failure: cursor must NOT move.
        definition = db.scalar(select(JobDefinition).where(JobDefinition.code == code))
        definition.handler_ref = "toolbox_runner_handlers:failing"
        db.commit()
        window_2_end = datetime.now(UTC)
        run_2 = execute_job(
            db,
            job_code=code,
            trigger="manual",
            window=Window(from_ts=cursor.last_processed_event_ts, to_ts=window_2_end),
        )
        assert run_2.status == "failed"
        db.expire_all()
        cursor = db.get(JobCursor, code)
        assert cursor.last_processed_event_ts == window_1_end  # no hole, no double

        # Retry from the SAME cursor succeeds and advances exactly once.
        definition = db.scalar(select(JobDefinition).where(JobDefinition.code == code))
        definition.handler_ref = "toolbox_runner_handlers:advance_cursor"
        db.commit()
        run_3 = execute_job(
            db,
            job_code=code,
            trigger="manual",
            window=Window(from_ts=cursor.last_processed_event_ts, to_ts=window_2_end),
        )
        assert run_3.status == "completed"
        db.expire_all()
        assert db.get(JobCursor, code).last_processed_event_ts == window_2_end


def test_runner_flag_disabled_logs_dry_run_skip(engine, monkeypatch) -> None:
    from types import SimpleNamespace

    from app.services.runner import engine as engine_module

    monkeypatch.setattr(
        engine_module, "get_settings", lambda: SimpleNamespace(runner_enabled=False)
    )
    handlers.calls.clear()
    with Session(engine) as db:
        code = _create_job(db, handler="ok")
        run = execute_job(db, job_code=code, trigger="cron")
        assert run.status == "skipped"
        assert run.skip_reason == "flag_disabled"
        assert handlers.calls == []  # registered, never executed


def test_disabled_job_logs_skip_even_with_runner_enabled(engine, runner_enabled) -> None:
    with Session(engine) as db:
        code = _create_job(db, handler="ok", enabled=False)
        run = execute_job(db, job_code=code, trigger="manual")
        assert run.status == "skipped"
        assert run.skip_reason == "job_disabled"


def test_timeout_marks_run_failed(engine, runner_enabled) -> None:
    with Session(engine) as db:
        code = _create_job(db, handler="sleepy", timeout_s=1)
        run = execute_job(db, job_code=code, trigger="manual")
        assert run.status == "failed"
        assert run.skip_reason == "timeout"


def test_gpu_service_unreachable_is_logged_skip_never_failure(engine, runner_enabled) -> None:
    with Session(engine) as db:
        code = _create_job(db, handler="gpu_down")
        run = execute_job(db, job_code=code, trigger="manual")
        assert run.status == "skipped"
        assert run.skip_reason == "gpu_service_unreachable"


def test_socle_jobs_are_seeded_disabled(engine) -> None:
    # CF-4/CF-6 (doc 76): every seeded job is born enabled=false.
    with Session(engine) as db:
        seeded = db.scalars(
            select(JobDefinition).where(
                JobDefinition.code.in_(
                    ["system.events_heartbeat", "path.mawaqit_refresh", "system.backup_nightly"]
                )
            )
        ).all()
        assert len(seeded) == 3
        assert all(job.enabled is False for job in seeded)
