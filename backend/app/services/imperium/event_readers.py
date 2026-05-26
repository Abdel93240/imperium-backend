from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.imperium import ImperiumEvent


def list_events_for_user(
    db: Session,
    *,
    user_id: UUID,
    event_type: str | None = None,
    source_module: str | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ImperiumEvent]:
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
