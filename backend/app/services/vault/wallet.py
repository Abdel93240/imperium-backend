"""Soldes réels du Vault (VAU-10, doc 42 §4, §8).

L'utilisateur saisit ses soldes (cash, banque, crypto en contre-valeur EUR) ; pas de type
« transfert » en V1 : un dépôt de cash en banque se reflète en ajustant les soldes. Le solde
prévu = dernier relevé + transactions passées depuis, par portefeuille ; une transaction sur
un autre portefeuille (plateforme…) est montrée à part, hors total. Écart prévu / réel de
plus de 5 % → suggestion « Vérifier ton solde réel ? », jamais bloquante.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.vault import ImperiumVaultTransaction, VaultWalletSnapshot
from app.schemas.vault import WalletSnapshotCreate, WalletSnapshotRead, WalletStateRead
from app.services.events.emitter import build_event
from app.services.pulse import food_stock

WALLETS = ("cash", "bank", "crypto")
CHECK_THRESHOLD = Decimal("0.05")
CLOCK_SKEW = timedelta(minutes=5)
CHECK_MESSAGE = "Vérifier ton solde réel ?"


class WalletInputError(ValueError):
    pass


class WalletIdempotencyConflictError(ValueError):
    pass


def record_snapshot(
    db: Session, *, current_user: User, payload: WalletSnapshotCreate, idempotency_key: str, now: datetime | None = None
) -> tuple[WalletStateRead, bool]:
    fingerprint = food_stock.request_hash("vault.wallet.snapshot", payload.model_dump(mode="json"))
    existing = db.scalar(
        select(VaultWalletSnapshot).where(
            VaultWalletSnapshot.user_id == current_user.id, VaultWalletSnapshot.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise WalletIdempotencyConflictError("Idempotency key already used with a different snapshot.")
        return wallet_state(db, current_user=current_user, now=now), True
    now = now or datetime.now(UTC)
    recorded_at = payload.recorded_at or now
    if recorded_at > now + CLOCK_SKEW:
        raise WalletInputError("La date du relevé ne peut pas être dans le futur.")
    snapshot = VaultWalletSnapshot(
        user_id=current_user.id, cash_cents=payload.cash_cents, bank_cents=payload.bank_cents,
        crypto_cents=payload.crypto_cents, recorded_at=recorded_at, source="manual",
        note=(payload.note or "").strip() or None, idempotency_key=idempotency_key, request_hash=fingerprint,
    )
    db.add(snapshot)
    db.flush()
    # Événement sans montants : les soldes restent dans la table (privacy high).
    db.add(
        build_event(
            db, user_id=current_user.id, event_type="finance.wallet.updated",
            payload={"snapshot_id": str(snapshot.id), "recorded_at": recorded_at.isoformat(), "source": "manual"},
            idempotency_key=f"finance.wallet.updated.{snapshot.id}", source_app=SourceApp.vault, privacy_level=PrivacyLevel.high,
        )
    )
    db.commit()
    return wallet_state(db, current_user=current_user, now=now), False


def latest_snapshot(db: Session, user: User, at: datetime | None = None) -> VaultWalletSnapshot | None:
    query = select(VaultWalletSnapshot).where(VaultWalletSnapshot.user_id == user.id)
    if at is not None:
        query = query.where(VaultWalletSnapshot.recorded_at <= at)
    return db.scalar(query.order_by(VaultWalletSnapshot.recorded_at.desc(), VaultWalletSnapshot.created_at.desc()).limit(1))


def wallet_state(db: Session, *, current_user: User, now: datetime | None = None) -> WalletStateRead:
    now = now or datetime.now(UTC)
    snapshot = latest_snapshot(db, current_user, now)
    if snapshot is None:
        return WalletStateRead(
            snapshot=None, predicted_cash_cents=None, predicted_bank_cents=None, predicted_crypto_cents=None,
            predicted_total_cents=None, transactions_since=0, other_wallets_cents={}, check_suggested=False,
            message="Saisis tes soldes réels pour suivre ton wallet.",
        )
    deltas, others, count = movements_since(db, current_user, snapshot.recorded_at, now)
    predicted = {
        "cash": snapshot.cash_cents + deltas["cash"], "bank": snapshot.bank_cents + deltas["bank"],
        "crypto": snapshot.crypto_cents + deltas["crypto"],
    }
    actual = _total(snapshot)
    total = sum(predicted.values())
    check = abs(Decimal(total - actual)) > CHECK_THRESHOLD * max(Decimal(abs(actual)), Decimal(100))
    return WalletStateRead(
        snapshot=_read(snapshot), predicted_cash_cents=predicted["cash"], predicted_bank_cents=predicted["bank"],
        predicted_crypto_cents=predicted["crypto"], predicted_total_cents=total, transactions_since=count,
        other_wallets_cents=others, check_suggested=check, message=CHECK_MESSAGE if check else None,
    )


def movements_since(db: Session, user: User, since: datetime, until: datetime) -> tuple[dict[str, int], dict[str, int], int]:
    """Mouvements signés (centimes) par portefeuille entre le relevé et maintenant."""
    rows = db.scalars(
        select(ImperiumVaultTransaction).where(
            ImperiumVaultTransaction.user_id == user.id, ImperiumVaultTransaction.currency == "EUR",
            ImperiumVaultTransaction.occurred_at > since, ImperiumVaultTransaction.occurred_at <= until,
        )
    )
    deltas = {wallet: 0 for wallet in WALLETS}
    others: dict[str, int] = {}
    count = 0
    for transaction in rows:
        signed = transaction.amount_cents if transaction.transaction_type == "income" else -transaction.amount_cents
        count += 1
        if transaction.wallet in deltas:
            deltas[transaction.wallet] += signed
        else:
            others[transaction.wallet] = others.get(transaction.wallet, 0) + signed
    return deltas, others, count


def list_snapshots(db: Session, *, current_user: User, limit: int) -> list[WalletSnapshotRead]:
    rows = db.scalars(
        select(VaultWalletSnapshot).where(VaultWalletSnapshot.user_id == current_user.id)
        .order_by(VaultWalletSnapshot.recorded_at.desc()).limit(limit)
    )
    return [_read(row) for row in rows]


def _total(snapshot: VaultWalletSnapshot) -> int:
    return snapshot.cash_cents + snapshot.bank_cents + snapshot.crypto_cents


def _read(snapshot: VaultWalletSnapshot) -> WalletSnapshotRead:
    return WalletSnapshotRead(
        id=snapshot.id, cash_cents=snapshot.cash_cents, bank_cents=snapshot.bank_cents, crypto_cents=snapshot.crypto_cents,
        total_cents=_total(snapshot), recorded_at=snapshot.recorded_at, source=snapshot.source, note=snapshot.note,
    )
