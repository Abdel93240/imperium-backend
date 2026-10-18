"""Invocations à lire (doc 41 §11-bis) : bibliothèque par situation, favoris, matin et soir.

Distinct des compteurs de dhikr (§11) : ici on lit, on ne compte pas. Les textes viennent de
l'utilisateur, qui les valide (directement ou après une proposition de « Nourrir l'IA », doc 70) ;
la source est obligatoire, l'IA n'est jamais la source. L'audio n'est qu'un lien https, jamais
téléchargé. La liste du matin et du soir se coche par jour de Paris. Le rappel quotidien
(§11-bis.2) attend une base de textes vérifiés : pas dans ce lot. Événements sans texte.
"""

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.path import PathInvocation, PathInvocationCheck
from app.schemas.path_invocations import (
    DailyBlockRead,
    DailyInvocationRead,
    DailyInvocationsResponse,
    InvocationCheckRequest,
    InvocationCreate,
    InvocationListResponse,
    InvocationRead,
    InvocationUpdate,
)
from app.services.events.emitter import build_event
from app.services.path.fasting import paris_today
from app.services.pulse import food_stock


class InvocationNotFoundError(ValueError):
    pass


class InvocationInputError(ValueError):
    pass


class InvocationIdempotencyConflictError(ValueError):
    pass


class InvocationVersionConflictError(ValueError):
    def __init__(self, current: InvocationRead) -> None:
        super().__init__("Cette invocation a changé depuis ta lecture.")
        self.current = current


def list_invocations(
    db: Session, *, current_user: User, situation: str | None = None, favorites: bool = False
) -> InvocationListResponse:
    query = select(PathInvocation).where(PathInvocation.user_id == current_user.id)
    if situation is not None:
        query = query.where(PathInvocation.situation == situation)
    if favorites:
        query = query.where(PathInvocation.is_favorite.is_(True))
    rows = db.scalars(query.order_by(PathInvocation.situation, PathInvocation.created_at, PathInvocation.id))
    return InvocationListResponse(items=[InvocationRead.model_validate(row) for row in rows])


def create_invocation(
    db: Session, *, current_user: User, payload: InvocationCreate, idempotency_key: str
) -> tuple[InvocationRead, bool]:
    fingerprint = food_stock.request_hash("path.invocation", payload.model_dump(mode="json"))
    existing = db.scalar(
        select(PathInvocation).where(
            PathInvocation.user_id == current_user.id, PathInvocation.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise InvocationIdempotencyConflictError("Idempotency key already used with a different invocation.")
        return InvocationRead.model_validate(existing), True
    row = PathInvocation(user_id=current_user.id, **payload.model_dump(), version=1, idempotency_key=idempotency_key,
                         request_hash=fingerprint)
    db.add(row)
    db.flush()
    db.refresh(row)
    _event(db, current_user, row, "added")
    read = InvocationRead.model_validate(row)
    db.commit()
    return read, False


def update_invocation(
    db: Session, *, current_user: User, invocation_id: UUID, payload: InvocationUpdate
) -> InvocationRead:
    row = _get(db, current_user, invocation_id, lock=True)
    if row.version != payload.version:
        raise InvocationVersionConflictError(InvocationRead.model_validate(row))
    changes = payload.model_dump(exclude_unset=True, exclude={"version"})
    for field in ("arabic_text", "translation_fr", "source"):
        if field in changes:
            value = (changes[field] or "").strip()
            if not value:
                raise InvocationInputError(f"{field} est obligatoire.")
            changes[field] = value
    if "situation" in changes and changes["situation"] is None:
        raise InvocationInputError("situation est obligatoire.")
    period = changes.get("daily_period", row.daily_period)
    order = changes.get("daily_order", row.daily_order)
    if (period is None) != (order is None):
        raise InvocationInputError("daily_period et daily_order vont ensemble.")
    if "audio_url" in changes:
        changes["audio_url"] = (changes["audio_url"] or "").strip() or None
    for field, value in changes.items():
        setattr(row, field, value)
    row.version += 1
    db.flush()
    db.refresh(row)
    _event(db, current_user, row, "updated")
    read = InvocationRead.model_validate(row)
    db.commit()
    return read


def set_favorite(db: Session, *, current_user: User, invocation_id: UUID, is_favorite: bool) -> InvocationRead:
    """Pose ou retire le favori ; renvoyer la même valeur ne change rien (rejeu hors ligne sans clé)."""
    row = _get(db, current_user, invocation_id, lock=True)
    if row.is_favorite != is_favorite:
        row.is_favorite = is_favorite
        row.version += 1
        db.flush()
        db.refresh(row)
        _event(db, current_user, row, "favorite" if is_favorite else "unfavorite")
    read = InvocationRead.model_validate(row)
    db.commit()
    return read


def delete_invocation(db: Session, *, current_user: User, invocation_id: UUID) -> None:
    """Suppression réelle ; ses coches partent avec elle."""
    row = _get(db, current_user, invocation_id)
    _event(db, current_user, row, "removed")
    db.delete(row)
    db.commit()


def daily(db: Session, *, current_user: User, day: date | None = None) -> DailyInvocationsResponse:
    day = day or paris_today()
    rows = list(
        db.scalars(
            select(PathInvocation)
            .where(PathInvocation.user_id == current_user.id, PathInvocation.daily_period.is_not(None))
            .order_by(PathInvocation.daily_order, PathInvocation.created_at, PathInvocation.id)
        )
    )
    checks = {
        check.invocation_id: check.checked_at
        for check in db.scalars(
            select(PathInvocationCheck).where(PathInvocationCheck.user_id == current_user.id, PathInvocationCheck.day == day)
        )
    }
    blocks = {}
    for period in ("morning", "evening"):
        items = [
            DailyInvocationRead(invocation=InvocationRead.model_validate(row), checked=row.id in checks,
                                checked_at=checks.get(row.id))
            for row in rows
            if row.daily_period == period
        ]
        blocks[period] = DailyBlockRead(items=items, done=sum(item.checked for item in items), total=len(items))
    return DailyInvocationsResponse(day=day, **blocks)


def check(
    db: Session, *, current_user: User, invocation_id: UUID, payload: InvocationCheckRequest, now: datetime | None = None
) -> DailyInvocationsResponse:
    """Coche ou décoche une invocation du matin/soir pour un jour ; idempotent."""
    now = now or datetime.now(UTC)
    day = payload.day or paris_today()
    if day > paris_today():
        raise InvocationInputError("On ne coche pas un jour à venir.")
    row = _get(db, current_user, invocation_id)
    if row.daily_period is None:
        raise InvocationInputError("Cette invocation n'est pas dans la liste du matin ou du soir.")
    existing = db.scalar(
        select(PathInvocationCheck).where(PathInvocationCheck.invocation_id == row.id, PathInvocationCheck.day == day)
    )
    if payload.checked and existing is None:
        db.add(PathInvocationCheck(user_id=current_user.id, invocation_id=row.id, day=day, checked_at=now))
    elif not payload.checked and existing is not None:
        db.execute(delete(PathInvocationCheck).where(PathInvocationCheck.id == existing.id))
    db.flush()
    response = daily(db, current_user=current_user, day=day)
    db.commit()
    return response


def _get(db: Session, user: User, invocation_id: UUID, *, lock: bool = False) -> PathInvocation:
    query = select(PathInvocation).where(PathInvocation.id == invocation_id, PathInvocation.user_id == user.id)
    row = db.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise InvocationNotFoundError("Invocation introuvable.")
    return row


def _event(db: Session, user: User, row: PathInvocation, action: str) -> None:
    db.add(
        build_event(
            db, user_id=user.id, event_type="path.invocation.updated",
            payload={"invocation_id": str(row.id), "action": action, "situation": row.situation,
                     "daily_period": row.daily_period, "is_favorite": row.is_favorite},
            idempotency_key=f"path.invocation.{action}.{row.id}.v{row.version}", source_app=SourceApp.path,
            privacy_level=PrivacyLevel.high,
        )
    )
