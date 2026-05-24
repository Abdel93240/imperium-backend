import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import IdempotencyStatus, PrivacyLevel, SourceApp
from app.models.event import Event
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumCalendarEvent
from app.schemas.imperium import CalendarEventCreate, CalendarEventRead, CalendarEventType


class CalendarEventNotFoundError(ValueError):
    pass


class CalendarEventIdempotencyConflictError(ValueError):
    pass


class CalendarEventValidationError(ValueError):
    pass


def create_calendar_event(
    db: Session,
    *,
    current_user: User,
    payload: CalendarEventCreate,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[CalendarEventRead, bool]:
    request_hash = _hash_request("calendar.event.created", payload.model_dump(mode="json"))
    existing_key = _get_existing_idempotency(db, current_user=current_user, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_existing_idempotency(existing_key, request_hash), True

    calendar_event = ImperiumCalendarEvent(
        user_id=current_user.id,
        event_type=payload.event_type.value,
        title=payload.title,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        blocks_time=payload.blocks_time,
        location=payload.location,
        notes=payload.notes,
    )
    db.add(calendar_event)
    db.flush()

    event_id = f"evt_{uuid4().hex}"
    db.add(
        _build_event(
            current_user=current_user,
            event_id=event_id,
            idempotency_key=idempotency_key,
            payload={
                "calendar_event_id": str(calendar_event.id),
                **payload.model_dump(mode="json", exclude_none=True),
            },
        )
    )
    db.flush()

    response = CalendarEventRead.model_validate(calendar_event)
    _store_idempotency(
        db,
        current_user=current_user,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response=response,
    )
    db.commit()
    return response, False


def list_calendar_events(
    db: Session,
    *,
    current_user: User,
    starts_from: datetime | None = None,
    starts_to: datetime | None = None,
    event_type: CalendarEventType | None = None,
) -> list[ImperiumCalendarEvent]:
    if starts_from is not None and starts_to is not None and starts_to < starts_from:
        raise CalendarEventValidationError("to must be greater than or equal to from.")

    query = select(ImperiumCalendarEvent).where(ImperiumCalendarEvent.user_id == current_user.id)
    if starts_from is not None:
        query = query.where(ImperiumCalendarEvent.starts_at >= starts_from)
    if starts_to is not None:
        query = query.where(ImperiumCalendarEvent.starts_at <= starts_to)
    if event_type is not None:
        query = query.where(ImperiumCalendarEvent.event_type == event_type.value)
    query = query.order_by(ImperiumCalendarEvent.starts_at.asc(), ImperiumCalendarEvent.created_at.asc())
    return list(db.scalars(query))


def delete_calendar_event(db: Session, *, current_user: User, event_id: UUID) -> UUID:
    calendar_event = _get_user_calendar_event(db, current_user=current_user, event_id=event_id)
    if calendar_event is None:
        raise CalendarEventNotFoundError("Calendar event not found.")

    deleted_id = calendar_event.id
    db.delete(calendar_event)
    db.commit()
    return deleted_id


def _get_existing_idempotency(
    db: Session,
    *,
    current_user: User,
    idempotency_key: str,
) -> IdempotencyKey | None:
    return db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == current_user.id,
            IdempotencyKey.idempotency_key == idempotency_key,
        )
    )


def _handle_existing_idempotency(
    existing_key: IdempotencyKey,
    request_hash: str,
) -> CalendarEventRead:
    if existing_key.request_hash != request_hash:
        raise CalendarEventIdempotencyConflictError("Idempotency key already used with different payload.")
    if existing_key.response_body is None:
        raise CalendarEventIdempotencyConflictError("Idempotency key is already processing.")
    return CalendarEventRead(**existing_key.response_body)


def _get_user_calendar_event(
    db: Session,
    *,
    current_user: User,
    event_id: UUID,
) -> ImperiumCalendarEvent | None:
    return db.scalar(
        select(ImperiumCalendarEvent).where(
            ImperiumCalendarEvent.id == event_id,
            ImperiumCalendarEvent.user_id == current_user.id,
        )
    )


def _build_event(
    *,
    current_user: User,
    event_id: str,
    idempotency_key: str,
    payload: dict,
) -> Event:
    now = datetime.now(UTC)
    return Event(
        event_id=event_id,
        event_type="calendar.event.created",
        schema_version="1.0",
        occurred_at=now,
        received_at=now,
        source_app=SourceApp.imperium,
        device_id=None,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        correlation_id=f"corr_calendar_event_created_{uuid4().hex}",
        causation_id=None,
        privacy_level=PrivacyLevel.medium,
        payload=payload,
    )


def _store_idempotency(
    db: Session,
    *,
    current_user: User,
    idempotency_key: str,
    request_method: str,
    request_path: str,
    request_hash: str,
    response: CalendarEventRead,
) -> None:
    db.add(
        IdempotencyKey(
            user_id=current_user.id,
            idempotency_key=idempotency_key,
            request_method=request_method,
            request_path=request_path,
            request_hash=request_hash,
            status=IdempotencyStatus.completed,
            response_status_code=201,
            response_body=response.model_dump(mode="json"),
        )
    )


def _hash_request(action: str, payload: dict) -> str:
    canonical = json.dumps(
        {"action": action, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
