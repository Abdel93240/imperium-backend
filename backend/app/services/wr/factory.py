"""Usine du WR : déclenchement, ordre des workers, curseurs incrémentaux (spec WR §3.2, §4).

Un run traite, pour chaque worker, la fenêtre ]curseur, maintenant] dans l'ordre W1 → W4 → W2 → W3 → W5,
puis avance le curseur du worker. Un worker qui échoue n'avance PAS son curseur et arrête la chaîne
(les suivants dépendent de lui) : le run suivant reprend le même lot. Un worker pas encore codé est
sauté sans curseur ; codé plus tard, il partira du début du jour de Paris de son premier run.
Un worker codé ne tourne que s'il est listé dans `wr.factory_workers_enabled` (vide au départ :
bascule worker par worker, carte V18), sinon il est sauté sans curseur lui aussi.

Codés aujourd'hui : W1 (rollups quotidiens, rollups.py), W4 (anomalies sur les rollups,
anomalies.py) et W5 (items `anomaly` depuis W4, dédoublonnés par signal et jour, puis recalcul des
priorités du docket) ; W2 découverte causale en dry-run seulement (causal.py : sondes et verdicts
factices tant que `real_ai_enabled` est faux, échec explicite sinon) et W3 apprentissages en dry-run
seulement (learning.py : extractions factices, confrontations journalisées, aucune écriture mémoire).
Ce module n'appelle aucun modèle. Les jobs `wr.factory_on_session_end` et `wr.factory_fallback` sont semés désactivés.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.event import Event
from app.models.toolbox import SignalDefinition, SignalValue
from app.models.wr import WrDocketItem, WrWorkerCursor, WrWorkerRun
from app.services.events.emitter import build_event
from app.services.params import get_parameter
from app.services.wr import anomalies, causal, docket, learning, rollups

PARIS = ZoneInfo("Europe/Paris")
WORKER_ORDER = ("w1_rollups", "w4_anomalies", "w2_causal", "w3_learning", "w5_docket")
FALLBACK_LOCAL_HOUR = 23
ANOMALY_LOOKBACK_DAYS = 7
# Domaine du rollup → domaine du docket.
ANOMALY_DOMAINS = {"finance": "vault", "rides": "vector", "missions": "imperium"}


@dataclass
class WorkerOutcome:
    items_in: int | None = None
    items_out: int | None = None
    detail: dict = field(default_factory=dict)


Worker = Callable[[Session, User, datetime, datetime], WorkerOutcome]


def _w1_rollups(db: Session, user: User, window_from: datetime, window_to: datetime) -> WorkerOutcome:
    days = rollups.touched_days(db, user=user, window_from=window_from, window_to=window_to)
    written = rollups.rollup_days(db, user=user, days=days, now=window_to)
    return WorkerOutcome(items_in=len(days), items_out=written,
                         detail={"days": [day.isoformat() for day in days], "pulse": "stub"})


def _w4_anomalies(db: Session, user: User, window_from: datetime, window_to: datetime) -> WorkerOutcome:
    days = anomalies.touched_days(db, user=user, window_from=window_from, window_to=window_to)
    values = anomalies.evaluate_days(db, user=user, days=days)
    flagged = [value for value in values if value.band != "green"]
    return WorkerOutcome(items_in=len(days), items_out=len(values),
                         detail={"days": [day.isoformat() for day in days], "flagged": len(flagged)})


def _w2_causal(db: Session, user: User, window_from: datetime, window_to: datetime) -> WorkerOutcome:
    stats = causal.run_window(db, user=user, window_from=window_from, window_to=window_to)
    return WorkerOutcome(items_in=stats.targets, items_out=stats.assemblies,
                         detail={"dry_run": True, "reasons": stats.reasons, "probes": stats.probes,
                                 "candidates": stats.candidates, "retained": stats.retained,
                                 "verdicts": stats.verdicts, "links": stats.links, "vector_channels": "off"})


def _w3_learning(db: Session, user: User, window_from: datetime, window_to: datetime) -> WorkerOutcome:
    stats = learning.run_window(db, user=user, window_from=window_from, window_to=window_to)
    return WorkerOutcome(items_in=stats.episodes, items_out=stats.extractions,
                         detail={"dry_run": True, "rejected": stats.rejected,
                                 "predicates_rejected": stats.predicates_rejected,
                                 "confrontations": stats.confrontations, "memory_writes": 0})


def _w5_docket(db: Session, user: User, window_from: datetime, window_to: datetime) -> WorkerOutcome:
    created = _anomaly_items(db, user, window_to)
    count = docket.reprioritize(db, current_user=user, now=window_to)
    return WorkerOutcome(items_in=count, items_out=count + created,
                         detail={"reprioritized": count, "anomaly_items": created})


def _anomaly_items(db: Session, user: User, now: datetime) -> int:
    """Une anomalie W4 >= `wr.anomaly_docket_min_band` des 7 derniers jours → un item `anomaly`, une seule fois."""
    minimum = str(get_parameter(db, "wr.anomaly_docket_min_band", default="orange"))
    labels = dict(db.execute(select(SignalDefinition.code, SignalDefinition.label_fr)
                             .where(SignalDefinition.domain == "wr")).all())
    values = db.scalars(
        select(SignalValue).where(SignalValue.signal_code.like("wr.%"),
                                  SignalValue.measured_at > now - timedelta(days=ANOMALY_LOOKBACK_DAYS),
                                  SignalValue.measured_at <= now + timedelta(days=1),
                                  SignalValue.detail["user_id"].astext == str(user.id))
        .order_by(SignalValue.measured_at)
    ).all()
    created = 0
    for value in values:
        if not anomalies.band_at_least(value.band, minimum):
            continue
        refs = {"signal_code": value.signal_code, "local_date": value.detail["local_date"]}
        exists = db.scalar(select(WrDocketItem.id).where(
            WrDocketItem.user_id == user.id, WrDocketItem.item_type == "anomaly",
            WrDocketItem.evidence_refs.contains(refs)).limit(1))
        if exists is not None:
            continue
        domain = value.signal_code.split(".")[1]
        docket.create_item(
            db, current_user=user, item_type="anomaly", domain=ANOMALY_DOMAINS.get(domain, "wr"),
            title_fr=f"{labels.get(value.signal_code, value.signal_code)} inhabituel le {value.detail['local_date']}",
            payload={"signal_code": value.signal_code, "local_date": value.detail["local_date"],
                     "value": float(value.value), "baseline": value.detail["baseline"], "z": value.detail["z"],
                     "band": value.band, "unexplained": bool((value.flags or {}).get("unexplained"))},
            evidence_refs={**refs, "signal_value_id": str(value.id)},
            impact_estimate=4 if value.band == "red" else 3, source_worker="w4",
            severity="elevated" if value.band == "red" else "normal", now=now,
        )
        created += 1
    return created


# None = worker pas encore codé (sauté, sans curseur).
WORKERS: dict[str, Worker | None] = {
    "w1_rollups": _w1_rollups,
    "w4_anomalies": _w4_anomalies,
    "w2_causal": _w2_causal,
    "w3_learning": _w3_learning,
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
    summary: dict = {"completed": [], "not_coded": [], "disabled": [], "failed": None}
    enabled = set(get_parameter(db, "wr.factory_workers_enabled", default=[]) or [])
    for worker in WORKER_ORDER:
        handler = WORKERS[worker]
        if handler is None:
            summary["not_coded"].append(worker)
            continue
        if worker not in enabled:
            summary["disabled"].append(worker)
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


BACKFILL_WORKERS = ("w1_rollups", "w4_anomalies", "w5_docket")


def backfill(db: Session, *, user: User, days: int, now: datetime) -> dict:
    """Rattrapage à l'allumage de l'usine (geste de l'utilisateur, rejouable).

    W1 recalcule les `days` derniers jours de Paris, W4 les évalue dans l'ordre (la baseline de chaque jour
    s'appuie sur les jours d'avant), W5 dépose les anomalies des 7 derniers jours au docket ; puis les
    curseurs de W1, W4 et W5 passent à `now` : les passages suivants ne traitent que la suite.
    """
    today = now.astimezone(PARIS).date()
    span = [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
    started = time.monotonic()
    written = rollups.rollup_days(db, user=user, days=span, now=now)
    values = anomalies.evaluate_days(db, user=user, days=span)
    created = _anomaly_items(db, user, now)
    reprioritized = docket.reprioritize(db, current_user=user, now=now)
    outcomes = {
        "w1_rollups": WorkerOutcome(items_in=len(span), items_out=written, detail={"backfill_days": days}),
        "w4_anomalies": WorkerOutcome(items_in=len(span), items_out=len(values),
                                      detail={"flagged": sum(value.band != "green" for value in values)}),
        "w5_docket": WorkerOutcome(items_in=reprioritized, items_out=reprioritized + created,
                                   detail={"anomaly_items": created}),
    }
    window_from = datetime.combine(span[0], datetime.min.time(), tzinfo=PARIS)
    for worker in BACKFILL_WORKERS:
        _record(db, worker, "manual", None, None, window_from, now, started, "completed", outcomes[worker])
        cursor = db.get(WrWorkerCursor, worker)
        if cursor is None:
            db.add(WrWorkerCursor(worker=worker, last_processed_event_ts=now, updated_at=now))
        else:
            cursor.last_processed_event_ts, cursor.last_processed_event_id, cursor.updated_at = now, None, now
    db.flush()
    return {"days": days, "rollups": written, "signal_values": len(values),
            "flagged": outcomes["w4_anomalies"].detail["flagged"], "anomaly_items": created}


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

