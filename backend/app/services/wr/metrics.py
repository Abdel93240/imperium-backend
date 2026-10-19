"""Métriques hebdomadaires du WR et politique de saut (spec WR §3.8, §7).

Semaine = [lundi 00:00, lundi suivant 00:00) en Europe/Paris. Sources :
- docket : items créés dans la semaine (et par type pour chain_proposals, patterns_new,
  contradictions) ; décisions et décisions forcées = events `planning.docket.*` de la semaine ;
- usine : runs `wr.factory*` du runner (aucun job d'usine n'existe encore → 0) ;
- WR : session de la semaine. Lancée → wr_mode `full` (le mode court n'est pas encore
  enregistré sur la session) et durée lancement → fin. Rien de lancé quand la fenêtre est
  close (lundi de S+2, la revue de S se tenant pendant S+1) → `skipped` ; avant, NULL.
NULL = non mesurable tant que le worker ou le moteur qui l'alimente n'est pas codé.
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, literal_column, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.event import Event
from app.models.imperium import ImperiumWeeklyReviewSession
from app.models.toolbox import JobRun
from app.models.wr import WrDocketItem, WrMetricsWeekly


PARIS = ZoneInfo("Europe/Paris")
WR_WINDOW_DAYS = 14
METRIC_FIELDS = (
    "factory_runs", "events_processed", "chain_proposals", "patterns_new", "patterns_reinforced",
    "contradictions", "docket_created", "docket_validated", "docket_refused", "docket_deferred",
    "docket_forced_decisions", "wr_duration_min", "wr_mode", "cloud_cost_estimate", "agreement_by_slot",
)


def week_start_of(moment: datetime) -> date:
    local = moment.astimezone(PARIS).date()
    return local - timedelta(days=local.weekday())


def compute_week(
    db: Session, *, current_user: User, week_start: date, now: datetime | None = None
) -> WrMetricsWeekly:
    """Métriques d'une semaine, en lecture seule (la ligne rendue n'est pas ajoutée à la session)."""
    if week_start.weekday() != 0:
        raise ValueError("week_start must be a Monday.")
    now = now or datetime.now(UTC)
    start = datetime.combine(week_start, time.min, tzinfo=PARIS)
    end = datetime.combine(week_start + timedelta(days=7), time.min, tzinfo=PARIS)

    created_by_type = dict(db.execute(
        select(WrDocketItem.item_type, func.count())
        .where(WrDocketItem.user_id == current_user.id, WrDocketItem.created_at >= start, WrDocketItem.created_at < end)
        .group_by(WrDocketItem.item_type)
    ).all())
    status = Event.payload.op("->>")(literal_column("'status'")).label("status")
    decided_by_status = dict(db.execute(
        select(status, func.count())
        .where(Event.user_id == current_user.id, Event.event_type == "planning.docket.item_decided",
               Event.occurred_at >= start, Event.occurred_at < end)
        .group_by(status)
    ).all())
    forced = db.scalar(
        select(func.count()).select_from(Event)
        .where(Event.user_id == current_user.id, Event.event_type == "planning.docket.item_forced",
               Event.occurred_at >= start, Event.occurred_at < end)
    )
    factory_runs = db.scalar(
        select(func.count()).select_from(JobRun)
        .where(JobRun.job_code.like("wr.factory%"), JobRun.status == "completed",
               JobRun.created_at >= start, JobRun.created_at < end)
    )
    session = db.scalar(
        select(ImperiumWeeklyReviewSession).where(
            ImperiumWeeklyReviewSession.user_id == current_user.id, ImperiumWeeklyReviewSession.week_start == week_start
        )
    )
    wr_mode, duration = None, None
    if session is not None and session.launched_at is not None:
        wr_mode = "full"
        if session.completed_at is not None:
            duration = int((session.completed_at - session.launched_at).total_seconds() // 60)
    elif now >= datetime.combine(week_start + timedelta(days=WR_WINDOW_DAYS), time.min, tzinfo=PARIS):
        wr_mode = "skipped"

    return WrMetricsWeekly(
        user_id=current_user.id, week_start=week_start, factory_runs=factory_runs, events_processed=None,
        chain_proposals=created_by_type.get("chain_proposal", 0), patterns_new=created_by_type.get("pattern_new", 0),
        patterns_reinforced=None, contradictions=created_by_type.get("pattern_contradiction", 0),
        docket_created=sum(created_by_type.values()), docket_validated=decided_by_status.get("validated", 0),
        docket_refused=decided_by_status.get("refused", 0), docket_deferred=decided_by_status.get("deferred", 0),
        docket_forced_decisions=forced, wr_duration_min=duration, wr_mode=wr_mode, cloud_cost_estimate=None,
        agreement_by_slot=None, computed_at=now,
    )


def recent_weeks(db: Session, *, current_user: User, weeks: int, now: datetime | None = None) -> list[WrMetricsWeekly]:
    """Les `weeks` dernières semaines, semaine en cours comprise, la plus récente d'abord."""
    now = now or datetime.now(UTC)
    current = week_start_of(now)
    return [
        compute_week(db, current_user=current_user, week_start=current - timedelta(days=7 * offset), now=now)
        for offset in range(weeks)
    ]


def upsert_week(db: Session, row: WrMetricsWeekly) -> None:
    values = {field: getattr(row, field) for field in METRIC_FIELDS}
    statement = insert(WrMetricsWeekly).values(
        user_id=row.user_id, week_start=row.week_start, computed_at=row.computed_at, **values
    )
    db.execute(statement.on_conflict_do_update(
        constraint="wr_metrics_weekly_user_week_unique", set_={**values, "computed_at": row.computed_at},
    ))


def metrics_rollup_job(ctx, window) -> None:
    """Job `wr.metrics_rollup` (semé désactivé) : recalcule les deux dernières semaines closes."""
    now = window.to_ts or datetime.now(UTC)
    user = _job_user(ctx.db)
    if user is None:
        ctx.items_in, ctx.items_out, ctx.detail = 0, 0, {"skip": "no_user"}
        ctx.cursor_ts = now
        return
    current = week_start_of(now)
    weeks = [current - timedelta(days=14), current - timedelta(days=7)]
    for week_start in weeks:
        upsert_week(ctx.db, compute_week(ctx.db, current_user=user, week_start=week_start, now=now))
    ctx.db.commit()
    ctx.items_in = ctx.items_out = len(weeks)
    ctx.detail = {"weeks": [week.isoformat() for week in weeks]}
    ctx.cursor_ts = now


def _job_user(db: Session) -> User | None:
    from app.core.config import get_settings

    settings = get_settings()
    if settings.imperium_canonical_user_id is not None:
        user = db.get(User, settings.imperium_canonical_user_id)
        if user is not None:
            return user
    return db.scalar(select(User).order_by(User.created_at).limit(1))
