import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import IdempotencyStatus, PrivacyLevel, SourceApp
from app.models.event import Event
from app.models.idempotency import IdempotencyKey
from app.models.vault import VaultTransaction
from app.schemas.vault import (
    CreateVaultTransactionRequest,
    VaultTransactionResponse,
    VaultTransactionWriteResponse,
    VaultWeeklySummaryResponse,
)

ZERO = Decimal("0.00")


class IdempotencyConflictError(ValueError):
    pass


class InvalidWeekStartError(ValueError):
    pass


def create_transaction(
    db: Session,
    *,
    current_user: User,
    payload: CreateVaultTransactionRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[VaultTransactionWriteResponse, bool]:
    request_hash = _hash_payload(payload)
    existing_key = _get_existing_idempotency(db, current_user=current_user, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_existing_idempotency(existing_key, request_hash), True

    transaction = VaultTransaction(
        user_id=current_user.id,
        occurred_at=payload.occurred_at,
        local_date=payload.local_date,
        timezone=payload.timezone,
        transaction_type=payload.transaction_type.value,
        wallet=payload.wallet.value,
        category=payload.category,
        label=payload.label,
        amount=payload.amount,
        currency=payload.currency,
        notes=payload.notes,
        source_app=SourceApp.vault.value,
    )
    db.add(transaction)
    db.flush()

    event_id = f"evt_{uuid4().hex}"
    event_payload = {
        "transaction_id": str(transaction.id),
        **payload.model_dump(mode="json", exclude_none=True),
    }
    event = _build_event(
        current_user=current_user,
        event_id=event_id,
        idempotency_key=idempotency_key,
        payload=event_payload,
    )
    db.add(event)
    db.flush()

    transaction.event_id = event.id
    db.flush()

    response = _write_response(
        transaction=transaction,
        event_id=event_id,
        idempotency_key=idempotency_key,
        status_text="created",
    )
    db.add(
        IdempotencyKey(
            user_id=current_user.id,
            idempotency_key=idempotency_key,
            request_method=request_method,
            request_path=request_path,
            request_hash=request_hash,
            status=IdempotencyStatus.completed,
            response_status_code=201,
            response_body=response.model_dump(mode="json"),
        )
    )
    db.commit()
    return response, False


def get_recent_transactions(
    db: Session,
    *,
    current_user: User,
    limit: int,
) -> list[VaultTransaction]:
    return list(
        db.scalars(
            select(VaultTransaction)
            .where(VaultTransaction.user_id == current_user.id)
            .order_by(VaultTransaction.occurred_at.desc(), VaultTransaction.created_at.desc())
            .limit(limit)
        )
    )


def get_weekly_summary(
    db: Session,
    *,
    current_user: User,
    week_start: date,
) -> VaultWeeklySummaryResponse:
    if week_start.weekday() != 0:
        raise InvalidWeekStartError("week_start must be a Monday.")

    week_end = week_start + timedelta(days=6)
    transactions = list(
        db.scalars(
            select(VaultTransaction).where(
                VaultTransaction.user_id == current_user.id,
                VaultTransaction.local_date >= week_start,
                VaultTransaction.local_date <= week_end,
            )
        )
    )

    income_total = ZERO
    expense_total = ZERO
    correction_total = ZERO
    by_wallet: dict[str, dict[str, Decimal]] = {}
    by_category: dict[str, dict[str, Decimal]] = {}

    for transaction in transactions:
        amount = _money(transaction.amount)
        if transaction.transaction_type == "income":
            income_total += amount
        elif transaction.transaction_type == "expense":
            expense_total += amount
        elif transaction.transaction_type == "correction":
            correction_total += amount

        _add_summary_amount(by_wallet, transaction.wallet, transaction.transaction_type, amount)
        _add_summary_amount(by_category, transaction.category, transaction.transaction_type, amount)

    income_total = _money(income_total)
    expense_total = _money(expense_total)
    correction_total = _money(correction_total)
    net_total = _money(income_total - expense_total + correction_total)

    return VaultWeeklySummaryResponse(
        week_start=week_start,
        week_end=week_end,
        income_total=income_total,
        expense_total=expense_total,
        correction_total=correction_total,
        net_total=net_total,
        by_wallet=by_wallet,
        by_category=by_category,
    )


def _get_existing_idempotency(
    db: Session,
    *,
    current_user: User,
    idempotency_key: str,
) -> IdempotencyKey | None:
    return db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == current_user.id,
            IdempotencyKey.idempotency_key == idempotency_key,
        )
    )


def _handle_existing_idempotency(
    existing_key: IdempotencyKey,
    request_hash: str,
) -> VaultTransactionWriteResponse:
    if existing_key.request_hash != request_hash:
        raise IdempotencyConflictError("Idempotency key already used with different payload.")
    if existing_key.response_body is None:
        raise IdempotencyConflictError("Idempotency key is already processing.")
    return VaultTransactionWriteResponse(**existing_key.response_body)


def _build_event(
    *,
    current_user: User,
    event_id: str,
    idempotency_key: str,
    payload: dict,
) -> Event:
    now = datetime.now(UTC)
    return Event(
        event_id=event_id,
        event_type="vault.transaction.created",
        schema_version="1.0",
        occurred_at=now,
        received_at=now,
        source_app=SourceApp.vault,
        device_id=None,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        correlation_id=f"corr_vault_transaction_created_{uuid4().hex}",
        causation_id=None,
        privacy_level=PrivacyLevel.high,
        payload=payload,
    )


def _write_response(
    *,
    transaction: VaultTransaction,
    event_id: str,
    idempotency_key: str,
    status_text: str,
) -> VaultTransactionWriteResponse:
    transaction_response = VaultTransactionResponse.model_validate(transaction)
    transaction_response.idempotency_key = idempotency_key
    return VaultTransactionWriteResponse(
        transaction=transaction_response,
        event_id=event_id,
        idempotency_key=idempotency_key,
        status=status_text,
    )


def _hash_payload(payload: CreateVaultTransactionRequest) -> str:
    canonical = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _add_summary_amount(
    summary: dict[str, dict[str, Decimal]],
    key: str,
    transaction_type: str,
    amount: Decimal,
) -> None:
    bucket = summary.setdefault(
        key,
        {
            "income_total": ZERO,
            "expense_total": ZERO,
            "correction_total": ZERO,
            "net_total": ZERO,
        },
    )
    if transaction_type == "income":
        bucket["income_total"] = _money(bucket["income_total"] + amount)
    elif transaction_type == "expense":
        bucket["expense_total"] = _money(bucket["expense_total"] + amount)
    elif transaction_type == "correction":
        bucket["correction_total"] = _money(bucket["correction_total"] + amount)

    bucket["net_total"] = _money(
        bucket["income_total"] - bucket["expense_total"] + bucket["correction_total"]
    )


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))
