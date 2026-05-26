from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.imperium import ImperiumEvent

DEFAULT_EVENT_READER_LIMIT = 50
MAX_EVENT_READER_LIMIT = 100


def list_events_for_user(
    db: Session,
    *,
    user_id: UUID,
    event_type: str | None = None,
    source_module: str | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    limit: int = DEFAULT_EVENT_READER_LIMIT,
    offset: int = 0,
) -> list[ImperiumEvent]:
    limit = _validate_limit(limit)
    offset = _validate_offset(offset)
    if user_id is None:
        raise ValueError("user_id is required to read Imperium events.")

    query = select(ImperiumEvent).where(ImperiumEvent.user_id == user_id)

    if event_type is not None:
        query = query.where(ImperiumEvent.event_type == event_type)
    if source_module is not None:
        query = query.where(ImperiumEvent.source_module == source_module)
    if occurred_from is not None:
        query = query.where(ImperiumEvent.occurred_at >= occurred_from)
    if occurred_to is not None:
        query = query.where(ImperiumEvent.occurred_at <= occurred_to)

    query = query.order_by(
        ImperiumEvent.occurred_at.desc(),
        ImperiumEvent.created_at.desc(),
        ImperiumEvent.id.desc(),
    ).limit(limit).offset(offset)

    return list(db.scalars(query))


def _validate_limit(limit: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError("limit must be an integer.")
    if limit < 1:
        raise ValueError("limit must be greater than or equal to 1.")
    if limit > MAX_EVENT_READER_LIMIT:
        raise ValueError(f"limit must be less than or equal to {MAX_EVENT_READER_LIMIT}.")
    return limit


def _validate_offset(offset: int) -> int:
    if isinstance(offset, bool) or not isinstance(offset, int):
        raise ValueError("offset must be an integer.")
    if offset < 0:
        raise ValueError("offset must be greater than or equal to 0.")
    return offset
