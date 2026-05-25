import hashlib
import json
from datetime import datetime

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
)

VAULT_TRANSACTIONS_SAFE_EXPLANATION = "Vault transactions for current user."


class VaultTransactionIdempotencyConflictError(ValueError):
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
        category=payload.category,
        source=payload.source,
        note=payload.note,
        external_ref=payload.external_ref,
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


def _hash_request(action: str, payload: dict) -> str:
    canonical = json.dumps(
        {"action": action, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
