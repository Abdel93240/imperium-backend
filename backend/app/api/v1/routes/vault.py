from datetime import date
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.vault import (
    CreateVaultTransactionRequest,
    VaultTransactionResponse,
    VaultTransactionWriteResponse,
    VaultWeeklySummaryResponse,
)
from app.services.vault.transactions import (
    IdempotencyConflictError,
    InvalidWeekStartError,
    create_transaction,
    get_recent_transactions,
    get_weekly_summary,
    transaction_to_response,
)

router = APIRouter()


@router.post(
    "/transactions",
    response_model=VaultTransactionWriteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_transaction_route(
    payload: CreateVaultTransactionRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> VaultTransactionWriteResponse:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Idempotency-Key header.",
        )

    try:
        result, duplicate = create_transaction(
            db,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except IdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vault transaction or event conflicts with an existing record.",
        ) from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/transactions/recent", response_model=list[VaultTransactionResponse])
def recent_transactions_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[VaultTransactionResponse]:
    transactions = get_recent_transactions(db, current_user=current_user, limit=limit)
    return [transaction_to_response(transaction) for transaction in transactions]


@router.get("/summary/week", response_model=VaultWeeklySummaryResponse)
def weekly_summary_route(
    week_start: date,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> VaultWeeklySummaryResponse:
    try:
        return get_weekly_summary(db, current_user=current_user, week_start=week_start)
    except InvalidWeekStartError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
