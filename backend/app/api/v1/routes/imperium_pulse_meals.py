"""Repas Pulse (doc 40 §10) : brouillon au texte ou en photo (PUL-02), validation et décompte du stock (PUL-03),
jour (PUL-10)."""

import io
from datetime import date, datetime
from typing import Annotated
from urllib.parse import unquote
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.pulse_meals import MealConfirmRequest, MealDayRead, MealDraftCreate, MealRead
from app.services.pulse import meal_photo, meals
from app.services.pulse.expiry import paris_today

router = APIRouter()


def _require_key(idempotency_key: str | None) -> str:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    return idempotency_key


@router.get("/meals", response_model=MealDayRead)
def list_meals_route(current_user: CurrentUserDep, db: SessionDep, day: date | None = None) -> MealDayRead:
    """Repas validés du jour de Paris demandé (aujourd'hui par défaut) et totaux des macros."""
    return meals.list_day(db, current_user=current_user, day=day or paris_today())


@router.post("/meals/drafts", response_model=MealRead, status_code=status.HTTP_201_CREATED)
def create_meal_draft_route(
    payload: MealDraftCreate,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> MealRead:
    """Brouillon : macros saisies ou vides, décompte du stock proposé ; rien n'est écrit au stock."""
    try:
        read, duplicate = meals.create_draft(
            db, current_user=current_user, payload=payload, idempotency_key=_require_key(idempotency_key)
        )
    except meals.MealIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return read


@router.post("/meals/photo-drafts", response_model=MealRead, status_code=status.HTTP_201_CREATED)
async def create_meal_photo_draft_route(
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    x_filename: Annotated[str, Header(alias="X-Filename")],
    eaten_at: datetime | None = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    content_length: Annotated[int | None, Header(alias="Content-Length")] = None,
) -> MealRead:
    """Photo de l'assiette en corps brut → brouillon aux macros estimées (photo non conservée)."""
    key = _require_key(idempotency_key)
    if content_length is not None and content_length > meal_photo.MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Fichier refusé : 25 Mo maximum.")
    buffer = bytearray()
    async for chunk in request.stream():
        buffer.extend(chunk)
        if len(buffer) > meal_photo.MAX_BYTES:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Fichier refusé : 25 Mo maximum.")
    try:
        # L'analyse peut prendre jusqu'à 60 s : hors de la boucle d'événements.
        read, duplicate = await run_in_threadpool(
            meal_photo.create_photo_draft, db, current_user=current_user, filename=unquote(x_filename),
            content_type=request.headers.get("content-type"), stream=io.BytesIO(bytes(buffer)), idempotency_key=key,
            eaten_at=eaten_at,
        )
    except meal_photo.MealPhotoFileError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except meal_photo.MealPhotoAnalysisError as exc:
        code = status.HTTP_422_UNPROCESSABLE_ENTITY if exc.reason == "unreadable" else status.HTTP_503_SERVICE_UNAVAILABLE
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    except meals.MealIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return read


@router.get("/meals/{meal_id}", response_model=MealRead)
def get_meal_route(meal_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> MealRead:
    try:
        return meals.get_meal(db, current_user=current_user, meal_id=meal_id)
    except meals.MealNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/meals/{meal_id}/confirm", response_model=MealRead)
def confirm_meal_route(
    meal_id: UUID,
    payload: MealConfirmRequest,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Enregistre le repas et décompte les lignes cochées une seule fois ; stock insuffisant sans `finish` → 409."""
    key = _require_key(idempotency_key)
    try:
        return meals.confirm_meal(db, current_user=current_user, meal_id=meal_id, payload=payload, idempotency_key=key)
    except meals.MealNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except meals.MealUnitError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except (meals.MealStateError, meals.MealIdempotencyConflictError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except meals.MealStockInsufficientError as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc), "code": "STOCK_INSUFFICIENT", "current": exc.current.model_dump(mode="json")},
        )


@router.post("/meals/{meal_id}/cancel", response_model=MealRead)
def cancel_meal_route(meal_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> MealRead:
    try:
        return meals.cancel_meal(db, current_user=current_user, meal_id=meal_id)
    except meals.MealNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except meals.MealStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
