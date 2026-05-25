from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUserDep, SessionDep
from app.core.dates import get_default_local_date
from app.schemas.pulse import (
    PulseEntryCreate,
    PulseEntryListResponse,
    PulseEntryRead,
    PulseStatsSummaryResponse,
    PulseTodayResponse,
)
from app.services.pulse.entries import (
    PulseEntryConflictError,
    PulseEntryNotFoundError,
    PulseIdempotencyConflictError,
    create_pulse_entry,
    get_pulse_stats_summary,
    get_pulse_today_entry,
    get_pulse_entry,
    list_pulse_entries,
)

router = APIRouter()


@router.get("/today", response_model=PulseTodayResponse)
def get_pulse_today_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    query_date: date | None = Query(default=None, alias="date"),
) -> PulseTodayResponse:
    return get_pulse_today_entry(
        db,
        current_user=current_user,
        local_date=query_date or get_default_local_date(),
    )


@router.get("/stats/summary", response_model=PulseStatsSummaryResponse)
def get_pulse_stats_summary_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    date_from: date | None = None,
    date_to: date | None = None,
) -> PulseStatsSummaryResponse:
    _validate_date_range(date_from=date_from, date_to=date_to)
    return get_pulse_stats_summary(
        db,
        current_user=current_user,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("/entries", response_model=PulseEntryRead, status_code=status.HTTP_201_CREATED)
def create_pulse_entry_route(
    payload: PulseEntryCreate,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PulseEntryRead:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")

    try:
        result, duplicate = create_pulse_entry(
            db,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except (PulseEntryConflictError, PulseIdempotencyConflictError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pulse entry conflicts with existing data.") from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/entries", response_model=PulseEntryListResponse)
def list_pulse_entries_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PulseEntryListResponse:
    _validate_date_range(date_from=date_from, date_to=date_to)
    return list_pulse_entries(
        db,
        current_user=current_user,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


@router.get("/entries/{entry_id}", response_model=PulseEntryRead)
def get_pulse_entry_route(
    entry_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> PulseEntryRead:
    try:
        return get_pulse_entry(db, current_user=current_user, entry_id=entry_id)
    except PulseEntryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _validate_date_range(*, date_from: date | None, date_to: date | None) -> None:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must be before or equal to date_to.",
        )
