import hashlib
import json
from datetime import UTC, date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import IdempotencyStatus
from app.models.idempotency import IdempotencyKey
from app.models.vault import ImperiumVaultTransaction
from app.schemas.vault import (
    ImperiumVaultTransactionCreate,
    ImperiumVaultTransactionListResponse,
    ImperiumVaultTransactionRead,
    ImperiumVaultTransactionReversalSummary,
    ImperiumVaultTransactionReverseRequest,
    ImperiumVaultTransactionReverseResponse,
)

VAULT_TRANSACTIONS_SAFE_EXPLANATION = "Vault transactions for current user."


class VaultTransactionIdempotencyConflictError(ValueError):
    pass


class VaultTransactionNotFoundError(ValueError):
    pass


class VaultTransactionReversalConflictError(ValueError):
    pass


def create_vault_transaction(
    db: Session,
    *,
    current_user: User,
    payload: ImperiumVaultTransactionCreate,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[ImperiumVaultTransactionRead, bool]:
    request_hash = _hash_request("imperium.vault.transaction.created", payload.model_dump(mode="json"))
    existing_key = _get_existing_idempotency(db, current_user=current_user, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_existing_idempotency(existing_key, request_hash, request_path), True

    transaction = ImperiumVaultTransaction(
        user_id=current_user.id,
        transaction_type=payload.transaction_type,
        amount_cents=payload.amount_cents,
        currency=payload.currency,
        occurred_at=payload.occurred_at,
        local_date=_payload_local_date(payload.occurred_at, payload.timezone),
        timezone=_vault_timezone_label(payload.occurred_at, payload.timezone),
        category=payload.category,
        source=payload.source,
        note=payload.note,
        external_ref=payload.external_ref,
        is_reversal=False,
    )
    db.add(transaction)
    db.flush()

    response = ImperiumVaultTransactionRead.model_validate(transaction)
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


def reverse_vault_transaction(
    db: Session,
    *,
    current_user: User,
    transaction_id: UUID,
    payload: ImperiumVaultTransactionReverseRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[ImperiumVaultTransactionReverseResponse, bool]:
    request_hash = _hash_request(
        "imperium.vault.transaction.reversed",
        {"transaction_id": str(transaction_id), "payload": payload.model_dump(mode="json")},
    )
    existing_key = _get_existing_idempotency(db, current_user=current_user, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_existing_reversal_idempotency(existing_key, request_hash, request_path), True

    original = db.scalar(
        select(ImperiumVaultTransaction).where(
            ImperiumVaultTransaction.id == transaction_id,
            ImperiumVaultTransaction.user_id == current_user.id,
        )
    )
    if original is None:
        raise VaultTransactionNotFoundError("Vault transaction not found.")
    if original.is_reversal:
        raise VaultTransactionReversalConflictError("Vault reversal transactions cannot be reversed.")

    existing_reversal = db.scalar(
        select(ImperiumVaultTransaction).where(
            ImperiumVaultTransaction.user_id == current_user.id,
            ImperiumVaultTransaction.reversal_of_transaction_id == original.id,
            ImperiumVaultTransaction.is_reversal.is_(True),
        )
    )
    if existing_reversal is not None:
        raise VaultTransactionReversalConflictError("Vault transaction already has a reversal.")

    reversal_occurred_at = datetime.now(UTC)
    reversal_timezone = _user_timezone_name(current_user)
    reversal_local_date = _local_date_in_timezone(reversal_occurred_at, reversal_timezone)
    reversal = ImperiumVaultTransaction(
        user_id=current_user.id,
        transaction_type=_opposite_transaction_type(original.transaction_type),
        amount_cents=original.amount_cents,
        currency=original.currency,
        occurred_at=reversal_occurred_at,
        local_date=reversal_local_date,
        timezone=reversal_timezone,
        category=original.category,
        source="reversal",
        note=f"Reversal of transaction {original.id}",
        external_ref=None,
        is_reversal=True,
        reversal_of_transaction_id=original.id,
        reversal_reason=payload.reason,
    )
    db.add(reversal)
    db.flush()

    response = ImperiumVaultTransactionReverseResponse(
        transaction=ImperiumVaultTransactionRead.model_validate(reversal),
        reversal_summary=ImperiumVaultTransactionReversalSummary(
            status="reversed",
            original_transaction_id=original.id,
            guardrails_checked=[
                "OWNERSHIP_CONFIRMED",
                "ORIGINAL_TRANSACTION_FOUND",
                "ORIGINAL_NOT_ALREADY_REVERSED",
                "IDEMPOTENCY_KEY_ACCEPTED",
            ],
        ),
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


def list_vault_transactions(
    db: Session,
    *,
    current_user: User,
    limit: int,
    offset: int,
    transaction_type: str | None = None,
    category: str | None = None,
    source: str | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
) -> ImperiumVaultTransactionListResponse:
    query = select(ImperiumVaultTransaction).where(ImperiumVaultTransaction.user_id == current_user.id)

    if transaction_type is not None:
        query = query.where(ImperiumVaultTransaction.transaction_type == transaction_type)
    if category is not None:
        query = query.where(ImperiumVaultTransaction.category == category)
    if source is not None:
        query = query.where(ImperiumVaultTransaction.source == source)
    if occurred_from is not None:
        query = query.where(ImperiumVaultTransaction.occurred_at >= occurred_from)
    if occurred_to is not None:
        query = query.where(ImperiumVaultTransaction.occurred_at <= occurred_to)

    transactions = list(
        db.scalars(
            query.order_by(
                ImperiumVaultTransaction.occurred_at.desc(),
                ImperiumVaultTransaction.created_at.desc(),
                ImperiumVaultTransaction.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
    )

    return ImperiumVaultTransactionListResponse(
        items=[ImperiumVaultTransactionRead.model_validate(transaction) for transaction in transactions],
        count=len(transactions),
        limit=limit,
        offset=offset,
        safe_explanation=VAULT_TRANSACTIONS_SAFE_EXPLANATION,
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
    request_path: str,
) -> ImperiumVaultTransactionRead:
    if existing_key.request_path != request_path:
        raise VaultTransactionIdempotencyConflictError("Idempotency-Key already used on a different endpoint.")
    if existing_key.request_hash != request_hash:
        raise VaultTransactionIdempotencyConflictError("Idempotency key already used with different payload.")
    if existing_key.response_body is None:
        raise VaultTransactionIdempotencyConflictError("Idempotency key is already processing.")
    return ImperiumVaultTransactionRead.model_validate(existing_key.response_body)


def _handle_existing_reversal_idempotency(
    existing_key: IdempotencyKey,
    request_hash: str,
    request_path: str,
) -> ImperiumVaultTransactionReverseResponse:
    if existing_key.request_path != request_path:
        raise VaultTransactionIdempotencyConflictError("Idempotency-Key already used on a different endpoint.")
    if existing_key.request_hash != request_hash:
        raise VaultTransactionIdempotencyConflictError("Idempotency key already used with different payload.")
    if existing_key.response_body is None:
        raise VaultTransactionIdempotencyConflictError("Idempotency key is already processing.")
    return ImperiumVaultTransactionReverseResponse.model_validate(existing_key.response_body)


def _opposite_transaction_type(transaction_type: str) -> str:
    if transaction_type == "income":
        return "expense"
    return "income"


def _vault_timezone_label(occurred_at: datetime, payload_timezone: str | None) -> str:
    if payload_timezone is not None:
        return payload_timezone
    name = occurred_at.tzname()
    if name:
        if len(name) == 6 and name[0] in {"+", "-"} and name[3] == ":":
            return f"UTC{name}"
        return name
    offset = occurred_at.utcoffset()
    if offset is None:
        return "UTC"
    total_seconds = int(offset.total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    total_seconds = abs(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    return f"UTC{sign}{hours:02d}:{minutes:02d}"


def _payload_local_date(occurred_at: datetime, payload_timezone: str | None) -> date:
    if payload_timezone is None:
        return occurred_at.date()
    try:
        return occurred_at.astimezone(ZoneInfo(payload_timezone)).date()
    except ZoneInfoNotFoundError:
        return occurred_at.date()


def _user_timezone_name(current_user: User) -> str:
    timezone = getattr(current_user, "timezone", None)
    if isinstance(timezone, str) and timezone.strip():
        return timezone.strip()
    return "UTC"


def _local_date_in_timezone(value: datetime, timezone_name: str) -> date:
    try:
        return value.astimezone(ZoneInfo(timezone_name)).date()
    except ZoneInfoNotFoundError:
        return value.astimezone(UTC).date()


def _hash_request(action: str, payload: dict) -> str:
    canonical = json.dumps(
        {"action": action, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
