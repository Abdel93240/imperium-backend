from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.vault import (
    UpcomingExpenseCreate,
    UpcomingExpensePay,
    UpcomingExpensePayResult,
    UpcomingExpenseRead,
    UpcomingExpenseUpdate,
    VaultPressureExplainResponse,
    VaultPressureHistoryItem,
    VaultPressureResponse,
    WalletSnapshotCreate,
    WalletSnapshotRead,
    WalletStateRead,
    WeeklyFinanceSummaryRead,
)
from app.services.vault.pressure import (
    compute_pressure_from_db,
    latest_pressure_snapshot,
    pressure_history,
)
from app.services.imperium.vault_transactions import VaultTransactionIdempotencyConflictError
from app.services.vault import upcoming, wallet
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
    snapshot = latest_pressure_snapshot(db, current_user=current_user)
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
    return [
        VaultPressureHistoryItem(
            id=snapshot.id,
            computed_at=snapshot.computed_at,
            score=snapshot.score,
            label=snapshot.label,
            daily_targets=snapshot.daily_targets,
        )
        for snapshot in pressure_history(db, current_user=current_user, limit=limit)
    ]


@router.get("/upcoming-expenses", response_model=list[UpcomingExpenseRead])
def list_upcoming_expenses_route(
    current_user: CurrentUserDep, db: SessionDep, active: bool | None = True
) -> list[UpcomingExpenseRead]:
    return list_upcoming_expenses(db, current_user=current_user, active=active)


@router.post("/upcoming-expenses", response_model=UpcomingExpenseRead, status_code=status.HTTP_201_CREATED)
def create_upcoming_expense_route(
    payload: UpcomingExpenseCreate, current_user: CurrentUserDep, db: SessionDep
) -> UpcomingExpenseRead:
    return create_upcoming_expense(db, current_user=current_user, payload=payload)


@router.patch("/upcoming-expenses/{expense_id}", response_model=UpcomingExpenseRead)
def update_upcoming_expense_route(
    expense_id: UUID,
    payload: UpcomingExpenseUpdate,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> UpcomingExpenseRead:
    expense = update_upcoming_expense(db, current_user=current_user, expense_id=expense_id, payload=payload)
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upcoming expense not found.")
    return expense


@router.delete("/upcoming-expenses/{expense_id}", response_model=UpcomingExpenseRead)
def delete_upcoming_expense_route(
    expense_id: UUID, current_user: CurrentUserDep, db: SessionDep
) -> UpcomingExpenseRead:
    expense = deactivate_upcoming_expense(db, current_user=current_user, expense_id=expense_id)
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upcoming expense not found.")
    return expense


@router.post("/upcoming-expenses/{expense_id}/mark-paid", response_model=UpcomingExpensePayResult)
def mark_upcoming_expense_paid_route(
    expense_id: UUID,
    payload: UpcomingExpensePay,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """VAU-11 : dépense écrite au Vault, échéance close, prochaine échéance créée si elle se répète."""
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    try:
        return upcoming.mark_paid(db, current_user=current_user, expense_id=expense_id, payload=payload,
                                  idempotency_key=idempotency_key, request_path=request.url.path)
    except upcoming.UpcomingExpenseNotFoundError as exc:
        db.rollback()
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})
    except (upcoming.UpcomingExpenseStateError, VaultTransactionIdempotencyConflictError) as exc:
        db.rollback()
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


@router.get("/wallet", response_model=WalletStateRead)
def wallet_state_route(current_user: CurrentUserDep, db: SessionDep) -> WalletStateRead:
    """VAU-10 : dernier relevé réel et solde prévu (relevé + transactions depuis)."""
    return wallet.wallet_state(db, current_user=current_user)


@router.get("/wallet/snapshots", response_model=list[WalletSnapshotRead])
def wallet_snapshots_route(
    current_user: CurrentUserDep, db: SessionDep, limit: Annotated[int, Query(ge=1, le=100)] = 20
) -> list[WalletSnapshotRead]:
    return wallet.list_snapshots(db, current_user=current_user, limit=limit)


@router.post("/wallet/snapshots", response_model=WalletStateRead, status_code=status.HTTP_201_CREATED)
def record_wallet_snapshot_route(
    payload: WalletSnapshotCreate,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """« Mettre à jour wallet » : soldes réels cash, banque, crypto ; la pression les lit ensuite."""
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    try:
        state, duplicate = wallet.record_snapshot(db, current_user=current_user, payload=payload, idempotency_key=idempotency_key)
    except wallet.WalletInputError as exc:
        db.rollback()
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": str(exc)})
    except wallet.WalletIdempotencyConflictError as exc:
        db.rollback()
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return state


@router.get("/weekly-summaries", response_model=list[WeeklyFinanceSummaryRead])
def weekly_summaries_route(
    current_user: CurrentUserDep, db: SessionDep, from_: Annotated[date | None, Query(alias="from")] = None
) -> list[WeeklyFinanceSummaryRead]:
    return list_weekly_summaries(db, current_user=current_user, from_date=from_)


def _pressure_response(snapshot) -> VaultPressureResponse:
    return VaultPressureResponse(
        score=snapshot.score,
        label=snapshot.label,
        daily_targets=snapshot.daily_targets,
        computed_at=snapshot.computed_at,
    )
