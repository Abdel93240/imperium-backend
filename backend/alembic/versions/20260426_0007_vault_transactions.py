"""add vault transactions

Revision ID: 20260426_0007
Revises: 20260426_0006
Create Date: 2026-04-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260426_0007"
down_revision: str | None = "20260426_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vault_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("transaction_type", sa.Text(), nullable=False),
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False, server_default="EUR"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_app", sa.Text(), nullable=False, server_default="vault"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "transaction_type IN ('income', 'expense', 'correction')",
            name="vault_transactions_transaction_type_check",
        ),
        sa.CheckConstraint("wallet IN ('cash', 'bank')", name="vault_transactions_wallet_check"),
        sa.CheckConstraint("amount > 0", name="vault_transactions_amount_positive"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="vault_transactions_user_id_fkey"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], name="vault_transactions_event_id_fkey"),
    )
    op.create_index("vault_transactions_user_local_date_idx", "vault_transactions", ["user_id", "local_date"])
    op.create_index(
        "vault_transactions_user_occurred_at_idx",
        "vault_transactions",
        ["user_id", sa.text("occurred_at DESC")],
    )
    op.create_index(
        "vault_transactions_user_transaction_type_idx",
        "vault_transactions",
        ["user_id", "transaction_type"],
    )


def downgrade() -> None:
    op.drop_index("vault_transactions_user_transaction_type_idx", table_name="vault_transactions")
    op.drop_index("vault_transactions_user_occurred_at_idx", table_name="vault_transactions")
    op.drop_index("vault_transactions_user_local_date_idx", table_name="vault_transactions")
    op.drop_table("vault_transactions")
