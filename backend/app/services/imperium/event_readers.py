from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.imperium import ImperiumEvent

DEFAULT_EVENT_READER_LIMIT = 50
MAX_EVENT_READER_LIMIT = 100


@dataclass(frozen=True, slots=True)
class EventReadFilters:
    user_id: UUID
    event_type: str | None = None
    source_module: str | None = None
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None
    limit: int = DEFAULT_EVENT_READER_LIMIT
    offset: int = 0

    def __post_init__(self) -> None:
        if self.user_id is None:
            raise ValueError("user_id is required to read Imperium events.")
        object.__setattr__(self, "limit", _validate_limit(self.limit))
        object.__setattr__(self, "offset", _validate_offset(self.offset))


@dataclass(frozen=True, slots=True)
class EventReadPage:
    items: list[ImperiumEvent]
    limit: int
    offset: int
    has_more: bool
    next_offset: int | None


def read_imperium_events(db: Session, filters: EventReadFilters) -> EventReadPage:
    query = _build_event_read_query(filters)
    rows = list(db.scalars(query.limit(filters.limit + 1).offset(filters.offset)))
    items = rows[: filters.limit]
    has_more = len(rows) > filters.limit

    return EventReadPage(
        items=items,
        limit=filters.limit,
        offset=filters.offset,
        has_more=has_more,
        next_offset=filters.offset + filters.limit if has_more else None,
    )


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
    filters = EventReadFilters(
        user_id=user_id,
        event_type=event_type,
        source_module=source_module,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        limit=limit,
        offset=offset,
    )
    return read_imperium_events(db, filters).items


def _build_event_read_query(filters: EventReadFilters):
    query = select(ImperiumEvent).where(ImperiumEvent.user_id == filters.user_id)

    if filters.event_type is not None:
        query = query.where(ImperiumEvent.event_type == filters.event_type)
    if filters.source_module is not None:
        query = query.where(ImperiumEvent.source_module == filters.source_module)
    if filters.occurred_from is not None:
        query = query.where(ImperiumEvent.occurred_at >= filters.occurred_from)
    if filters.occurred_to is not None:
        query = query.where(ImperiumEvent.occurred_at <= filters.occurred_to)

    return query.order_by(
        ImperiumEvent.occurred_at.desc(),
        ImperiumEvent.created_at.desc(),
        ImperiumEvent.id.desc(),
    )


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
