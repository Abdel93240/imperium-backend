import importlib
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.toolbox import JobCursor, JobDefinition, JobRun

logger = logging.getLogger(__name__)

SKIP_FLAG_DISABLED = "flag_disabled"
SKIP_JOB_DISABLED = "job_disabled"
SKIP_LOCK_HELD = "lock_held"
SKIP_GPU_UNREACHABLE = "gpu_service_unreachable"
FAIL_TIMEOUT = "timeout"


@dataclass(frozen=True)
class Window:
    from_ts: datetime | None
    to_ts: datetime | None


@dataclass
class RunContext:
    db: Session | None
    job: JobDefinition
    run_id: UUID
    trigger: str
    trigger_ref: UUID | None
    # Handlers set these to drive the run row and the cursor.
    items_in: int | None = None
    items_out: int | None = None
    detail: dict = field(default_factory=dict)
    cursor_ts: datetime | None = None
    cursor_event_id: UUID | None = None


Handler = Callable[[RunContext, Window], None]


class HandlerResolutionError(RuntimeError):
    pass


def resolve_handler(handler_ref: str) -> Handler:
    """Resolve a 'package.module:function' reference to a callable."""
    module_name, _, function_name = handler_ref.partition(":")
    if not module_name or not function_name:
        raise HandlerResolutionError(f"Invalid handler_ref '{handler_ref}'.")
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise HandlerResolutionError(f"Cannot import module for '{handler_ref}'.") from exc
    handler = getattr(module, function_name, None)
    if not callable(handler):
        raise HandlerResolutionError(f"'{handler_ref}' does not resolve to a callable.")
    return handler


def execute_job(
    db: Session,
    *,
    job_code: str,
    trigger: str,
    trigger_ref: UUID | None = None,
    window: Window | None = None,
    now: datetime | None = None,
) -> JobRun:
    """Run one job once, recording exactly one job_runs row.

    The session is committed at each state transition so a concurrent observer
    (and the advisory-lock loser) always sees a consistent journal.
    """
    settings = get_settings()
    now = now or datetime.now(UTC)
    job = db.scalar(select(JobDefinition).where(JobDefinition.code == job_code))
    if job is None:
        raise LookupError(f"Unknown job '{job_code}'.")

    if not settings.runner_enabled:
        return _record_skip(db, job, trigger, trigger_ref, SKIP_FLAG_DISABLED, now)
    if not job.enabled:
        return _record_skip(db, job, trigger, trigger_ref, SKIP_JOB_DISABLED, now)

    # The advisory lock lives on a DEDICATED connection held for the whole run:
    # the session's pooled connection changes across commits and would drop it.
    lock_conn = None
    if job.singleton:
        lock_conn = db.get_bind().connect()
        lock_taken = bool(
            lock_conn.execute(
                text("SELECT pg_try_advisory_lock(hashtext(:code))"), {"code": job.code}
            ).scalar()
        )
        if not lock_taken:
            lock_conn.close()
            return _record_skip(db, job, trigger, trigger_ref, SKIP_LOCK_HELD, now)

    try:
        if window is None:
            window = _default_window(db, job, now)
        run = JobRun(
            id=uuid4(),
            job_code=job.code,
            trigger=trigger,
            trigger_ref=trigger_ref,
            window_from=window.from_ts,
            window_to=window.to_ts,
            status="running",
        )
        db.add(run)
        db.commit()

        # The handler gets its OWN session (same bind): on timeout the abandoned
        # thread must never race the main session.
        ctx = RunContext(
            db=None, job=job, run_id=run.id, trigger=trigger, trigger_ref=trigger_ref
        )
        started = time.monotonic()
        outcome, error_text = _run_with_timeout(db, job, ctx, window)
        duration_ms = int((time.monotonic() - started) * 1000)

        run = db.get(JobRun, run.id)
        run.duration_ms = duration_ms
        run.items_in = ctx.items_in
        run.items_out = ctx.items_out
        run.detail = ctx.detail or None
        if outcome == "completed":
            run.status = "completed"
            _advance_cursor(db, job.code, ctx)
        elif outcome == "gpu_unreachable":
            # A down GPU service never fails a job (graved topology rule).
            run.status = "skipped"
            run.skip_reason = SKIP_GPU_UNREACHABLE
            run.detail = {**(ctx.detail or {}), "error": error_text}
            _notify_gpu_skip(db, job.code)
        elif outcome == "timeout":
            run.status = "failed"
            run.skip_reason = FAIL_TIMEOUT
        else:
            run.status = "failed"
            run.detail = {**(ctx.detail or {}), "error": error_text}
        db.commit()
        logger.info(
            "Job run finished.",
            extra={"job_code": job.code, "run_id": str(run.id), "status": run.status},
        )
        return run
    finally:
        if lock_conn is not None:
            lock_conn.execute(
                text("SELECT pg_advisory_unlock(hashtext(:code))"), {"code": job.code}
            )
            lock_conn.close()


def _run_with_timeout(
    db: Session, job: JobDefinition, ctx: RunContext, window: Window
) -> tuple[str, str | None]:
    from app.services.ai.embedding import GpuServiceUnreachable

    result: dict[str, Any] = {}

    def _target() -> None:
        handler_db = Session(bind=db.get_bind())
        ctx.db = handler_db
        try:
            handler = resolve_handler(job.handler_ref)
            handler(ctx, window)
            handler_db.commit()
            result["outcome"] = "completed"
        except GpuServiceUnreachable as exc:
            handler_db.rollback()
            result["outcome"] = "gpu_unreachable"
            result["error"] = str(exc)
        except Exception as exc:  # noqa: BLE001 - the journal records the failure
            handler_db.rollback()
            logger.exception("Job handler failed.", extra={"job_code": job.code})
            result["outcome"] = "failed"
            result["error"] = str(exc)
        finally:
            handler_db.close()

    thread = threading.Thread(target=_target, name=f"job-{job.code}", daemon=True)
    thread.start()
    thread.join(timeout=job.timeout_s)
    if thread.is_alive():
        return "timeout", None
    return result.get("outcome", "failed"), result.get("error")


def _default_window(db: Session, job: JobDefinition, now: datetime) -> Window:
    if job.kind != "event_subscription":
        return Window(from_ts=None, to_ts=now)
    cursor = db.get(JobCursor, job.code)
    return Window(from_ts=cursor.last_processed_event_ts if cursor else None, to_ts=now)


def _advance_cursor(db: Session, job_code: str, ctx: RunContext) -> None:
    if ctx.cursor_ts is None:
        return
    cursor = db.get(JobCursor, job_code)
    if cursor is None:
        db.add(
            JobCursor(
                job_code=job_code,
                last_processed_event_ts=ctx.cursor_ts,
                last_processed_event_id=ctx.cursor_event_id,
            )
        )
    else:
        cursor.last_processed_event_ts = ctx.cursor_ts
        cursor.last_processed_event_id = ctx.cursor_event_id


def _record_skip(
    db: Session,
    job: JobDefinition,
    trigger: str,
    trigger_ref: UUID | None,
    reason: str,
    now: datetime,
) -> JobRun:
    run = JobRun(
        id=uuid4(),
        job_code=job.code,
        trigger=trigger,
        trigger_ref=trigger_ref,
        status="skipped",
        skip_reason=reason,
        window_to=now,
    )
    db.add(run)
    db.commit()
    logger.info(
        "Job run skipped.", extra={"job_code": job.code, "skip_reason": reason}
    )
    return run


def _notify_gpu_skip(db: Session, job_code: str) -> None:
    from app.services.notifications import notify

    try:
        notify(
            db,
            severity="normal",
            domain="system",
            message_fr=f"Service GPU injoignable : job {job_code} sauté (skip loggé).",
            ref=("job_definition", None),
        )
    except Exception:  # noqa: BLE001 - notification must never break the runner
        logger.exception("GPU-skip notification failed.", extra={"job_code": job_code})
