"""Séances de sport Pulse (doc 40 §13) : planifier (PUL-05), suivre et terminer (PUL-06)."""

from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.pulse_workouts import (
    WorkoutCompleteRequest,
    WorkoutCreate,
    WorkoutListResponse,
    WorkoutRead,
    WorkoutSkipRequest,
    WorkoutStartRequest,
    WorkoutUpdate,
)
from app.services.pulse import food_stock, workouts
from app.services.pulse.expiry import paris_today

router = APIRouter()


def _require_key(idempotency_key: str | None) -> str:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    return idempotency_key


def _http_error(db: SessionDep, exc: Exception) -> HTTPException:
    db.rollback()
    if isinstance(exc, workouts.WorkoutNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, workouts.WorkoutInputError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


_ERRORS = (
    workouts.WorkoutNotFoundError,
    workouts.WorkoutInputError,
    workouts.WorkoutStateError,
    workouts.WorkoutIdempotencyConflictError,
    food_stock.FoodStockIdempotencyConflictError,
)


@router.get("/workouts", response_model=WorkoutListResponse)
def list_workouts_route(
    current_user: CurrentUserDep, db: SessionDep, from_day: date | None = None, to_day: date | None = None
) -> WorkoutListResponse:
    """Séances planifiées sur des jours de Paris (par défaut : aujourd'hui et les 6 jours suivants)."""
    start = from_day or paris_today()
    try:
        return workouts.list_workouts(db, current_user=current_user, from_day=start, to_day=to_day or start + timedelta(days=6))
    except _ERRORS as exc:
        raise _http_error(db, exc) from exc


@router.post("/workouts", response_model=WorkoutRead, status_code=status.HTTP_201_CREATED)
def create_workout_route(
    payload: WorkoutCreate,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WorkoutRead:
    try:
        read, duplicate = workouts.create_workout(
            db, current_user=current_user, payload=payload, idempotency_key=_require_key(idempotency_key)
        )
    except _ERRORS as exc:
        raise _http_error(db, exc) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return read


@router.get("/workouts/{workout_id}", response_model=WorkoutRead)
def get_workout_route(workout_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> WorkoutRead:
    try:
        return workouts.get_workout(db, current_user=current_user, workout_id=workout_id)
    except _ERRORS as exc:
        raise _http_error(db, exc) from exc


@router.patch("/workouts/{workout_id}", response_model=WorkoutRead)
def update_workout_route(
    workout_id: UUID,
    payload: WorkoutUpdate,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Séance planifiée seulement ; version dépassée → 409 avec la séance actuelle."""
    try:
        return workouts.update_workout(
            db, current_user=current_user, workout_id=workout_id, payload=payload,
            idempotency_key=_require_key(idempotency_key), request_path=request.url.path,
        )
    except workouts.WorkoutVersionConflictError as exc:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc), "code": "WORKOUT_VERSION_CONFLICT", "current": exc.current.model_dump(mode="json")},
        )
    except _ERRORS as exc:
        raise _http_error(db, exc) from exc


@router.post("/workouts/{workout_id}/start", response_model=WorkoutRead)
def start_workout_route(
    workout_id: UUID, payload: WorkoutStartRequest, current_user: CurrentUserDep, db: SessionDep
) -> WorkoutRead:
    try:
        return workouts.start_workout(db, current_user=current_user, workout_id=workout_id, payload=payload)
    except _ERRORS as exc:
        raise _http_error(db, exc) from exc


@router.post("/workouts/{workout_id}/complete", response_model=WorkoutRead)
def complete_workout_route(
    workout_id: UUID,
    payload: WorkoutCompleteRequest,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WorkoutRead:
    try:
        return workouts.complete_workout(
            db, current_user=current_user, workout_id=workout_id, payload=payload, idempotency_key=_require_key(idempotency_key)
        )
    except _ERRORS as exc:
        raise _http_error(db, exc) from exc


@router.post("/workouts/{workout_id}/skip", response_model=WorkoutRead)
def skip_workout_route(
    workout_id: UUID,
    payload: WorkoutSkipRequest,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WorkoutRead:
    try:
        return workouts.skip_workout(
            db, current_user=current_user, workout_id=workout_id, payload=payload, idempotency_key=_require_key(idempotency_key)
        )
    except _ERRORS as exc:
        raise _http_error(db, exc) from exc
