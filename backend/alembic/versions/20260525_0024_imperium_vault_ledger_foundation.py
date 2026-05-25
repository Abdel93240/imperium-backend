"""add imperium vault ledger foundation

Revision ID: 20260525_0024
Revises: 20260525_0023
Create Date: 2026-05-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260525_0024"
down_revision: str | None = "20260525_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "imperium_vault_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_type", sa.Text(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False, server_default="EUR"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("external_ref", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "transaction_type IN ('income', 'expense')",
            name="imperium_vault_transactions_transaction_type_check",
        ),
        sa.CheckConstraint("amount_cents > 0", name="imperium_vault_transactions_amount_positive"),
        sa.CheckConstraint("length(currency) = 3", name="imperium_vault_transactions_currency_length_check"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="imperium_vault_transactions_user_id_fkey"),
    )
    op.create_index(
        "imperium_vault_transactions_user_occurred_at_idx",
        "imperium_vault_transactions",
        ["user_id", sa.text("occurred_at DESC")],
    )
    op.create_index(
        "imperium_vault_transactions_user_transaction_type_idx",
        "imperium_vault_transactions",
        ["user_id", "transaction_type"],
    )


def downgrade() -> None:
    op.drop_index("imperium_vault_transactions_user_transaction_type_idx", table_name="imperium_vault_transactions")
    op.drop_index("imperium_vault_transactions_user_occurred_at_idx", table_name="imperium_vault_transactions")
    op.drop_table("imperium_vault_transactions")
