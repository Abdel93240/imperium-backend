"""Objectifs Pulse (décision utilisateur 2026-10-22) : l'utilisateur écrit ses objectifs et décide de leur ordre.

Rang 1 = le plus important ; les rangs des objectifs en cours restent 1, 2, 3… sans trou. Atteint ou retiré, un
objectif sort du classement (gardé pour l'historique et la Weekly Review). Le programme d'entraînement et la diète
lisent `ranked_lines` : la liste dans l'ordre, rien d'autre. Aucune IA ici.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.pulse import PulseGoal
from app.schemas.pulse_goals import GoalCreate, GoalList, GoalOrder, GoalRead, GoalUpdate
from app.services.events.emitter import build_event

MAX_ACTIVE = 20


class GoalNotFoundError(ValueError):
    pass


class GoalStateError(ValueError):
    pass


def list_goals(db: Session, *, current_user: User) -> GoalList:
    rows = list(db.scalars(select(PulseGoal).where(PulseGoal.user_id == current_user.id,
                                                  PulseGoal.status.in_(("active", "achieved")))))
    active = sorted((r for r in rows if r.status == "active"), key=lambda r: r.rank)
    achieved = sorted((r for r in rows if r.status == "achieved"), key=lambda r: r.achieved_at or r.updated_at, reverse=True)
    return GoalList(items=[GoalRead.model_validate(r) for r in active], achieved=[GoalRead.model_validate(r) for r in achieved])


def create(db: Session, *, current_user: User, payload: GoalCreate, idempotency_key: str) -> tuple[GoalRead, bool]:
    existing = db.scalar(select(PulseGoal).where(PulseGoal.user_id == current_user.id,
                                                 PulseGoal.idempotency_key == idempotency_key))
    if existing is not None:
        return GoalRead.model_validate(existing), True
    count = db.scalar(select(func.count()).select_from(PulseGoal).where(
        PulseGoal.user_id == current_user.id, PulseGoal.status == "active")) or 0
    if count >= MAX_ACTIVE:
        raise GoalStateError(f"{MAX_ACTIVE} objectifs en cours au plus.")
    goal = PulseGoal(user_id=current_user.id, title=payload.title, notes=payload.notes or None, rank=count + 1,
                     status="active", idempotency_key=idempotency_key)
    db.add(goal)
    db.flush()
    _emit(db, current_user, goal, "added")
    db.refresh(goal)
    read = GoalRead.model_validate(goal)
    db.commit()
    return read, False


def update(db: Session, *, current_user: User, goal_id: UUID, payload: GoalUpdate) -> GoalRead:
    goal = _get(db, current_user, goal_id)
    if goal.status == "archived":
        raise GoalNotFoundError("Goal not found.")
    fields = payload.model_fields_set
    if "title" in fields and payload.title:
        goal.title = payload.title
    if "notes" in fields:
        goal.notes = payload.notes or None
    if payload.status and payload.status != goal.status:
        if payload.status == "achieved":
            goal.status, goal.achieved_at = "achieved", datetime.now(UTC)
            _close_gap(db, current_user)
            _emit(db, current_user, goal, "achieved")
        else:  # remis en cours : à la fin du classement
            goal.status, goal.achieved_at = "active", None
            goal.rank = _active_count(db, current_user, exclude=goal.id) + 1
            _emit(db, current_user, goal, "reopened")
    db.flush()
    db.refresh(goal)
    read = GoalRead.model_validate(goal)
    db.commit()
    return read


def reorder(db: Session, *, current_user: User, payload: GoalOrder) -> GoalList:
    active = {g.id: g for g in db.scalars(select(PulseGoal).where(PulseGoal.user_id == current_user.id,
                                                                  PulseGoal.status == "active"))}
    if set(payload.ids) != set(active) or len(payload.ids) != len(active):
        raise GoalStateError("The new order must list every goal in progress, once.")
    for rank, goal_id in enumerate(payload.ids, start=1):
        active[goal_id].rank = rank
    db.add(build_event(db, user_id=current_user.id, event_type="pulse.goals.reordered",
                       payload={"goal_ids": [str(i) for i in payload.ids]},
                       idempotency_key=f"pulse.goals.reordered.{current_user.id}.{datetime.now(UTC).timestamp()}",
                       source_app=SourceApp.pulse, privacy_level=PrivacyLevel.medium))
    db.commit()
    return list_goals(db, current_user=current_user)


def remove(db: Session, *, current_user: User, goal_id: UUID) -> None:
    """Retiré : sort de la liste et du classement, gardé pour l'historique."""
    goal = _get(db, current_user, goal_id)
    if goal.status == "archived":
        return
    was_active = goal.status == "active"
    goal.status = "archived"
    db.flush()
    if was_active:
        _close_gap(db, current_user)
    _emit(db, current_user, goal, "removed")
    db.commit()


def ranked_lines(db: Session, user: User) -> list[str]:
    """« 1. Abdos visibles (précision) » … : ce que lisent le programme et la diète."""
    return [f"{g.rank}. {g.title}" + (f" ({g.notes})" if g.notes else "")
            for g in list_goals(db, current_user=user).items]


def _close_gap(db: Session, user: User) -> None:
    active = db.scalars(select(PulseGoal).where(PulseGoal.user_id == user.id, PulseGoal.status == "active")
                        .order_by(PulseGoal.rank, PulseGoal.created_at))
    for rank, goal in enumerate(active, start=1):
        goal.rank = rank


def _active_count(db: Session, user: User, *, exclude: UUID) -> int:
    return db.scalar(select(func.count()).select_from(PulseGoal).where(
        PulseGoal.user_id == user.id, PulseGoal.status == "active", PulseGoal.id != exclude)) or 0


def _get(db: Session, user: User, goal_id: UUID) -> PulseGoal:
    goal = db.get(PulseGoal, goal_id)
    if goal is None or goal.user_id != user.id:
        raise GoalNotFoundError("Goal not found.")
    return goal


def _emit(db: Session, user: User, goal: PulseGoal, action: str) -> None:
    db.add(build_event(db, user_id=user.id, event_type="pulse.goal.updated",
                       payload={"goal_id": str(goal.id), "action": action, "rank": goal.rank},
                       idempotency_key=f"pulse.goal.updated.{goal.id}.{action}.{datetime.now(UTC).timestamp()}",
                       source_app=SourceApp.pulse, privacy_level=PrivacyLevel.medium))
