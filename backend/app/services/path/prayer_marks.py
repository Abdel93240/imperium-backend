"""Marquage des prières (PAT-02, doc 41 §7).

Seule une action explicite de l'utilisateur pose un statut : jamais de déduction depuis
l'heure, le lieu ou le téléphone. Une ligne par prière et par jour ; effacer le statut
supprime la ligne. Changer un statut déjà posé demande la version lue (`base_version`) :
sinon conflit, jamais d'écrasement silencieux (doc 41 §18).

Les événements portent la prière, le jour et le statut ; jamais la note.
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.path import PathPrayerLog
from app.schemas.path_worship import PrayerClearRequest, PrayerDayRead, PrayerMarkRequest, PrayerRead
from app.services.events.emitter import build_event
from app.services.path.prayer import PRAYERS, prayer_times
from app.services.pulse import food_stock

PARIS = ZoneInfo("Europe/Paris")
CLOCK_SKEW = timedelta(minutes=5)
EVENT_BY_STATUS = {"accomplished": "path.prayer.logged", "not_marked_as_accomplished": "path.prayer.not_marked"}


class PrayerInputError(ValueError):
    pass


class PrayerNotFoundError(ValueError):
    pass


class PrayerStatusConflictError(ValueError):
    def __init__(self, current: PrayerRead) -> None:
        super().__init__("Le statut de cette prière a changé depuis ta lecture.")
        self.current = current


def day_view(db: Session, *, current_user: User, day: date) -> PrayerDayRead:
    adhans, source = prayer_times(db, day, user_id=current_user.id)
    logs = {
        log.prayer_name: log
        for log in db.scalars(
            select(PathPrayerLog).where(PathPrayerLog.user_id == current_user.id, PathPrayerLog.prayer_date == day)
        )
    }
    return PrayerDayRead(
        day=day, times_source=source, prayers=[_read(name, day, adhans[name], logs.get(name)) for name in PRAYERS]
    )


def mark_prayer(
    db: Session,
    *,
    current_user: User,
    prayer_name: str,
    payload: PrayerMarkRequest,
    idempotency_key: str,
    request_path: str,
    now: datetime | None = None,
) -> tuple[PrayerRead, bool]:
    fingerprint = food_stock.request_hash(
        "path.prayer.mark", {"prayer_name": prayer_name, **payload.model_dump(mode="json")}
    )
    previous = food_stock.replay(db, current_user, idempotency_key, fingerprint, request_path, PrayerRead)
    if previous is not None:
        return previous, True
    now = now or datetime.now(UTC)
    adhans, _ = prayer_times(db, payload.prayer_date, user_id=current_user.id)
    adhan_at = adhans[prayer_name]
    if payload.prayer_date > now.astimezone(PARIS).date():
        raise PrayerInputError("Ce jour n'est pas encore arrivé.")
    prayed_at = None
    if payload.status == "accomplished":
        prayed_at = payload.prayed_at or now
        if prayed_at > now + CLOCK_SKEW:
            raise PrayerInputError("L'heure de la prière ne peut pas être dans le futur.")
    else:
        if payload.prayed_at is not None:
            raise PrayerInputError("Une heure de prière n'a de sens que pour une prière accomplie.")
        if adhan_at > now:
            raise PrayerInputError("Cette prière n'est pas encore arrivée.")
    note = (payload.note or "").strip() or None
    log = _get(db, current_user, payload.prayer_date, prayer_name)
    previous_status = log.status if log is not None else None
    if log is None:
        log = PathPrayerLog(
            user_id=current_user.id, prayer_date=payload.prayer_date, prayer_name=prayer_name, status=payload.status,
            prayed_at=prayed_at, note=note, version=1,
        )
        db.add(log)
    elif log.status == payload.status:
        read = _read(prayer_name, payload.prayer_date, adhan_at, log)
        food_stock.remember(db, current_user, idempotency_key, "POST", request_path, fingerprint, 200, read)
        db.commit()
        return read, False
    elif payload.base_version != log.version:
        raise PrayerStatusConflictError(_read(prayer_name, payload.prayer_date, adhan_at, log))
    else:
        log.status, log.prayed_at, log.note, log.version = payload.status, prayed_at, note, log.version + 1
    db.flush()
    db.refresh(log)
    db.add(
        build_event(
            db, user_id=current_user.id, event_type=EVENT_BY_STATUS[log.status],
            payload={"prayer_log_id": str(log.id), "prayer_name": prayer_name, "prayer_date": log.prayer_date.isoformat(),
                     "status": log.status, "previous_status": previous_status, "source": "user_action"},
            idempotency_key=f"path.prayer.{log.id}.v{log.version}", source_app=SourceApp.path,
            privacy_level=PrivacyLevel.high,
        )
    )
    read = _read(prayer_name, payload.prayer_date, adhan_at, log)
    food_stock.remember(db, current_user, idempotency_key, "POST", request_path, fingerprint, 200, read)
    db.commit()
    return read, False


def clear_prayer(
    db: Session,
    *,
    current_user: User,
    prayer_name: str,
    payload: PrayerClearRequest,
    idempotency_key: str,
    request_path: str,
) -> tuple[PrayerRead, bool]:
    fingerprint = food_stock.request_hash(
        "path.prayer.clear", {"prayer_name": prayer_name, **payload.model_dump(mode="json")}
    )
    previous = food_stock.replay(db, current_user, idempotency_key, fingerprint, request_path, PrayerRead)
    if previous is not None:
        return previous, True
    adhans, _ = prayer_times(db, payload.prayer_date, user_id=current_user.id)
    log = _get(db, current_user, payload.prayer_date, prayer_name)
    if log is None:
        raise PrayerNotFoundError("Aucun statut posé pour cette prière.")
    if payload.base_version != log.version:
        raise PrayerStatusConflictError(_read(prayer_name, payload.prayer_date, adhans[prayer_name], log))
    db.add(
        build_event(
            db, user_id=current_user.id, event_type="path.prayer.cleared",
            payload={"prayer_log_id": str(log.id), "prayer_name": prayer_name, "prayer_date": log.prayer_date.isoformat(),
                     "previous_status": log.status, "source": "user_action"},
            idempotency_key=f"path.prayer.cleared.{log.id}.v{log.version}", source_app=SourceApp.path,
            privacy_level=PrivacyLevel.high,
        )
    )
    db.delete(log)
    db.flush()
    read = _read(prayer_name, payload.prayer_date, adhans[prayer_name], None)
    food_stock.remember(db, current_user, idempotency_key, "POST", request_path, fingerprint, 200, read)
    db.commit()
    return read, False


def _get(db: Session, user: User, day: date, prayer_name: str) -> PathPrayerLog | None:
    return db.scalar(
        select(PathPrayerLog)
        .where(PathPrayerLog.user_id == user.id, PathPrayerLog.prayer_date == day, PathPrayerLog.prayer_name == prayer_name)
        .with_for_update()
    )


def _read(prayer_name: str, day: date, adhan_at: datetime, log: PathPrayerLog | None) -> PrayerRead:
    return PrayerRead(
        prayer_name=prayer_name, prayer_date=day, adhan_at=adhan_at,
        status=log.status if log else None, prayed_at=log.prayed_at if log else None, note=log.note if log else None,
        version=log.version if log else None, log_id=log.id if log else None,
    )
