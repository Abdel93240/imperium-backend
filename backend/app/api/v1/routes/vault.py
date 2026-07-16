from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.vault import (
    UpcomingExpenseCreate,
    UpcomingExpenseRead,
    UpcomingExpenseUpdate,
    VaultPressureExplainResponse,
    VaultPressureHistoryItem,
    VaultPressureResponse,
    WeeklyFinanceSummaryRead,
)
from app.services.vault.pressure import (
    compute_pressure_from_db,
    latest_pressure_snapshot,
    pressure_history,
)
from app.services.vault.upcoming import (
    create_upcoming_expense,
    deactivate_upcoming_expense,
    list_upcoming_expenses,
    update_upcoming_expense,
)
from app.services.vault.weekly import list_weekly_summaries

router = APIRouter()


@router.get("/pressure", response_model=VaultPressureResponse)
def pressure_route(current_user: CurrentUserDep, db: SessionDep) -> VaultPressureResponse:
    snapshot = compute_pressure_from_db(db, current_user=current_user)
    return _pressure_response(snapshot)


@router.get("/pressure/explain", response_model=VaultPressureExplainResponse)
def pressure_explain_route(current_user: CurrentUserDep, db: SessionDep) -> VaultPressureExplainResponse:
    snapshot = latest_pressure_snapshot(db)
    if snapshot is None:
        snapshot = compute_pressure_from_db(db, current_user=current_user)
    return VaultPressureExplainResponse(
        score=snapshot.score,
        label=snapshot.label,
        factors=snapshot.factors,
        daily_targets=snapshot.daily_targets,
        inputs_snapshot=snapshot.inputs_snapshot,
        computed_at=snapshot.computed_at,
    )


@router.get("/pressure/history", response_model=list[VaultPressureHistoryItem])
def pressure_history_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> list[VaultPressureHistoryItem]:
    _ = current_user
    return [
        VaultPressureHistoryItem(
            id=snapshot.id,
            computed_at=snapshot.computed_at,
            score=snapshot.score,
            label=snapshot.label,
            daily_targets=snapshot.daily_targets,
        )
        for snapshot in pressure_history(db, limit=limit)
    ]


@router.get("/upcoming-expenses", response_model=list[UpcomingExpenseRead])
def list_upcoming_expenses_route(
    current_user: CurrentUserDep, db: SessionDep, active: bool | None = True
) -> list[UpcomingExpenseRead]:
    _ = current_user
    return list_upcoming_expenses(db, active=active)


@router.post("/upcoming-expenses", response_model=UpcomingExpenseRead, status_code=status.HTTP_201_CREATED)
def create_upcoming_expense_route(
    payload: UpcomingExpenseCreate, current_user: CurrentUserDep, db: SessionDep
) -> UpcomingExpenseRead:
    _ = current_user
    return create_upcoming_expense(db, payload=payload)


@router.patch("/upcoming-expenses/{expense_id}", response_model=UpcomingExpenseRead)
def update_upcoming_expense_route(
    expense_id: UUID,
    payload: UpcomingExpenseUpdate,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> UpcomingExpenseRead:
    _ = current_user
    expense = update_upcoming_expense(db, expense_id=expense_id, payload=payload)
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upcoming expense not found.")
    return expense


@router.delete("/upcoming-expenses/{expense_id}", response_model=UpcomingExpenseRead)
def delete_upcoming_expense_route(
    expense_id: UUID, current_user: CurrentUserDep, db: SessionDep
) -> UpcomingExpenseRead:
    _ = current_user
    expense = deactivate_upcoming_expense(db, expense_id=expense_id)
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upcoming expense not found.")
    return expense


@router.get("/weekly-summaries", response_model=list[WeeklyFinanceSummaryRead])
def weekly_summaries_route(
    current_user: CurrentUserDep, db: SessionDep, from_: Annotated[date | None, Query(alias="from")] = None
) -> list[WeeklyFinanceSummaryRead]:
    _ = current_user
    return list_weekly_summaries(db, from_date=from_)


def _pressure_response(snapshot) -> VaultPressureResponse:
    return VaultPressureResponse(
        score=snapshot.score,
        label=snapshot.label,
        daily_targets=snapshot.daily_targets,
        computed_at=snapshot.computed_at,
    )
