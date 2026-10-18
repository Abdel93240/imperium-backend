"""Imperium : chronologie de l'historique (IMP.HISTORY.MAIN, doc 65 §7), lecture seule."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.history import (
    HistoryDayListResponse,
    HistoryEventDetailResponse,
    HistoryEventListResponse,
    HistoryFilter,
    HistoryFinancesResponse,
    HistoryPeriod,
)
from app.services.imperium import history

router = APIRouter()


@router.get("/history/events", response_model=HistoryEventListResponse)
def history_events_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    filter_name: Annotated[HistoryFilter, Query(alias="filter")] = "all",
    query: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> HistoryEventListResponse:
    """Missions, journées, plans, décisions, projets et Weekly Reviews, du plus récent au plus ancien."""
    return history.list_history_events(db, current_user=current_user, filter_name=filter_name, query=query,
                                       limit=limit, offset=offset)


@router.get("/history/events/{event_id}", response_model=HistoryEventDetailResponse)
def history_event_route(event_id: str, current_user: CurrentUserDep, db: SessionDep) -> HistoryEventDetailResponse:
    """Détail d'un élément de la chronologie (carte de détail)."""
    try:
        return history.get_history_event(db, current_user=current_user, event_id=event_id)
    except history.HistoryEventNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/history/days", response_model=HistoryDayListResponse)
def history_days_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> HistoryDayListResponse:
    """Historique des journées : démarrage, clôture, ressenti, missions faites / ratées / annulées."""
    return history.list_history_days(db, current_user=current_user, limit=limit, offset=offset)


@router.get("/history/finances", response_model=HistoryFinancesResponse)
def history_finances_route(
    current_user: CurrentUserDep, db: SessionDep, period: HistoryPeriod = "3months"
) -> HistoryFinancesResponse:
    """Bloc Finances : résultat net par jour sur la période, écart avec la précédente, solde du jour."""
    return history.history_finances(db, current_user=current_user, period=period)
