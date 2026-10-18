"""Path : ghusl (doc 41 §10) — état requis PAT-04 et adresses PAT-10."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.path_ghusl import (
    GhuslAddressCreate,
    GhuslAddressListResponse,
    GhuslAddressRead,
    GhuslAddressUpdate,
    GhuslCompleteRequest,
    GhuslCurrentRead,
    GhuslStateRead,
)
from app.services.path import ghusl
from app.services.pulse import food_stock

router = APIRouter()


def _require_key(idempotency_key: str | None) -> str:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    return idempotency_key


def _error(db: SessionDep, exc: Exception) -> JSONResponse:
    db.rollback()
    if isinstance(exc, ghusl.GhuslStateError) and exc.current is not None:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc), "code": "GHUSL_STATE_CONFLICT", "current": exc.current.model_dump(mode="json")},
        )
    if isinstance(exc, ghusl.GhuslAddressVersionConflictError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc), "code": "GHUSL_ADDRESS_VERSION_CONFLICT", "current": exc.current.model_dump(mode="json")},
        )
    if isinstance(exc, ghusl.GhuslNotFoundError):
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})
    if isinstance(exc, ghusl.GhuslStateError):
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": str(exc)})
    if isinstance(exc, IntegrityError):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": "Écriture concurrente : relis puis réessaie."})
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


_ERRORS = (
    ghusl.GhuslStateError,
    ghusl.GhuslNotFoundError,
    ghusl.GhuslIdempotencyConflictError,
    ghusl.GhuslAddressVersionConflictError,
    food_stock.FoodStockIdempotencyConflictError,
    IntegrityError,
)


@router.get("/ghusl", response_model=GhuslCurrentRead)
def ghusl_current_route(current_user: CurrentUserDep, db: SessionDep) -> GhuslCurrentRead:
    """Ghusl requis ou non, activation en cours (mission, replanification)."""
    return ghusl.current(db, current_user=current_user)


@router.post("/ghusl/activate", response_model=GhuslStateRead, status_code=status.HTTP_201_CREATED)
def activate_ghusl_route(
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """« Ghusl requis » : mission Imperium et replanification immédiate ; jamais déduit."""
    try:
        read, duplicate = ghusl.activate(db, current_user=current_user, idempotency_key=_require_key(idempotency_key))
    except _ERRORS as exc:
        return _error(db, exc)
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return read


@router.post("/ghusl/complete", response_model=GhuslStateRead)
def complete_ghusl_route(
    payload: GhuslCompleteRequest,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """« Ghusl fait » : termine l'activation lue et la mission, sans nouvelle replanification."""
    try:
        read, _ = ghusl.complete(
            db, current_user=current_user, payload=payload, idempotency_key=_require_key(idempotency_key),
            request_path=request.url.path,
        )
    except _ERRORS as exc:
        return _error(db, exc)
    return read


@router.get("/ghusl-addresses", response_model=GhuslAddressListResponse)
def list_addresses_route(current_user: CurrentUserDep, db: SessionDep) -> GhuslAddressListResponse:
    return ghusl.list_addresses(db, current_user=current_user)


@router.post("/ghusl-addresses", response_model=GhuslAddressRead, status_code=status.HTTP_201_CREATED)
def create_address_route(
    payload: GhuslAddressCreate,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Adresse ghusl ; `is_default: true` retire le défaut de l'ancienne."""
    try:
        read, duplicate = ghusl.create_address(
            db, current_user=current_user, payload=payload, idempotency_key=_require_key(idempotency_key)
        )
    except _ERRORS as exc:
        return _error(db, exc)
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return read


@router.patch("/ghusl-addresses/{address_id}", response_model=GhuslAddressRead)
def update_address_route(
    address_id: UUID,
    payload: GhuslAddressUpdate,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Modification avec la version lue ; sinon 409 GHUSL_ADDRESS_VERSION_CONFLICT."""
    try:
        return ghusl.update_address(
            db, current_user=current_user, address_id=address_id, payload=payload,
            idempotency_key=_require_key(idempotency_key), request_path=request.url.path,
        )
    except _ERRORS as exc:
        return _error(db, exc)


@router.delete("/ghusl-addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_address_route(address_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    try:
        ghusl.delete_address(db, current_user=current_user, address_id=address_id)
    except _ERRORS as exc:
        return _error(db, exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
