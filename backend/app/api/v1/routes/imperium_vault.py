from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.imperium import (
    ImperiumVaultCategorySummaryResponse,
    ImperiumVaultMonthlySummaryResponse,
    ImperiumVaultSummaryResponse,
    ImperiumVaultTransactionDetailResponse,
)
from app.schemas.vault import (
    ImperiumVaultTransactionCreate,
    ImperiumVaultTransactionListResponse,
    ImperiumVaultTransactionRead,
    ImperiumVaultTransactionReverseRequest,
    ImperiumVaultTransactionReverseResponse,
)
from app.services.imperium.vault_transactions import (
    VaultTransactionIdempotencyConflictError,
    VaultTransactionNotFoundError,
    VaultTransactionReversalConflictError,
    create_vault_transaction,
    list_vault_transactions,
    reverse_vault_transaction,
)
from app.services.imperium.vault import (
    get_vault_category_summary,
    get_vault_transaction_detail,
    get_vault_monthly_summary,
    get_vault_summary,
)

router = APIRouter()


@router.get("/summary", response_model=ImperiumVaultSummaryResponse)
def get_imperium_vault_summary_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    currency: Annotated[str, Query(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")] = "EUR",
) -> ImperiumVaultSummaryResponse:
    _validate_datetime_range_params(occurred_from=occurred_from, occurred_to=occurred_to)
    return get_vault_summary(
        db,
        current_user=current_user,
        currency=currency,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
    )


@router.get("/summary/categories", response_model=ImperiumVaultCategorySummaryResponse)
def get_imperium_vault_category_summary_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    currency: Annotated[str, Query(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")] = "EUR",
    transaction_type: Literal["income", "expense"] | None = None,
) -> ImperiumVaultCategorySummaryResponse:
    _validate_datetime_range_params(occurred_from=occurred_from, occurred_to=occurred_to)
    return get_vault_category_summary(
        db,
        current_user=current_user,
        currency=currency,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        transaction_type=transaction_type,
    )


@router.get("/summary/monthly", response_model=ImperiumVaultMonthlySummaryResponse)
def get_imperium_vault_monthly_summary_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    currency: Annotated[str, Query(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")] = "EUR",
) -> ImperiumVaultMonthlySummaryResponse:
    _validate_datetime_range_params(occurred_from=occurred_from, occurred_to=occurred_to)
    return get_vault_monthly_summary(
        db,
        current_user=current_user,
        currency=currency,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
    )


@router.get("/transactions", response_model=ImperiumVaultTransactionListResponse)
def list_imperium_vault_transactions_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    transaction_type: Literal["income", "expense"] | None = None,
    category: Annotated[str | None, Query(max_length=80)] = None,
    source: Annotated[str | None, Query(max_length=80)] = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
) -> ImperiumVaultTransactionListResponse:
    _validate_datetime_range_params(occurred_from=occurred_from, occurred_to=occurred_to)
    return list_vault_transactions(
        db,
        current_user=current_user,
        limit=limit,
        offset=offset,
        transaction_type=transaction_type,
        category=category.strip() if category else None,
        source=source.strip() if source else None,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
    )


@router.get("/transactions/{transaction_id}", response_model=ImperiumVaultTransactionDetailResponse)
def get_imperium_vault_transaction_detail_route(
    transaction_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> ImperiumVaultTransactionDetailResponse:
    result = get_vault_transaction_detail(
        db,
        current_user=current_user,
        transaction_id=transaction_id,
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault transaction not found.")
    return result


@router.post(
    "/transactions",
    response_model=ImperiumVaultTransactionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_imperium_vault_transaction_route(
    payload: ImperiumVaultTransactionCreate,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ImperiumVaultTransactionRead:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")

    try:
        result, duplicate = create_vault_transaction(
            db,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except VaultTransactionIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vault transaction conflicts with an existing record.",
        ) from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


def _validate_datetime_range_params(
    *,
    occurred_from: datetime | None,
    occurred_to: datetime | None,
) -> None:
    for name, value in (("occurred_from", occurred_from), ("occurred_to", occurred_to)):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{name} must include timezone information.",
            )


@router.post(
    "/transactions/{transaction_id}/reverse",
    response_model=ImperiumVaultTransactionReverseResponse,
    status_code=status.HTTP_201_CREATED,
)
def reverse_imperium_vault_transaction_route(
    transaction_id: UUID,
    payload: ImperiumVaultTransactionReverseRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ImperiumVaultTransactionReverseResponse:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")

    try:
        result, duplicate = reverse_vault_transaction(
            db,
            current_user=current_user,
            transaction_id=transaction_id,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except VaultTransactionNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (VaultTransactionIdempotencyConflictError, VaultTransactionReversalConflictError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vault transaction reversal conflicts with an existing record.",
        ) from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result
