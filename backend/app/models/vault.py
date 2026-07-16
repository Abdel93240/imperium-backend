from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    desc,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, UUIDPrimaryKeyMixin


class ImperiumVaultTransaction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "imperium_vault_transactions"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('income', 'expense')",
            name="imperium_vault_transactions_transaction_type_check",
        ),
        CheckConstraint("amount_cents > 0", name="imperium_vault_transactions_amount_positive"),
        CheckConstraint("length(currency) = 3", name="imperium_vault_transactions_currency_length_check"),
        CheckConstraint(
            "("
            "is_reversal = true AND reversal_of_transaction_id IS NOT NULL"
            ") OR ("
            "is_reversal = false AND reversal_of_transaction_id IS NULL"
            ")",
            name="imperium_vault_transactions_reversal_link_check",
        ),
        Index(
            "imperium_vault_transactions_user_occurred_at_idx",
            "user_id",
            desc("occurred_at"),
        ),
        Index(
            "imperium_vault_transactions_user_local_date_idx",
            "user_id",
            desc("local_date"),
        ),
        Index(
            "imperium_vault_transactions_user_transaction_type_idx",
            "user_id",
            "transaction_type",
        ),
        Index(
            "imperium_vault_transactions_user_reversal_of_idx",
            "user_id",
            "reversal_of_transaction_id",
        ),
        Index(
            "imperium_vault_transactions_one_reversal_per_original_idx",
            "reversal_of_transaction_id",
            unique=True,
            postgresql_where=text("is_reversal = true"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    transaction_type: Mapped[str] = mapped_column(Text, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="EUR", server_default="EUR")
    wallet: Mapped[str] = mapped_column(Text, nullable=False, default="cash", server_default="cash")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    local_date: Mapped[date] = mapped_column(Date(), nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_reversal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    reversal_of_transaction_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("imperium_vault_transactions.id"),
        nullable=True,
    )
    reversal_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
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


class UpcomingExpense(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "upcoming_expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="upcoming_expenses_amount_positive"),
        CheckConstraint(
            "recurrence IS NULL OR recurrence IN ('monthly', 'quarterly', 'yearly')",
            name="upcoming_expenses_recurrence_check",
        ),
        Index("upcoming_expenses_due_active_idx", "active", "due_date"),
        Index("upcoming_expenses_user_active_due_idx", "user_id", "active", "due_date"),
        Index("upcoming_expenses_category_idx", "category"),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    label_fr: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date(), nullable=False)
    recurrence: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    wallet: Mapped[str | None] = mapped_column(Text, nullable=True)
    mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class WeeklyFinanceSummary(Base):
    __tablename__ = "weekly_finance_summaries"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    week_start: Mapped[date] = mapped_column(Date(), primary_key=True)
    business_revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    business_expenses: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    weekly_business_profit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    personal_expenses: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False)


class PressureSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "pressure_snapshots"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="pressure_snapshots_score_range"),
        CheckConstraint(
            "label IN ('safe', 'stable', 'attention', 'pressure', 'critical')",
            name="pressure_snapshots_label_check",
        ),
        Index("pressure_snapshots_computed_at_idx", desc("computed_at")),
        Index("pressure_snapshots_user_computed_at_idx", "user_id", desc("computed_at")),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    factors: Mapped[dict] = mapped_column(JSONB, nullable=False)
    daily_targets: Mapped[dict] = mapped_column(JSONB, nullable=False)
    inputs_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
