from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.events import (
    ImperiumEventCreateRequest,
    ImperiumEventDetailResponse,
    ImperiumEventListResponse,
    ImperiumEventSourceModule,
    ImperiumEventWriteResponse,
)
from app.services.imperium.events import (
    ImperiumEventIdempotencyConflictError,
    ImperiumEventNotFoundError,
    create_imperium_event,
    get_imperium_event,
    list_imperium_events,
)

router = APIRouter()


@router.post("/events", response_model=ImperiumEventWriteResponse, status_code=status.HTTP_201_CREATED)
def create_imperium_event_route(
    payload: ImperiumEventCreateRequest,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ImperiumEventWriteResponse:
    idempotency_key = _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = create_imperium_event(
            db,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
        )
    except ImperiumEventIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Imperium event conflicts with an existing record.",
        ) from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/events", response_model=ImperiumEventListResponse)
def list_imperium_events_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    event_type: str | None = None,
    source_module: ImperiumEventSourceModule | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
) -> ImperiumEventListResponse:
    return list_imperium_events(
        db,
        current_user=current_user,
        limit=limit,
        offset=offset,
        event_type=event_type,
        source_module=source_module,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
    )


@router.get("/events/{event_id}", response_model=ImperiumEventDetailResponse)
def imperium_event_detail_route(
    event_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> ImperiumEventDetailResponse:
    try:
        return get_imperium_event(db, current_user=current_user, event_id=event_id)
    except ImperiumEventNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _require_idempotency_key(idempotency_key: str | None) -> str:
    if idempotency_key is None or not idempotency_key.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    return idempotency_key.strip()
