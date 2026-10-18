"""Path : invocations à lire (doc 41 §11-bis, onglets Invocations et Favoris de PAT-12)."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.path_invocations import (
    DailyInvocationsResponse,
    InvocationCheckRequest,
    InvocationCreate,
    InvocationFavoriteUpdate,
    InvocationListResponse,
    InvocationRead,
    InvocationUpdate,
    Situation,
)
from app.services.path import invocations

router = APIRouter()

_ERRORS = (
    invocations.InvocationNotFoundError,
    invocations.InvocationInputError,
    invocations.InvocationIdempotencyConflictError,
    invocations.InvocationVersionConflictError,
    IntegrityError,
)


def _error(db: SessionDep, exc: Exception) -> JSONResponse:
    db.rollback()
    if isinstance(exc, invocations.InvocationVersionConflictError):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={
            "detail": str(exc), "code": "INVOCATION_VERSION_CONFLICT", "current": exc.current.model_dump(mode="json"),
        })
    if isinstance(exc, invocations.InvocationNotFoundError):
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})
    if isinstance(exc, invocations.InvocationInputError):
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": str(exc)})
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


@router.get("/invocations", response_model=InvocationListResponse)
def list_invocations_route(
    current_user: CurrentUserDep, db: SessionDep, situation: Situation | None = None, favorites: bool = False
) -> InvocationListResponse:
    """Bibliothèque par situation ; `favorites=true` pour l'onglet Favoris."""
    return invocations.list_invocations(db, current_user=current_user, situation=situation, favorites=favorites)


@router.post("/invocations", response_model=InvocationRead, status_code=status.HTTP_201_CREATED)
def create_invocation_route(
    payload: InvocationCreate,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Texte arabe, traduction et source validés par l'utilisateur ; matin/soir en option."""
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    try:
        read, duplicate = invocations.create_invocation(db, current_user=current_user, payload=payload,
                                                        idempotency_key=idempotency_key)
    except _ERRORS as exc:
        return _error(db, exc)
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return read


@router.get("/invocations/daily", response_model=DailyInvocationsResponse)
def daily_invocations_route(current_user: CurrentUserDep, db: SessionDep, day: date | None = None):
    """Invocations du matin et du soir avec la progression du jour (Paris)."""
    return invocations.daily(db, current_user=current_user, day=day)


@router.patch("/invocations/{invocation_id}", response_model=InvocationRead)
def update_invocation_route(invocation_id: UUID, payload: InvocationUpdate, current_user: CurrentUserDep, db: SessionDep):
    try:
        return invocations.update_invocation(db, current_user=current_user, invocation_id=invocation_id, payload=payload)
    except _ERRORS as exc:
        return _error(db, exc)


@router.patch("/invocations/{invocation_id}/favorite", response_model=InvocationRead)
def favorite_invocation_route(
    invocation_id: UUID, payload: InvocationFavoriteUpdate, current_user: CurrentUserDep, db: SessionDep
):
    try:
        return invocations.set_favorite(db, current_user=current_user, invocation_id=invocation_id,
                                        is_favorite=payload.is_favorite)
    except _ERRORS as exc:
        return _error(db, exc)


@router.post("/invocations/{invocation_id}/check", response_model=DailyInvocationsResponse)
def check_invocation_route(
    invocation_id: UUID, payload: InvocationCheckRequest, current_user: CurrentUserDep, db: SessionDep
):
    """Coche (ou décoche avec `checked: false`) une invocation du matin ou du soir."""
    try:
        return invocations.check(db, current_user=current_user, invocation_id=invocation_id, payload=payload)
    except _ERRORS as exc:
        return _error(db, exc)


@router.delete("/invocations/{invocation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invocation_route(invocation_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    try:
        invocations.delete_invocation(db, current_user=current_user, invocation_id=invocation_id)
    except _ERRORS as exc:
        return _error(db, exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
