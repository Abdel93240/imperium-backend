"""Walker du docket — phase P4 du WR (spec WR §9 P4, carte V18 ACT-WR-06). Code pur.

Une marche par session WR lancée : l'utilisateur choisit le mode (full : tous les types ; light :
rouges, décisions forcées, contradictions, deltas de plan), le budget en minutes est figé au départ
depuis `wr.budget_min`. next_item() sert l'item ouvert le plus prioritaire du mode (décisions
forcées d'abord) ; un item reporté pendant la marche n'est plus resservi. Budget épuisé : seuls
les rouges et les décisions forcées sont encore servis, le reste porte sans pénalité. Les
décisions passent par la route du docket (explication obligatoire pour un refus ou une
modification). Lecture seule : servir un item n'écrit rien.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.wr import WrDocketItem, WrWalk
from app.schemas.wr import WalkNextResponse, WalkRead
from app.services.events.emitter import build_event
from app.services.params import get_parameter
from app.services.wr import digest, docket

DEFAULT_BUDGET = {"full": 45, "light": 15}


class WalkStateError(RuntimeError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def start_walk(db: Session, *, current_user: User, mode: str, now: datetime | None = None) -> tuple[WrWalk, bool]:
    """Démarre la marche de la session WR ouverte ; déjà démarrée, la rend telle quelle (mode inchangé)."""
    session = digest._open_session(db, current_user)
    if session is None:
        raise WalkStateError("No open weekly review: launch it before walking the docket.", "WR_NOT_OPEN")
    existing = db.scalar(select(WrWalk).where(WrWalk.review_session_id == session.id))
    if existing is not None:
        return existing, False
    now = now or datetime.now(UTC)
    budgets = {**DEFAULT_BUDGET, **(get_parameter(db, "wr.budget_min", default=DEFAULT_BUDGET) or {})}
    walk = WrWalk(user_id=current_user.id, review_session_id=session.id, mode=mode,
                  budget_min=int(budgets[mode]), started_at=now)
    db.add(walk)
    db.flush()
    _emit(db, current_user, "planning.wr_walk.started", walk, {"mode": mode, "budget_min": walk.budget_min}, now)
    db.commit()
    return walk, True


def next_item(db: Session, *, current_user: User, now: datetime | None = None) -> WalkNextResponse:
    walk = _current(db, current_user)
    now = now or datetime.now(UTC)
    elapsed = max(int((now - walk.started_at).total_seconds() // 60), 0)
    exhausted = elapsed >= walk.budget_min
    candidates = [
        item for item in docket.list_items(db, current_user=current_user, mode=walk.mode, now=now)
        if item.status in docket.OPEN_STATUSES
        and not (item.status == "deferred" and item.decided_at is not None and item.decided_at >= walk.started_at)
        and (not exhausted or item.severity == "red" or item.force_decision)
    ]
    return WalkNextResponse(
        walk=WalkRead.model_validate(walk), item=candidates[0] if candidates else None, elapsed_min=elapsed,
        remaining_min=max(walk.budget_min - elapsed, 0), budget_exhausted=exhausted,
        remaining_items=len(candidates), decided_in_walk=_decided_since(db, current_user, walk.started_at),
    )


def close_walk(db: Session, *, current_user: User, now: datetime | None = None) -> WrWalk:
    """Clôt la marche ; les items non tranchés portent. Déjà close, elle est rendue telle quelle."""
    walk = _current(db, current_user, allow_closed=True)
    if walk.closed_at is None:
        now = now or datetime.now(UTC)
        walk.closed_at = now
        db.flush()
        carried = db.scalar(select(func.count()).select_from(WrDocketItem).where(
            WrDocketItem.user_id == current_user.id, WrDocketItem.status.in_(docket.OPEN_STATUSES)))
        _emit(db, current_user, "planning.wr_walk.closed", walk,
              {"mode": walk.mode, "elapsed_min": int((now - walk.started_at).total_seconds() // 60),
               "decided": _decided_since(db, current_user, walk.started_at), "carried": carried}, now)
        db.commit()
    return walk


def walk_mode(db: Session, *, review_session_id) -> str | None:
    return db.scalar(select(WrWalk.mode).where(WrWalk.review_session_id == review_session_id))


def _current(db: Session, current_user: User, *, allow_closed: bool = False) -> WrWalk:
    session = digest._open_session(db, current_user)
    if session is None:
        raise WalkStateError("No open weekly review.", "WR_NOT_OPEN")
    walk = db.scalar(select(WrWalk).where(WrWalk.review_session_id == session.id))
    if walk is None:
        raise WalkStateError("The docket walk has not been started.", "WALK_NOT_STARTED")
    if walk.closed_at is not None and not allow_closed:
        raise WalkStateError("The docket walk is closed.", "WALK_CLOSED")
    return walk


def _decided_since(db: Session, current_user: User, since: datetime) -> int:
    return db.scalar(select(func.count()).select_from(WrDocketItem).where(
        WrDocketItem.user_id == current_user.id, WrDocketItem.decided_at >= since,
        WrDocketItem.autoaccept_class_id.is_(None) | (WrDocketItem.item_type == "autoaccept_spotcheck"),
        WrDocketItem.status.in_(("validated", "refused", "deferred", "archived"))))


def _emit(db: Session, current_user: User, event_type: str, walk: WrWalk, extra: dict, now: datetime) -> None:
    db.add(build_event(
        db, user_id=current_user.id, event_type=event_type,
        payload={"walk_id": str(walk.id), "review_session_id": str(walk.review_session_id), **extra},
        idempotency_key=f"{event_type}.{walk.id}", source_app=SourceApp.imperium,
        privacy_level=PrivacyLevel.low, occurred_at=now,
    ))
    db.flush()
