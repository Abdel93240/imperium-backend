from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.path import (
    PathCheckInCreate,
    PathCheckInListResponse,
    PathCheckInRead,
    PathCheckInStatus,
    PathHabitCreate,
    PathHabitListResponse,
    PathHabitRead,
)
from app.services.path.habits import (
    PathCheckInConflictError,
    PathHabitInactiveError,
    PathHabitNotFoundError,
    PathIdempotencyConflictError,
    create_path_check_in,
    create_path_habit,
    list_path_check_ins,
    list_path_habits,
)

router = APIRouter()


@router.post("/habits", response_model=PathHabitRead, status_code=status.HTTP_201_CREATED)
def create_path_habit_route(
    payload: PathHabitCreate,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PathHabitRead:
    idempotency_key = _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = create_path_habit(
            db,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except PathIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Path habit conflicts with existing data.") from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/habits", response_model=PathHabitListResponse)
def list_path_habits_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    is_active: bool | None = None,
    domain: Annotated[str | None, Query(max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PathHabitListResponse:
    return list_path_habits(
        db,
        current_user=current_user,
        is_active=is_active,
        domain=domain.strip().lower() if domain else None,
        limit=limit,
        offset=offset,
    )


@router.post("/habits/{habit_id}/check-ins", response_model=PathCheckInRead, status_code=status.HTTP_201_CREATED)
def create_path_check_in_route(
    habit_id: UUID,
    payload: PathCheckInCreate,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PathCheckInRead:
    idempotency_key = _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = create_path_check_in(
            db,
            current_user=current_user,
            habit_id=habit_id,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except PathHabitNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (PathHabitInactiveError, PathCheckInConflictError, PathIdempotencyConflictError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Path check-in conflicts with existing data.",
        ) from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/check-ins", response_model=PathCheckInListResponse)
def list_path_check_ins_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    habit_id: UUID | None = None,
    status_filter: Annotated[PathCheckInStatus | None, Query(alias="status")] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PathCheckInListResponse:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must be before or equal to date_to.",
        )
    return list_path_check_ins(
        db,
        current_user=current_user,
        habit_id=habit_id,
        status=status_filter.value if status_filter else None,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


def _require_idempotency_key(idempotency_key: str | None) -> str:
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    return idempotency_key.strip()
