"""Refresh du registre `imperium_mission_scores` (spec Daily §4.6, §12 ; carte ACT-DLY-03).

Le critère A dépend du temps : le registre est rafraîchi chaque matin (job `daily.scores_refresh`,
6 h de Paris) et après chaque réglage d'un barème (`scoring_settings.update_settings`). Missions
ouvertes seulement (backlog, active, standby) ; une ligne n'est réécrite que si elle change.
`daily.day_start` (abonné à `planning.day.started`) rafraîchit aussi, puis lance la sélection initiale
du Niveau 1 si `daily.selection_enabled` (vague 28). Ni l'un ni l'autre ne démarre une journée.
"""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.imperium import ImperiumMission, ImperiumMissionScore
from app.services.imperium import decision_framework as df

PARIS = ZoneInfo("Europe/Paris")
REFRESH_LOCAL_HOUR = 6
OPEN_STATUSES = ("backlog", "active", "standby")


@dataclass
class RefreshStats:
    scanned: int = 0
    refreshed: int = 0
    full: int = 0
    deadline_only: int = 0


def refresh_scores(db: Session, *, current_user: User) -> RefreshStats:
    """Recalcule les scores des missions ouvertes avec les barèmes et la hiérarchie courants (flush seulement)."""
    scales = df.load_scales(db)
    priorities = df.get_user_priority_context(db, current_user=current_user)
    rows = db.execute(
        select(ImperiumMissionScore, ImperiumMission.deadline_at)
        .join(ImperiumMission, ImperiumMission.id == ImperiumMissionScore.mission_id)
        .where(ImperiumMissionScore.user_id == current_user.id, ImperiumMissionScore.source == df.SOURCE,
               ImperiumMission.status.in_(OPEN_STATUSES))
        .with_for_update(of=ImperiumMissionScore)
    ).all()
    stats = RefreshStats(scanned=len(rows))
    for score, deadline_at in rows:
        full = isinstance((score.explanation or {}).get("inputs"), dict)
        if df.rescore(score, deadline_at=deadline_at, priorities=priorities, scales=scales):
            stats.refreshed += 1
            if full:
                stats.full += 1
            else:
                stats.deadline_only += 1
    db.flush()
    return stats


def scores_refresh_job(ctx, window) -> None:
    """Job `daily.scores_refresh` (semé désactivé) : 6 h de Paris ; ne démarre jamais une journée."""
    now = window.to_ts or datetime.now(UTC)
    ctx.cursor_ts = now
    if ctx.trigger != "manual" and now.astimezone(PARIS).hour != REFRESH_LOCAL_HOUR:
        ctx.items_in = ctx.items_out = 0
        ctx.detail = {"skipped": "not_refresh_hour"}
        return
    _refresh(ctx)


def day_start_job(ctx, window) -> None:
    """Job `daily.day_start` (abonné à `planning.day.started`, semé désactivé) : refresh puis sélection initiale."""
    from app.services.daily.selection import day_start_selection

    ctx.cursor_ts = window.to_ts or datetime.now(UTC)
    _refresh(ctx)
    if ctx.detail.get("skip") != "no_user":
        ctx.detail = {**ctx.detail, **day_start_selection(ctx)}


def _refresh(ctx, **extra) -> None:
    from app.services.wr.metrics import _job_user

    user = _job_user(ctx.db)
    if user is None:
        ctx.items_in = ctx.items_out = 0
        ctx.detail = {"skip": "no_user", **extra}
        return
    stats = refresh_scores(ctx.db, current_user=user)
    ctx.db.commit()
    ctx.items_in, ctx.items_out = stats.scanned, stats.refreshed
    ctx.detail = {**asdict(stats), **extra}
