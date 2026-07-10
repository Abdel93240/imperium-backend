import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import IdempotencyStatus, PrivacyLevel, SourceApp
from app.models.event import Event
from app.models.idempotency import IdempotencyKey
from app.models.vault import ImperiumVaultTransaction
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

    transaction = ImperiumVaultTransaction(
        user_id=current_user.id,
        transaction_type=payload.transaction_type.value,
        amount_cents=_amount_to_cents(payload.amount),
        currency=payload.currency,
        wallet=payload.wallet,
        occurred_at=payload.occurred_at,
        local_date=payload.local_date,
        timezone=payload.timezone,
        category=payload.category,
        source=SourceApp.vault.value,
        note=payload.notes,
        external_ref=None,
        is_reversal=False,
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
) -> list[ImperiumVaultTransaction]:
    return list(
        db.scalars(
            select(ImperiumVaultTransaction)
            .where(ImperiumVaultTransaction.user_id == current_user.id)
            .order_by(
                ImperiumVaultTransaction.occurred_at.desc(),
                ImperiumVaultTransaction.created_at.desc(),
            )
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
            select(ImperiumVaultTransaction).where(
                ImperiumVaultTransaction.user_id == current_user.id,
                ImperiumVaultTransaction.local_date >= week_start,
                ImperiumVaultTransaction.local_date <= week_end,
            )
        )
    )

    income_total = ZERO
    expense_total = ZERO
    reversal_total = ZERO
    reversal_count = 0
    by_wallet: dict[str, dict[str, Decimal | int]] = {}
    by_category: dict[str, dict[str, Decimal | int]] = {}

    for transaction in transactions:
        amount = _cents_to_money(transaction.amount_cents)
        if transaction.transaction_type == "income":
            income_total += amount
        elif transaction.transaction_type == "expense":
            expense_total += amount
        if transaction.is_reversal:
            reversal_total += amount
            reversal_count += 1

        _add_summary_amount(by_wallet, transaction.wallet, transaction.transaction_type, amount)
        _add_summary_amount(
            by_category,
            _category_label(transaction.category),
            transaction.transaction_type,
            amount,
        )
        if transaction.is_reversal:
            _add_reversal_amount(by_wallet, transaction.wallet, amount)
            _add_reversal_amount(by_category, _category_label(transaction.category), amount)

    income_total = _money(income_total)
    expense_total = _money(expense_total)
    reversal_total = _money(reversal_total)
    net_total = _money(income_total - expense_total)

    return VaultWeeklySummaryResponse(
        week_start=week_start,
        week_end=week_end,
        income_total=income_total,
        expense_total=expense_total,
        reversal_total=reversal_total,
        reversal_count=reversal_count,
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
    transaction: ImperiumVaultTransaction,
    event_id: str,
    idempotency_key: str,
    status_text: str,
) -> VaultTransactionWriteResponse:
    transaction_response = transaction_to_response(transaction, idempotency_key=idempotency_key)
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
    summary: dict[str, dict[str, Decimal | int]],
    key: str,
    transaction_type: str,
    amount: Decimal,
) -> None:
    bucket = summary.setdefault(
        key,
        {
            "income_total": ZERO,
            "expense_total": ZERO,
            "reversal_total": ZERO,
            "reversal_count": 0,
            "net_total": ZERO,
        },
    )
    if transaction_type == "income":
        bucket["income_total"] = _money(Decimal(bucket["income_total"]) + amount)
    elif transaction_type == "expense":
        bucket["expense_total"] = _money(Decimal(bucket["expense_total"]) + amount)

    bucket["net_total"] = _money(
        Decimal(bucket["income_total"]) - Decimal(bucket["expense_total"])
    )


def _add_reversal_amount(
    summary: dict[str, dict[str, Decimal | int]],
    key: str,
    amount: Decimal,
) -> None:
    bucket = summary.setdefault(
        key,
        {
            "income_total": ZERO,
            "expense_total": ZERO,
            "reversal_total": ZERO,
            "reversal_count": 0,
            "net_total": ZERO,
        },
    )
    bucket["reversal_total"] = _money(Decimal(bucket["reversal_total"]) + amount)
    bucket["reversal_count"] = int(bucket["reversal_count"]) + 1


def transaction_to_response(
    transaction: ImperiumVaultTransaction,
    *,
    idempotency_key: str | None = None,
) -> VaultTransactionResponse:
    return VaultTransactionResponse(
        id=transaction.id,
        occurred_at=transaction.occurred_at,
        local_date=transaction.local_date,
        timezone=transaction.timezone,
        transaction_type=transaction.transaction_type,
        wallet=transaction.wallet,
        category=_category_label(transaction.category),
        label=None,
        amount=_cents_to_money(transaction.amount_cents),
        currency=transaction.currency,
        notes=transaction.note,
        is_reversal=transaction.is_reversal,
        reversal_of_transaction_id=transaction.reversal_of_transaction_id,
        reversal_reason=transaction.reversal_reason,
        created_at=transaction.created_at,
        event_id=None,
        idempotency_key=idempotency_key,
    )


def _amount_to_cents(amount: Decimal) -> int:
    return int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _cents_to_money(amount_cents: int) -> Decimal:
    return _money(Decimal(amount_cents) / Decimal("100"))


def _category_label(category: str | None) -> str:
    if category is None:
        return "uncategorized"
    stripped = category.strip()
    return stripped or "uncategorized"


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))
