"""Métriques quotidiennes Pulse et agreement des slots Pulse (spec Pulse §3.9, §13, §14 ; carte ACT-PLS-27).

Un jour de Paris par ligne et par utilisateur, compté depuis `pulse_dispatch_log` (réveils retenus,
passes vertes gratuites, annotations, escalades, replis invalides) et `pulse_red_flag_events`. Les
propositions et le solveur ne sont pas codés : leurs colonnes restent NULL. L'agreement du jour vient
des contre-lectures `ai_audit_samples` des slots `pulse.*` (aucune tant que l'IA est coupée : NULL).

Le job `pulse.metrics_rollup` (semé désactivé) recalcule les deux derniers jours clos ; l'agreement
hebdo et la décroissance d'audit passent par le job partagé `wr.audit_weekly` (jamais appliquée seule).
"""

from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.pulse import PulseDispatchLog, PulseMetricsDaily, PulseRedFlagEvent
from app.models.toolbox import AIAuditSample
from app.schemas.pulse_signals import MetricsDayRead, MetricsSlotRead, MetricsSummaryRead
from app.services.ai import audit_loop

PARIS = ZoneInfo("Europe/Paris")
COUNTS = ("dispatches", "skipped_passes", "dispatches_useful", "dispatches_useless", "missed_reports",
          "escalations", "invalid_fallbacks", "red_flags")


def paris_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=PARIS)
    return start, datetime.combine(day + timedelta(days=1), time.min, tzinfo=PARIS)


def compute_day(db: Session, *, current_user: User, day: date) -> dict:
    """Compteurs du jour (lecture seule)."""
    start, end = paris_bounds(day)
    log = PulseDispatchLog
    in_day = (log.user_id == current_user.id, log.created_at >= start, log.created_at < end)
    skipped = log.model_used == "skipped"
    row = db.execute(select(
        func.count().filter(or_(log.model_used.is_(None), ~skipped)),
        func.count().filter(skipped),
        func.count().filter(log.user_reaction == "useful"),
        func.count().filter(log.user_reaction == "useless"),
        func.count().filter(log.user_reaction == "missed"),
        func.count().filter(log.escalated.is_(True)),
        func.count().filter(log.outcome == "invalid_fallback"),
    ).where(*in_day)).one()
    red = db.scalar(select(func.count()).select_from(PulseRedFlagEvent).where(
        PulseRedFlagEvent.user_id == current_user.id, PulseRedFlagEvent.raised_at >= start,
        PulseRedFlagEvent.raised_at < end))
    values = dict(zip(COUNTS, [*row, red], strict=True))
    values["agreement_by_slot"] = agreement_by_slot(db, start=start, end=end)
    return values


def agreement_by_slot(db: Session, *, start: datetime, end: datetime) -> dict[str, float] | None:
    rows = db.execute(select(
        AIAuditSample.slot_code, func.count(), func.count().filter(AIAuditSample.agreement.is_(True)),
    ).where(AIAuditSample.slot_code.like("pulse.%"), AIAuditSample.agreement.is_not(None),
            AIAuditSample.created_at >= start, AIAuditSample.created_at < end)
        .group_by(AIAuditSample.slot_code)).all()
    return {slot: round(100.0 * agreed / total, 1) for slot, total, agreed in rows} or None


def upsert_day(db: Session, *, current_user: User, day: date, now: datetime) -> PulseMetricsDaily:
    values = compute_day(db, current_user=current_user, day=day)
    row = db.scalar(select(PulseMetricsDaily).where(PulseMetricsDaily.user_id == current_user.id,
                                                    PulseMetricsDaily.metric_date == day))
    if row is None:
        row = PulseMetricsDaily(id=uuid4(), user_id=current_user.id, metric_date=day)
        db.add(row)
    for key, value in values.items():
        setattr(row, key, value)
    row.computed_at = now
    db.flush()
    return row


def summary(db: Session, *, current_user: User, days: int = 7, now: datetime | None = None) -> MetricsSummaryRead:
    now = now or datetime.now(UTC)
    today = now.astimezone(PARIS).date()
    rows = db.scalars(select(PulseMetricsDaily).where(
        PulseMetricsDaily.user_id == current_user.id, PulseMetricsDaily.metric_date >= today - timedelta(days=days),
        PulseMetricsDaily.metric_date < today).order_by(PulseMetricsDaily.metric_date))
    slots = []
    for state in audit_loop.slot_states(db, now=now):
        if state.domain != "pulse":
            continue
        slots.append(MetricsSlotRead(
            slot_code=state.slot_code, tier=state.tier, audit_sample_pct=state.audit_sample_pct,
            agreement_target_pct=state.agreement_target_pct,
            last_week_agreement_pct=state.weeks[0].agreement_pct if state.weeks else None,
            decay_proposed=state.decay_proposed,
        ))
    return MetricsSummaryRead(
        days=[MetricsDayRead.model_validate(row) for row in rows],
        today=MetricsDayRead(metric_date=today, **compute_day(db, current_user=current_user, day=today)),
        slots=slots,
    )


def rollup_job(ctx, window) -> None:
    """Job `pulse.metrics_rollup` (semé désactivé) : recalcule les deux derniers jours de Paris clos."""
    from app.services.wr.metrics import _job_user

    now = window.to_ts or datetime.now(UTC)
    ctx.cursor_ts = now
    user = _job_user(ctx.db)
    if user is None:
        ctx.items_in = ctx.items_out = 0
        ctx.detail = {"skip": "no_user"}
        return
    today = now.astimezone(PARIS).date()
    days = [today - timedelta(days=2), today - timedelta(days=1)]
    for day in days:
        upsert_day(ctx.db, current_user=user, day=day, now=now)
    ctx.db.commit()
    ctx.items_in = ctx.items_out = len(days)
    ctx.detail = {"days": [day.isoformat() for day in days]}
