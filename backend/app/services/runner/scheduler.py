"""Runner wiring: APScheduler for cron jobs + a LISTEN events_new consumer.

Everything registers regardless of flags; execute_job() itself dry-runs
(skipped + logged) while runner_enabled=False or the job is disabled — the
registration/execution split is the CF-4 guarantee.

Startup is explicit (start_runner from the FastAPI lifespan, gated by
RUNNER_SCHEDULER_AUTOSTART) so tests never spawn background threads.
"""

import logging
import threading
from uuid import UUID

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.toolbox import JobDefinition
from app.services.events.nomenclature import expand_for_read
from app.services.runner.engine import execute_job

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
_listener_stop = threading.Event()
_listener_thread: threading.Thread | None = None


def _run_job_once(job_code: str, trigger: str, trigger_ref: UUID | None = None) -> None:
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        try:
            execute_job(db, job_code=job_code, trigger=trigger, trigger_ref=trigger_ref)
        except Exception:  # noqa: BLE001 - the scheduler must survive any job
            logger.exception("Runner job invocation failed.", extra={"job_code": job_code})


def register_cron_jobs(scheduler: BackgroundScheduler, db: Session) -> list[str]:
    """Register every cron job_definition (enabled or not — dry-run logs skips)."""
    registered: list[str] = []
    jobs = db.scalars(select(JobDefinition).where(JobDefinition.kind == "cron")).all()
    for job in jobs:
        try:
            trigger = CronTrigger.from_crontab(job.schedule, timezone="UTC")
        except ValueError:
            logger.error(
                "Invalid cron schedule; job not registered.",
                extra={"job_code": job.code, "schedule": job.schedule},
            )
            continue
        scheduler.add_job(
            _run_job_once,
            trigger=trigger,
            args=[job.code, "cron"],
            id=f"runner:{job.code}",
            replace_existing=True,
        )
        registered.append(job.code)
    return registered


def dispatch_event(db: Session, event_id: str) -> list[str]:
    """Wake every event_subscription job matching the inserted event's type.

    event_types NULL = subscribed to all types. Returns the launched job codes.
    """
    event = db.get(Event, UUID(event_id))
    if event is None:
        return []
    jobs = db.scalars(
        select(JobDefinition).where(JobDefinition.kind == "event_subscription")
    ).all()
    launched: list[str] = []
    for job in jobs:
        if job.event_types and event.event_type not in expand_for_read(list(job.event_types)):
            continue
        execute_job(db, job_code=job.code, trigger="event", trigger_ref=event.id)
        launched.append(job.code)
    return launched


def _listen_loop() -> None:
    """Dedicated LISTEN events_new connection; wakes subscribed jobs on NOTIFY."""
    from app.db.session import engine

    raw = engine.raw_connection()
    try:
        driver_conn = raw.driver_connection  # psycopg 3 connection
        driver_conn.autocommit = True
        driver_conn.execute("LISTEN events_new")
        while not _listener_stop.is_set():
            for notice in driver_conn.notifies(timeout=1.0):
                _dispatch_notify(notice.payload)
    except Exception:  # noqa: BLE001 - listener death is logged, not fatal
        logger.exception("events_new listener stopped unexpectedly.")
    finally:
        raw.close()


def _dispatch_notify(event_id: str) -> None:
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        try:
            dispatch_event(db, event_id)
        except Exception:  # noqa: BLE001
            logger.exception("events_new dispatch failed.", extra={"event_id": event_id})


def start_runner() -> BackgroundScheduler:
    """Start APScheduler + the LISTEN consumer. Idempotent."""
    global _scheduler, _listener_thread
    if _scheduler is not None:
        return _scheduler

    from app.db.session import SessionLocal

    scheduler = BackgroundScheduler(timezone="UTC")
    with SessionLocal() as db:
        registered = register_cron_jobs(scheduler, db)
    scheduler.start()
    _scheduler = scheduler

    _listener_stop.clear()
    _listener_thread = threading.Thread(target=_listen_loop, name="events-new-listener", daemon=True)
    _listener_thread.start()
    logger.info("Runner started.", extra={"cron_jobs": registered})
    return scheduler


def shutdown_runner() -> None:
    global _scheduler, _listener_thread
    _listener_stop.set()
    if _listener_thread is not None:
        _listener_thread.join(timeout=5)
        _listener_thread = None
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
