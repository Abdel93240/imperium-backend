from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.imperium import ImperiumEvent
from app.schemas.events import (
    EventRead,
    ImperiumEventCreateRequest,
    ImperiumEventDetailResponse,
    ImperiumEventListResponse,
    ImperiumEventWriteResponse,
)
from app.services.imperium.event_readers import EventReadFilters, read_imperium_events

IMPERIUM_EVENTS_SAFE_EXPLANATION = "Imperium events for current user."


class ImperiumEventIdempotencyConflictError(ValueError):
    pass


class ImperiumEventNotFoundError(ValueError):
    pass


def create_imperium_event(
    db: Session,
    *,
    current_user: User,
    payload: ImperiumEventCreateRequest,
    idempotency_key: str,
) -> tuple[ImperiumEventWriteResponse, bool]:
    existing_event = _get_existing_event_by_idempotency_key(
        db,
        current_user=current_user,
        idempotency_key=idempotency_key,
    )
    if existing_event is not None:
        return _handle_existing_event(existing_event, payload), True

    now = datetime.now(UTC)
    event = ImperiumEvent(
        id=uuid4(),
        user_id=current_user.id,
        event_type=payload.event_type,
        source_module=payload.source_module,
        occurred_at=payload.occurred_at,
        payload_json=payload.payload_json,
        schema_version=payload.schema_version,
        idempotency_key=idempotency_key,
        created_at=now,
        updated_at=now,
    )
    db.add(event)

    response = ImperiumEventWriteResponse(event=EventRead.model_validate(event))

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing_event = _get_existing_event_by_idempotency_key(
            db,
            current_user=current_user,
            idempotency_key=idempotency_key,
        )
        if existing_event is not None and _event_matches_payload(existing_event, payload):
            return _handle_existing_event(existing_event, payload), True
        raise ImperiumEventIdempotencyConflictError("Imperium event conflicts with an existing record.") from exc

    return response, False


def list_imperium_events(
    db: Session,
    *,
    current_user: User,
    limit: int,
    offset: int,
    event_type: str | None = None,
    source_module: str | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
) -> ImperiumEventListResponse:
    page = read_imperium_events(
        db,
        EventReadFilters(
            user_id=current_user.id,
            event_type=event_type,
            source_module=source_module,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            limit=limit,
            offset=offset,
        ),
    )

    return ImperiumEventListResponse(
        items=[EventRead.model_validate(item) for item in page.items],
        count=len(page.items),
        limit=page.limit,
        offset=page.offset,
    )


def get_imperium_event(
    db: Session,
    *,
    current_user: User,
    event_id: UUID,
) -> ImperiumEventDetailResponse:
    event = db.scalar(
        select(ImperiumEvent).where(
            ImperiumEvent.id == event_id,
            ImperiumEvent.user_id == current_user.id,
        )
    )
    if event is None:
        raise ImperiumEventNotFoundError("Imperium event not found.")
    return ImperiumEventDetailResponse(event=EventRead.model_validate(event))


def _get_existing_event_by_idempotency_key(
    db: Session,
    *,
    current_user: User,
    idempotency_key: str,
) -> ImperiumEvent | None:
    return db.scalar(
        select(ImperiumEvent).where(
            ImperiumEvent.user_id == current_user.id,
            ImperiumEvent.idempotency_key == idempotency_key,
        )
    )


def _handle_existing_event(
    existing_event: ImperiumEvent,
    payload: ImperiumEventCreateRequest,
) -> ImperiumEventWriteResponse:
    if not _event_matches_payload(existing_event, payload):
        raise ImperiumEventIdempotencyConflictError("Imperium event idempotency key already used with different payload.")
    return ImperiumEventWriteResponse(event=EventRead.model_validate(existing_event))


def _event_matches_payload(existing_event: ImperiumEvent, payload: ImperiumEventCreateRequest) -> bool:
    return (
        existing_event.event_type == payload.event_type
        and existing_event.source_module == payload.source_module
        and existing_event.occurred_at == payload.occurred_at
        and existing_event.payload_json == payload.payload_json
        and existing_event.schema_version == payload.schema_version
    )
