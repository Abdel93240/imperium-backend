"""Path : calendrier hégirien (doc 41 §14, 14-V3)."""

from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.path_calendar import (
    CalendarEventListResponse,
    HijriDayRead,
    MonthStartConfirm,
    MonthStartRead,
    PersonalEventCreate,
    PersonalEventRead,
)
from app.services.path import fasting, hijri
from app.services.pulse import food_stock

router = APIRouter()


def _require_key(idempotency_key: str | None) -> str:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    return idempotency_key


def _error(db: SessionDep, exc: Exception) -> JSONResponse:
    db.rollback()
    if isinstance(exc, hijri.CalendarNotFoundError):
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})
    if isinstance(exc, hijri.CalendarInputError):
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": str(exc)})
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


_ERRORS = (hijri.CalendarInputError, hijri.CalendarNotFoundError, food_stock.FoodStockIdempotencyConflictError)


@router.get("/calendar/hijri", response_model=HijriDayRead)
def hijri_day_route(current_user: CurrentUserDep, db: SessionDep, day: date | None = None) -> HijriDayRead:
    """Date hégirienne d'un jour (aujourd'hui par défaut), avec son statut (prédite ou confirmée)."""
    return hijri.hijri_day(db, current_user=current_user, day=day or fasting.paris_today())


@router.get("/calendar/events", response_model=CalendarEventListResponse)
def calendar_events_route(
    current_user: CurrentUserDep, db: SessionDep, from_day: date | None = None, to_day: date | None = None
):
    """Dates religieuses et événements personnels (par défaut : les 14 prochains jours, fenêtre d'affichage)."""
    start = from_day or fasting.paris_today()
    try:
        return hijri.list_events(db, current_user=current_user, from_day=start,
                                 to_day=to_day or start + timedelta(days=hijri.DISPLAY_WINDOW_DAYS - 1))
    except _ERRORS as exc:
        return _error(db, exc)


@router.post("/calendar/confirm-date", response_model=MonthStartRead)
def confirm_date_route(
    payload: MonthStartConfirm,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Observation de la lune : fixe le 1er du mois (à un jour près de la prévision)."""
    try:
        return hijri.confirm_month_start(db, current_user=current_user, payload=payload,
                                         idempotency_key=_require_key(idempotency_key), request_path=request.url.path)
    except _ERRORS as exc:
        return _error(db, exc)


@router.get("/calendar/personal-events", response_model=list[PersonalEventRead])
def list_personal_route(current_user: CurrentUserDep, db: SessionDep) -> list[PersonalEventRead]:
    return hijri.list_personal(db, current_user=current_user)


@router.post("/calendar/personal-events", response_model=PersonalEventRead, status_code=status.HTTP_201_CREATED)
def add_personal_route(
    payload: PersonalEventCreate,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Événement religieux personnel (dars, rappel) : une année précise ou chaque année."""
    try:
        read, duplicate = hijri.add_personal(db, current_user=current_user, payload=payload,
                                             idempotency_key=_require_key(idempotency_key))
    except _ERRORS as exc:
        return _error(db, exc)
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return read


@router.delete("/calendar/personal-events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_personal_route(event_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    try:
        hijri.delete_personal(db, current_user=current_user, event_id=event_id)
    except _ERRORS as exc:
        return _error(db, exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
