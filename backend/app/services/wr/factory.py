"""Usine du WR : déclenchement, ordre des workers, curseurs incrémentaux (spec WR §3.2, §4).

Un run traite, pour chaque worker, la fenêtre ]curseur, maintenant] dans l'ordre W1 → W4 → W2 → W3 → W5,
puis avance le curseur du worker. Un worker qui échoue n'avance PAS son curseur et arrête la chaîne
(les suivants dépendent de lui) : le run suivant reprend le même lot. Un worker pas encore codé est
sauté sans curseur ; codé plus tard, il partira du début du jour de Paris de son premier run.

Codé aujourd'hui : W5 (recalcul persistant des priorités du docket). W1 rollups, W4 anomalies,
W2 découverte causale (IA) et W3 apprentissages (IA) restent à coder ; ce module n'appelle aucun
modèle. Les jobs `wr.factory_on_session_end` et `wr.factory_fallback` sont semés désactivés.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.event import Event
from app.models.wr import WrWorkerCursor, WrWorkerRun
from app.services.events.emitter import build_event
from app.services.wr import docket

PARIS = ZoneInfo("Europe/Paris")
WORKER_ORDER = ("w1_rollups", "w4_anomalies", "w2_causal", "w3_learning", "w5_docket")
FALLBACK_LOCAL_HOUR = 23


@dataclass
class WorkerOutcome:
    items_in: int | None = None
    items_out: int | None = None
    detail: dict = field(default_factory=dict)


Worker = Callable[[Session, User, datetime, datetime], WorkerOutcome]


def _w5_docket(db: Session, user: User, window_from: datetime, window_to: datetime) -> WorkerOutcome:
    count = docket.reprioritize(db, current_user=user, now=window_to)
    return WorkerOutcome(items_in=count, items_out=count, detail={"reprioritized": count})


# None = worker pas encore codé (sauté, sans curseur).
WORKERS: dict[str, Worker | None] = {
    "w1_rollups": None,
    "w4_anomalies": None,
    "w2_causal": None,
    "w3_learning": None,
    "w5_docket": _w5_docket,
}


def run_factory(
    db: Session,
    *,
    user: User,
    trigger: str,
    now: datetime,
    session_ref: UUID | None = None,
    job_run_id: UUID | None = None,
    causation_id: str | None = None,
) -> dict:
    """Un passage de l'usine ; rend le résumé (workers faits, sautés, en échec)."""
    summary: dict = {"completed": [], "not_coded": [], "failed": None}
    for worker in WORKER_ORDER:
        handler = WORKERS[worker]
        if handler is None:
            summary["not_coded"].append(worker)
            continue
        cursor = db.get(WrWorkerCursor, worker)
        window_from = cursor.last_processed_event_ts if cursor else _day_start(now)
        started = time.monotonic()
        try:
            with db.begin_nested():
                outcome = handler(db, user, window_from, now)
        except Exception as exc:  # noqa: BLE001 - le run est journalisé en échec, la chaîne s'arrête
            run = _record(db, worker, trigger, session_ref, job_run_id, window_from, now, started, "failed",
                          WorkerOutcome(detail={"error": type(exc).__name__}))
            _emit(db, user, run, causation_id)
            summary["failed"] = worker
            break
        run = _record(db, worker, trigger, session_ref, job_run_id, window_from, now, started, "completed", outcome)
        if cursor is None:
            db.add(WrWorkerCursor(worker=worker, last_processed_event_ts=now, updated_at=now))
        else:
            cursor.last_processed_event_ts, cursor.last_processed_event_id, cursor.updated_at = now, None, now
        _emit(db, user, run, causation_id)
        summary["completed"].append(worker)
    db.flush()
    return summary


def factory_on_session_end_job(ctx, window) -> None:
    """Job `wr.factory_on_session_end` (abonné à `rides.session.ended`, semé désactivé)."""
    now = window.to_ts or datetime.now(UTC)
    user = _job_user(ctx.db)
    event = ctx.db.scalar(select(Event).where(Event.id == ctx.trigger_ref)) if ctx.trigger_ref else None
    session_ref = None
    if event is not None and event.payload.get("session_id"):
        session_ref = UUID(str(event.payload["session_id"]))
    _run_job(ctx, user, "session_end" if ctx.trigger == "event" else "manual", now, session_ref,
             event.event_id if event is not None else None)
    ctx.cursor_ts = now


def factory_fallback_job(ctx, window) -> None:
    """Job `wr.factory_fallback` : 23 h de Paris, seulement si l'usine n'a pas tourné ce jour-là."""
    now = window.to_ts or datetime.now(UTC)
    if ctx.trigger != "manual" and now.astimezone(PARIS).hour != FALLBACK_LOCAL_HOUR:
        ctx.items_in = ctx.items_out = 0
        ctx.detail = {"skipped": "not_fallback_hour"}
        return
    ran_today = ctx.db.scalar(select(WrWorkerRun.id).where(WrWorkerRun.created_at >= _day_start(now)).limit(1))
    if ran_today is not None:
        ctx.items_in = ctx.items_out = 0
        ctx.detail = {"skipped": "already_ran_today"}
        return
    _run_job(ctx, _job_user(ctx.db), "fallback_cron" if ctx.trigger != "manual" else "manual", now, None, None)


def _run_job(ctx, user: User | None, trigger: str, now: datetime, session_ref: UUID | None,
             causation_id: str | None) -> None:
    if user is None:
        ctx.items_in = ctx.items_out = 0
        ctx.detail = {"skipped": "no_user"}
        return
    summary = run_factory(ctx.db, user=user, trigger=trigger, now=now, session_ref=session_ref,
                          job_run_id=ctx.run_id, causation_id=causation_id)
    ctx.db.commit()
    if summary["failed"]:
        raise RuntimeError(f"WR factory worker {summary['failed']} failed; its cursor did not move.")
    ctx.items_in = len(WORKER_ORDER)
    ctx.items_out = len(summary["completed"])
    ctx.detail = summary


def _record(db: Session, worker: str, trigger: str, session_ref: UUID | None, job_run_id: UUID | None,
            window_from: datetime, window_to: datetime, started: float, status: str,
            outcome: WorkerOutcome) -> WrWorkerRun:
    run = WrWorkerRun(
        worker=worker, trigger=trigger, session_ref=session_ref, job_run_id=job_run_id, window_from=window_from,
        window_to=window_to, items_in=outcome.items_in, items_out=outcome.items_out, llm_calls=0,
        duration_ms=int((time.monotonic() - started) * 1000), status=status, detail=outcome.detail or None,
        created_at=window_to,
    )
    db.add(run)
    db.flush()
    return run


def _emit(db: Session, user: User, run: WrWorkerRun, causation_id: str | None) -> None:
    db.add(build_event(
        db, user_id=user.id, event_type="planning.factory.run_completed",
        payload={"worker": run.worker, "trigger": run.trigger, "window_from": run.window_from.isoformat(),
                 "window_to": run.window_to.isoformat(), "items_out": run.items_out, "status": run.status},
        idempotency_key=f"planning.factory.run_completed.{run.id}", source_app=SourceApp.imperium,
        privacy_level=PrivacyLevel.low, causation_id=causation_id, occurred_at=run.window_to,
    ))
    db.flush()


def _day_start(now: datetime) -> datetime:
    local = now.astimezone(PARIS)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def _job_user(db: Session) -> User | None:
    from app.services.wr.metrics import _job_user as job_user

    return job_user(db)

