"""Routes du calendrier V1 (doc 51 §16 phase 5) en plus de la création, de la liste et de la suppression
(routes historiques de `imperium.py`) : lecture, modification, occurrences, conflits, « cette occurrence »,
décision sur la préparation d'une échéance."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.imperium import (
    CalendarConflictCheck,
    CalendarEventRead,
    CalendarEventUpdate,
    CalendarOccurrenceOverride,
    CalendarOccurrenceRead,
    CalendarPrepDecision,
)
from app.services.imperium import calendar

router = APIRouter()


def _http(db, exc: Exception) -> HTTPException:
    db.rollback()
    if isinstance(exc, calendar.CalendarEventNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


_ERRORS = (calendar.CalendarEventNotFoundError, calendar.CalendarEventValidationError)


@router.get("/calendar/occurrences", response_model=list[CalendarOccurrenceRead])
def list_occurrences_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    from_: Annotated[datetime, Query(alias="from")],
    to: Annotated[datetime, Query()],
) -> list[CalendarOccurrenceRead]:
    """Ce que l'écran affiche entre deux instants : séries dépliées, occurrences sautées ou déplacées appliquées."""
    try:
        return calendar.list_occurrences(db, current_user=current_user, starts_from=from_, starts_to=to)
    except _ERRORS as exc:
        raise _http(db, exc) from exc


@router.post("/calendar/conflicts", response_model=list[CalendarOccurrenceRead])
def conflicts_route(payload: CalendarConflictCheck, current_user: CurrentUserDep, db: SessionDep) -> list[CalendarOccurrenceRead]:
    """Créneaux déjà pris sur un intervalle (doc 51 §15.2) ; lecture seule."""
    return calendar.conflicts(db, current_user=current_user, check=payload)


@router.get("/calendar/events/{event_id}", response_model=CalendarEventRead)
def get_event_route(event_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> CalendarEventRead:
    try:
        return calendar.get_calendar_event(db, current_user=current_user, event_id=event_id)
    except _ERRORS as exc:
        raise _http(db, exc) from exc


@router.patch("/calendar/events/{event_id}", response_model=CalendarEventRead)
def update_event_route(event_id: UUID, payload: CalendarEventUpdate, current_user: CurrentUserDep,
                       db: SessionDep) -> CalendarEventRead:
    """Modifier (toute la série pour une récurrence)."""
    try:
        return calendar.update_calendar_event(db, current_user=current_user, event_id=event_id, payload=payload)
    except _ERRORS as exc:
        raise _http(db, exc) from exc


@router.post("/calendar/events/{event_id}/occurrences", response_model=CalendarEventRead)
def override_occurrence_route(event_id: UUID, payload: CalendarOccurrenceOverride, current_user: CurrentUserDep,
                              db: SessionDep) -> CalendarEventRead:
    """« Cette occurrence uniquement » : la sauter ou la déplacer."""
    try:
        return calendar.override_occurrence(db, current_user=current_user, event_id=event_id, payload=payload)
    except _ERRORS as exc:
        raise _http(db, exc) from exc


@router.post("/calendar/events/{event_id}/prep", response_model=CalendarEventRead)
def decide_prep_route(event_id: UUID, payload: CalendarPrepDecision, current_user: CurrentUserDep,
                      db: SessionDep) -> CalendarEventRead:
    """Valider (la mission de préparation est créée) ou refuser le créneau proposé pour une échéance."""
    try:
        return calendar.decide_prep(db, current_user=current_user, event_id=event_id, accept=payload.accept)
    except _ERRORS as exc:
        raise _http(db, exc) from exc
