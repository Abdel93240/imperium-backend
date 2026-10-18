"""Mosquées enregistrées (PAT-09, doc 41 §6.3).

Saisie manuelle (nom, adresse, coordonnées, identifiant MAWAQIT facultatif) ; une mosquée par
défaut au plus. Elle sert de référence aux horaires : cache MAWAQIT s'il existe, sinon calcul
local à ses coordonnées (Paris sans coordonnées). La recherche et la synchronisation MAWAQIT
passent par le réseau : pas dans ce lot. Événements sans nom ni adresse.
"""

from datetime import UTC, date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.path import PathRegisteredMosque
from app.schemas.path_mosques import MosqueCreate, MosqueDetailRead, MosqueListResponse, MosqueRead, MosqueUpdate
from app.services.events.emitter import build_event
from app.services.path.fasting import paris_today
from app.services.path.dashboard import qibla_from
from app.services.path.prayer import (
    DEFAULT_TZ,
    calculation_config,
    cached_mawaqit_row,
    compute_prayer_times_utc,
    mawaqit_quality,
    parse_mawaqit_times,
    prayer_times,
)
from app.services.pulse import food_stock


class MosqueNotFoundError(ValueError):
    pass


class MosqueInputError(ValueError):
    pass


class MosqueIdempotencyConflictError(ValueError):
    pass


class MosqueVersionConflictError(ValueError):
    def __init__(self, current: MosqueRead) -> None:
        super().__init__("Cette mosquée a changé depuis ta lecture.")
        self.current = current


def list_mosques(db: Session, *, current_user: User) -> MosqueListResponse:
    rows = db.scalars(
        select(PathRegisteredMosque).where(PathRegisteredMosque.user_id == current_user.id)
        .order_by(PathRegisteredMosque.is_default.desc(), PathRegisteredMosque.added_at.asc())
    )
    _, source = prayer_times(db, paris_today(), user_id=current_user.id)
    return MosqueListResponse(items=[MosqueRead.model_validate(row) for row in rows], times_source=source)


QUALITY_MESSAGES = {
    "stale": "Horaires MAWAQIT de plus de 24 h : à vérifier.",
    "expired": "Horaires MAWAQIT de plus de 48 h : horaires calculés affichés.",
    "missing": "Pas d'horaires MAWAQIT en cache pour ce jour : horaires calculés affichés.",
}


def mosque_detail(
    db: Session, *, current_user: User, mosque_id: UUID, day: date | None = None, now: datetime | None = None
) -> MosqueDetailRead:
    """PAT-08 (doc 59 §16.8) : cache MAWAQIT avec sa qualité, calcul local aux coordonnées, qibla.

    Lecture seule ; la synchronisation MAWAQIT passe par le réseau (pas encore).
    """
    row = db.scalar(
        select(PathRegisteredMosque).where(PathRegisteredMosque.id == mosque_id, PathRegisteredMosque.user_id == current_user.id)
    )
    if row is None:
        raise MosqueNotFoundError("Mosquée introuvable.")
    now = now or datetime.now(UTC)
    day = day or paris_today()
    zone = ZoneInfo(DEFAULT_TZ)
    config = calculation_config(db, current_user.id)
    if row.latitude is not None:
        origin, location = (float(row.latitude), float(row.longitude)), "mosque"
    else:
        origin, location = (config.latitude, config.longitude), config.location_source
    calculated = {
        prayer: _hhmm(moment.astimezone(zone))
        for prayer, moment in compute_prayer_times_utc(day, *origin, method=config.method, madhhab=config.madhhab).items()
    }
    cache = cached_mawaqit_row(db, row, day)
    quality = mawaqit_quality(cache.fetched_at, now) if cache is not None else "missing"
    mawaqit = (
        {prayer: _hhmm(moment) for prayer, moment in parse_mawaqit_times(cache.prayer_times, day, zone).items()}
        if cache is not None
        else None
    )
    primary = mawaqit is not None and quality != "expired"
    return MosqueDetailRead(
        mosque=MosqueRead.model_validate(row), day=day, times=mawaqit if primary else calculated,
        times_source="mawaqit" if primary else "calculated", mawaqit_times=mawaqit, mawaqit_data_quality=quality,
        mawaqit_fetched_at=cache.fetched_at if cache is not None else None, calculated_times=calculated,
        calculation_location=location,
        qibla_direction_degrees=qibla_from(origin) if row.latitude is not None else None,
        message=QUALITY_MESSAGES.get(quality),
    )


def _hhmm(moment: datetime) -> str:
    return moment.strftime("%H:%M")


def create_mosque(db: Session, *, current_user: User, payload: MosqueCreate, idempotency_key: str) -> tuple[MosqueRead, bool]:
    fingerprint = food_stock.request_hash("path.mosque", payload.model_dump(mode="json"))
    existing = db.scalar(
        select(PathRegisteredMosque).where(
            PathRegisteredMosque.user_id == current_user.id, PathRegisteredMosque.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise MosqueIdempotencyConflictError("Idempotency key already used with a different mosque.")
        return MosqueRead.model_validate(existing), True
    if payload.is_default:
        _clear_default(db, current_user)
    row = PathRegisteredMosque(
        user_id=current_user.id, name=payload.name.strip(), address=(payload.address or "").strip() or None,
        latitude=payload.latitude, longitude=payload.longitude, mawaqit_id=(payload.mawaqit_id or "").strip() or None,
        is_default=payload.is_default, version=1, idempotency_key=idempotency_key, request_hash=fingerprint,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    _event(db, current_user, row, "added")
    read = MosqueRead.model_validate(row)
    db.commit()
    return read, False


def update_mosque(
    db: Session, *, current_user: User, mosque_id: UUID, payload: MosqueUpdate, idempotency_key: str, request_path: str
) -> MosqueRead:
    fingerprint = food_stock.request_hash(
        "path.mosque.update", {"mosque_id": str(mosque_id), **payload.model_dump(mode="json", exclude_unset=True)}
    )
    previous = food_stock.replay(db, current_user, idempotency_key, fingerprint, request_path, MosqueRead)
    if previous is not None:
        return previous
    row = _get(db, current_user, mosque_id)
    if row.version != payload.version:
        raise MosqueVersionConflictError(MosqueRead.model_validate(row))
    changes = payload.model_dump(exclude_unset=True, exclude={"version"})
    if "name" in changes and (changes["name"] is None or not changes["name"].strip()):
        raise MosqueInputError("Le nom est obligatoire.")
    latitude, longitude = changes.get("latitude", row.latitude), changes.get("longitude", row.longitude)
    if (latitude is None) != (longitude is None):
        raise MosqueInputError("Latitude et longitude vont ensemble.")
    if changes.get("is_default"):
        _clear_default(db, current_user, keep=row.id)
    if changes.get("is_default") is None:
        changes.pop("is_default", None)
    for field in ("name", "address", "mawaqit_id"):
        if field in changes:
            changes[field] = (changes[field] or "").strip() or None
    for field, value in changes.items():
        setattr(row, field, value)
    row.version += 1
    db.flush()
    db.refresh(row)
    _event(db, current_user, row, "updated")
    read = MosqueRead.model_validate(row)
    food_stock.remember(db, current_user, idempotency_key, "PATCH", request_path, fingerprint, 200, read)
    db.commit()
    return read


def delete_mosque(db: Session, *, current_user: User, mosque_id: UUID) -> None:
    """Suppression réelle ; le cache MAWAQIT de la mosquée part avec elle."""
    row = _get(db, current_user, mosque_id)
    _event(db, current_user, row, "removed")
    db.delete(row)
    db.commit()


def _get(db: Session, user: User, mosque_id: UUID) -> PathRegisteredMosque:
    row = db.scalar(
        select(PathRegisteredMosque).where(PathRegisteredMosque.id == mosque_id, PathRegisteredMosque.user_id == user.id)
        .with_for_update()
    )
    if row is None:
        raise MosqueNotFoundError("Mosquée introuvable.")
    return row


def _clear_default(db: Session, user: User, keep: UUID | None = None) -> None:
    query = update(PathRegisteredMosque).where(PathRegisteredMosque.user_id == user.id, PathRegisteredMosque.is_default.is_(True))
    if keep is not None:
        query = query.where(PathRegisteredMosque.id != keep)
    db.execute(query.values(is_default=False, version=PathRegisteredMosque.version + 1))
    db.flush()


def _event(db: Session, user: User, row: PathRegisteredMosque, action: str) -> None:
    db.add(
        build_event(
            db, user_id=user.id, event_type="path.mosque.updated",
            payload={"mosque_id": str(row.id), "action": action, "is_default": row.is_default,
                     "has_coordinates": row.latitude is not None},
            idempotency_key=f"path.mosque.{action}.{row.id}.v{row.version}", source_app=SourceApp.path,
            privacy_level=PrivacyLevel.very_high,
        )
    )
