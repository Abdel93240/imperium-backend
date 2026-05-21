from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, UUIDPrimaryKeyMixin


class VaultTransaction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "vault_transactions"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('income', 'expense', 'correction')",
            name="vault_transactions_transaction_type_check",
        ),
        CheckConstraint("wallet IN ('cash', 'bank')", name="vault_transactions_wallet_check"),
        CheckConstraint("amount > 0", name="vault_transactions_amount_positive"),
        Index("vault_transactions_user_local_date_idx", "user_id", "local_date"),
        Index("vault_transactions_user_occurred_at_idx", "user_id", "occurred_at"),
        Index("vault_transactions_user_transaction_type_idx", "user_id", "transaction_type"),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    event_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("events.id"), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    local_date: Mapped[date] = mapped_column(Date(), nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    transaction_type: Mapped[str] = mapped_column(Text, nullable=False)
    wallet: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="EUR", server_default="EUR")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_app: Mapped[str] = mapped_column(Text, nullable=False, default="vault", server_default="vault")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
