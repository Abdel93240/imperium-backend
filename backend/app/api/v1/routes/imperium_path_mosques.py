"""Path : mosquées enregistrées (PAT-09, doc 41 §6.3)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.path_mosques import MosqueCreate, MosqueListResponse, MosqueRead, MosqueUpdate
from app.services.path import mosques
from app.services.pulse import food_stock

router = APIRouter()

_ERRORS = (
    mosques.MosqueNotFoundError,
    mosques.MosqueInputError,
    mosques.MosqueIdempotencyConflictError,
    mosques.MosqueVersionConflictError,
    food_stock.FoodStockIdempotencyConflictError,
    IntegrityError,
)


def _require_key(idempotency_key: str | None) -> str:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    return idempotency_key


def _error(db: SessionDep, exc: Exception) -> JSONResponse:
    db.rollback()
    if isinstance(exc, mosques.MosqueVersionConflictError):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={
            "detail": str(exc), "code": "MOSQUE_VERSION_CONFLICT", "current": exc.current.model_dump(mode="json"),
        })
    if isinstance(exc, mosques.MosqueNotFoundError):
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})
    if isinstance(exc, mosques.MosqueInputError):
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": str(exc)})
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


@router.get("/mosques", response_model=MosqueListResponse)
def list_mosques_route(current_user: CurrentUserDep, db: SessionDep) -> MosqueListResponse:
    """Mosquées enregistrées (par défaut d'abord) et source actuelle des horaires."""
    return mosques.list_mosques(db, current_user=current_user)


@router.post("/mosques", response_model=MosqueRead, status_code=status.HTTP_201_CREATED)
def create_mosque_route(
    payload: MosqueCreate,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Saisie manuelle ; `is_default: true` en fait la référence des horaires."""
    try:
        read, duplicate = mosques.create_mosque(db, current_user=current_user, payload=payload,
                                                idempotency_key=_require_key(idempotency_key))
    except _ERRORS as exc:
        return _error(db, exc)
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return read


@router.patch("/mosques/{mosque_id}", response_model=MosqueRead)
def update_mosque_route(
    mosque_id: UUID,
    payload: MosqueUpdate,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    try:
        return mosques.update_mosque(db, current_user=current_user, mosque_id=mosque_id, payload=payload,
                                     idempotency_key=_require_key(idempotency_key), request_path=request.url.path)
    except _ERRORS as exc:
        return _error(db, exc)


@router.delete("/mosques/{mosque_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mosque_route(mosque_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    try:
        mosques.delete_mosque(db, current_user=current_user, mosque_id=mosque_id)
    except _ERRORS as exc:
        return _error(db, exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
