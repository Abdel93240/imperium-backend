"""Adhkar (doc 41 §11) : routines de dhikr et compteurs.

Une routine est toujours activée par l'utilisateur (les suggestions ne créent rien), 8 actives
au plus. Le compteur vit par période : le jour (Paris), la semaine ISO, ou chaque prière du
jour. Un appui validé ajoute `amount` ; clés distinctes = sommes, même clé = rejeu (hors
ligne, doc 41 §18). Le comptage à la voix porte sa confiance ; sous 0,8, l'utilisateur doit
avoir relu le nombre. Rien n'est jamais déduit, même après une prière marquée.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.path import PathAdhkarCount, PathAdhkarIncrement, PathAdhkarRoutine
from app.schemas.path_adhkar import (
    AdhkarCounterRead,
    AdhkarIncrementRequest,
    AdhkarResetRequest,
    AdhkarRoutineCreate,
    AdhkarRoutineListResponse,
    AdhkarRoutineRead,
    AdhkarRoutineUpdate,
    AdhkarRoutineWithCountRead,
    AdhkarSuggestionRead,
)
from app.services.events.emitter import build_event
from app.services.path.prayer import PRAYERS
from app.services.pulse import food_stock

PARIS = ZoneInfo("Europe/Paris")
MAX_ACTIVE = 8
LOW_CONFIDENCE = 0.8
SUGGESTIONS = (
    AdhkarSuggestionRead(label="Adhkar du matin", adhkar_type="morning", target_count=1, frequency="daily"),
    AdhkarSuggestionRead(label="Adhkar du soir", adhkar_type="evening", target_count=1, frequency="daily"),
    AdhkarSuggestionRead(label="Istighfar", adhkar_type="istighfar", target_count=100, frequency="daily"),
    AdhkarSuggestionRead(label="Salawat", adhkar_type="salawat", target_count=100, frequency="daily"),
    AdhkarSuggestionRead(label="Subhan Allah", adhkar_type="tasbih", target_count=33, frequency="per_prayer"),
    AdhkarSuggestionRead(label="Al hamdu lillah", adhkar_type="tahmid", target_count=33, frequency="per_prayer"),
    AdhkarSuggestionRead(label="Allahu akbar", adhkar_type="takbir", target_count=34, frequency="per_prayer"),
)


class AdhkarInputError(ValueError):
    pass


class AdhkarNotFoundError(ValueError):
    pass


class AdhkarStateError(ValueError):
    pass


class AdhkarIdempotencyConflictError(ValueError):
    pass


class AdhkarVersionConflictError(ValueError):
    def __init__(self, current: AdhkarRoutineRead) -> None:
        super().__init__("Cette routine a changé depuis ta lecture.")
        self.current = current


class AdhkarResetConflictError(ValueError):
    def __init__(self, current: AdhkarCounterRead) -> None:
        super().__init__("Le compteur a changé (appuis en attente) : vérifie avant de remettre à zéro.")
        self.current = current


def paris_today(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(PARIS).date()


def period_key(frequency: str, day: date, prayer: str | None) -> str:
    if frequency == "weekly":
        return f"week:{(day - timedelta(days=day.weekday())).isoformat()}"
    if frequency == "per_prayer":
        return f"{day.isoformat()}:{prayer}"
    return day.isoformat()


# ---------- routines ----------

def suggestions() -> list[AdhkarSuggestionRead]:
    return list(SUGGESTIONS)


def list_routines(db: Session, *, current_user: User, day: date) -> AdhkarRoutineListResponse:
    routines = list(
        db.scalars(
            select(PathAdhkarRoutine).where(PathAdhkarRoutine.user_id == current_user.id)
            .order_by(PathAdhkarRoutine.active.desc(), PathAdhkarRoutine.created_at.asc())
        )
    )
    keys = {routine.id: _keys(routine, day) for routine in routines}
    counts = {
        (row.routine_id, row.period_key): row.count
        for row in db.scalars(
            select(PathAdhkarCount).where(
                PathAdhkarCount.user_id == current_user.id,
                PathAdhkarCount.period_key.in_([key for values in keys.values() for key in values] or [""]),
            )
        )
    }
    items = [
        AdhkarRoutineWithCountRead(
            **AdhkarRoutineRead.model_validate(routine).model_dump(),
            counters=[_counter(routine, key, counts.get((routine.id, key), 0)) for key in keys[routine.id]],
        )
        for routine in routines
    ]
    return AdhkarRoutineListResponse(day=day, items=items)


def create_routine(
    db: Session, *, current_user: User, payload: AdhkarRoutineCreate, idempotency_key: str
) -> tuple[AdhkarRoutineRead, bool]:
    fingerprint = food_stock.request_hash("path.adhkar.routine", payload.model_dump(mode="json"))
    existing = db.scalar(
        select(PathAdhkarRoutine).where(
            PathAdhkarRoutine.user_id == current_user.id, PathAdhkarRoutine.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise AdhkarIdempotencyConflictError("Idempotency key already used with a different routine.")
        return AdhkarRoutineRead.model_validate(existing), True
    _check_active_limit(db, current_user)
    routine = PathAdhkarRoutine(
        user_id=current_user.id, label=payload.label, adhkar_type=payload.adhkar_type, target_count=payload.target_count,
        frequency=payload.frequency, active=True, version=1, idempotency_key=idempotency_key, request_hash=fingerprint,
    )
    db.add(routine)
    db.flush()
    db.refresh(routine)
    _routine_event(db, current_user, routine, "created")
    read = AdhkarRoutineRead.model_validate(routine)
    db.commit()
    return read, False


def update_routine(
    db: Session, *, current_user: User, routine_id: UUID, payload: AdhkarRoutineUpdate, idempotency_key: str,
    request_path: str,
) -> AdhkarRoutineRead:
    fingerprint = food_stock.request_hash(
        "path.adhkar.routine.update", {"routine_id": str(routine_id), **payload.model_dump(mode="json", exclude_unset=True)}
    )
    previous = food_stock.replay(db, current_user, idempotency_key, fingerprint, request_path, AdhkarRoutineRead)
    if previous is not None:
        return previous
    routine = _get(db, current_user, routine_id)
    if routine.version != payload.version:
        raise AdhkarVersionConflictError(AdhkarRoutineRead.model_validate(routine))
    changes = payload.model_dump(exclude_unset=True, exclude={"version"})
    if any(changes.get(field, "") is None for field in ("label", "target_count", "frequency", "active")):
        raise AdhkarInputError("Un champ envoyé ne peut pas être vide.")
    if "label" in changes:
        changes["label"] = changes["label"].strip()
        if not changes["label"]:
            raise AdhkarInputError("Le libellé est obligatoire.")
    if changes.get("active") and not routine.active:
        _check_active_limit(db, current_user)
    for field, value in changes.items():
        setattr(routine, field, value)
    routine.version += 1
    db.flush()
    db.refresh(routine)
    _routine_event(db, current_user, routine, "updated")
    read = AdhkarRoutineRead.model_validate(routine)
    food_stock.remember(db, current_user, idempotency_key, "PATCH", request_path, fingerprint, 200, read)
    db.commit()
    return read


def delete_routine(db: Session, *, current_user: User, routine_id: UUID) -> None:
    """Suppression réelle de la routine et de ses compteurs."""
    routine = _get(db, current_user, routine_id)
    _routine_event(db, current_user, routine, "deleted")
    db.delete(routine)
    db.commit()


# ---------- compteurs ----------

def increment(
    db: Session, *, current_user: User, routine_id: UUID, payload: AdhkarIncrementRequest, idempotency_key: str,
    now: datetime | None = None,
) -> tuple[AdhkarCounterRead, bool]:
    fingerprint = food_stock.request_hash(
        "path.adhkar.increment", {"routine_id": str(routine_id), **payload.model_dump(mode="json")}
    )
    existing = db.scalar(
        select(PathAdhkarIncrement).where(
            PathAdhkarIncrement.user_id == current_user.id, PathAdhkarIncrement.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise AdhkarIdempotencyConflictError("Idempotency key already used with a different increment.")
        return AdhkarCounterRead.model_validate(existing.result), True
    if payload.source == "voice" and payload.confidence < LOW_CONFIDENCE and not payload.validated:
        raise AdhkarInputError("Comptage à la voix peu sûr : vérifie le nombre puis valide-le.")
    routine = _get(db, current_user, routine_id)
    if not routine.active:
        raise AdhkarStateError("Cette routine est en pause.")
    key = _period(routine, payload.day, payload.prayer, now)
    counter = _counter_row(db, current_user, routine, key)
    counter.count += payload.amount
    reached = counter.count >= routine.target_count
    first_time = reached and counter.target_reached_at is None
    if first_time:
        counter.target_reached_at = now or datetime.now(UTC)
    read = _counter(routine, key, counter.count)
    db.add(
        PathAdhkarIncrement(
            user_id=current_user.id, routine_id=routine.id, period_key=key, amount=payload.amount, source=payload.source,
            idempotency_key=idempotency_key, request_hash=fingerprint, result=read.model_dump(mode="json"),
        )
    )
    db.flush()
    db.add(
        build_event(
            db, user_id=current_user.id, event_type="path.adhkar.incremented",
            payload={"routine_id": str(routine.id), "adhkar_type": routine.adhkar_type, "period_key": key,
                     "amount": payload.amount, "count": counter.count, "target_reached": first_time,
                     "source": payload.source},
            idempotency_key=f"path.adhkar.incremented.{idempotency_key}", source_app=SourceApp.path,
            privacy_level=PrivacyLevel.high,
        )
    )
    db.commit()
    return read, False


def reset(
    db: Session, *, current_user: User, routine_id: UUID, payload: AdhkarResetRequest, idempotency_key: str,
    request_path: str, now: datetime | None = None,
) -> AdhkarCounterRead:
    fingerprint = food_stock.request_hash("path.adhkar.reset", {"routine_id": str(routine_id), **payload.model_dump(mode="json")})
    previous = food_stock.replay(db, current_user, idempotency_key, fingerprint, request_path, AdhkarCounterRead)
    if previous is not None:
        return previous
    routine = _get(db, current_user, routine_id)
    key = _period(routine, payload.day, payload.prayer, now)
    counter = _counter_row(db, current_user, routine, key)
    if counter.count != payload.expected_count:
        raise AdhkarResetConflictError(_counter(routine, key, counter.count))
    counter.count, counter.target_reached_at, counter.reset_at = 0, None, now or datetime.now(UTC)
    db.flush()
    db.add(
        build_event(
            db, user_id=current_user.id, event_type="path.adhkar.reset",
            payload={"routine_id": str(routine.id), "period_key": key, "previous_count": payload.expected_count},
            idempotency_key=f"path.adhkar.reset.{idempotency_key}", source_app=SourceApp.path,
            privacy_level=PrivacyLevel.high,
        )
    )
    read = _counter(routine, key, 0)
    food_stock.remember(db, current_user, idempotency_key, "POST", request_path, fingerprint, 200, read)
    db.commit()
    return read


# ---------- internes ----------

def _period(routine: PathAdhkarRoutine, day: date | None, prayer: str | None, now: datetime | None) -> str:
    today = paris_today(now)
    day = day or today
    if day > today:
        raise AdhkarInputError("Ce jour n'est pas encore arrivé.")
    if routine.frequency == "per_prayer" and prayer is None:
        raise AdhkarInputError("Choisis la prière de ce dhikr.")
    if routine.frequency != "per_prayer" and prayer is not None:
        raise AdhkarInputError("Cette routine ne se compte pas par prière.")
    return period_key(routine.frequency, day, prayer)


def _counter_row(db: Session, user: User, routine: PathAdhkarRoutine, key: str) -> PathAdhkarCount:
    query = select(PathAdhkarCount).where(PathAdhkarCount.routine_id == routine.id, PathAdhkarCount.period_key == key)
    counter = db.scalar(query.with_for_update())
    if counter is None:
        counter = PathAdhkarCount(user_id=user.id, routine_id=routine.id, period_key=key, count=0)
        try:
            with db.begin_nested():
                db.add(counter)
                db.flush()
        except IntegrityError:  # créé en même temps par un autre appui
            counter = db.scalar(query.with_for_update())
    return counter


def _keys(routine: PathAdhkarRoutine, day: date) -> list[str]:
    if routine.frequency == "per_prayer":
        return [period_key("per_prayer", day, prayer) for prayer in PRAYERS]
    return [period_key(routine.frequency, day, None)]


def _counter(routine: PathAdhkarRoutine, key: str, count: int) -> AdhkarCounterRead:
    return AdhkarCounterRead(
        routine_id=routine.id, period_key=key, count=count, target_count=routine.target_count,
        target_reached=count >= routine.target_count,
    )


def _check_active_limit(db: Session, user: User) -> None:
    active = db.scalar(
        select(func.count()).select_from(
            select(PathAdhkarRoutine.id).where(PathAdhkarRoutine.user_id == user.id, PathAdhkarRoutine.active.is_(True))
            .with_for_update().subquery()
        )
    ) or 0
    if active >= MAX_ACTIVE:
        raise AdhkarStateError(f"{MAX_ACTIVE} routines actives au plus : mets-en une en pause d'abord.")


def _get(db: Session, user: User, routine_id: UUID) -> PathAdhkarRoutine:
    routine = db.scalar(
        select(PathAdhkarRoutine).where(PathAdhkarRoutine.id == routine_id, PathAdhkarRoutine.user_id == user.id)
        .with_for_update()
    )
    if routine is None:
        raise AdhkarNotFoundError("Routine introuvable.")
    return routine


def _routine_event(db: Session, user: User, routine: PathAdhkarRoutine, action: str) -> None:
    db.add(
        build_event(
            db, user_id=user.id, event_type="path.routine.updated",
            payload={"routine_id": str(routine.id), "action": action, "adhkar_type": routine.adhkar_type,
                     "active": routine.active, "target_count": routine.target_count, "frequency": routine.frequency},
            idempotency_key=f"path.routine.{action}.{routine.id}.v{routine.version}", source_app=SourceApp.path,
            privacy_level=PrivacyLevel.high,
        )
    )
