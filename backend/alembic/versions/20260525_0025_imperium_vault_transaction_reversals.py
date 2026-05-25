"""add imperium vault transaction reversals

Revision ID: 20260525_0025
Revises: 20260525_0024
Create Date: 2026-05-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260525_0025"
down_revision: str | None = "20260525_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "imperium_vault_transactions",
        sa.Column("reversal_of_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "imperium_vault_transactions",
        sa.Column("reversal_reason", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "imperium_vault_transactions",
        sa.Column("is_reversal", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_foreign_key(
        "imperium_vault_transactions_reversal_of_fkey",
        "imperium_vault_transactions",
        "imperium_vault_transactions",
        ["reversal_of_transaction_id"],
        ["id"],
    )
    op.create_check_constraint(
        "imperium_vault_transactions_reversal_link_check",
        "imperium_vault_transactions",
        "("
        "is_reversal = true AND reversal_of_transaction_id IS NOT NULL"
        ") OR ("
        "is_reversal = false AND reversal_of_transaction_id IS NULL"
        ")",
    )
    op.create_index(
        "imperium_vault_transactions_user_reversal_of_idx",
        "imperium_vault_transactions",
        ["user_id", "reversal_of_transaction_id"],
    )
    op.create_index(
        "imperium_vault_transactions_one_reversal_per_original_idx",
        "imperium_vault_transactions",
        ["reversal_of_transaction_id"],
        unique=True,
        postgresql_where=sa.text("is_reversal = true"),
    )


def downgrade() -> None:
    op.drop_index(
        "imperium_vault_transactions_one_reversal_per_original_idx",
        table_name="imperium_vault_transactions",
        postgresql_where=sa.text("is_reversal = true"),
    )
    op.drop_index("imperium_vault_transactions_user_reversal_of_idx", table_name="imperium_vault_transactions")
    op.drop_constraint(
        "imperium_vault_transactions_reversal_link_check",
        "imperium_vault_transactions",
        type_="check",
    )
    op.drop_constraint(
        "imperium_vault_transactions_reversal_of_fkey",
        "imperium_vault_transactions",
        type_="foreignkey",
    )
    op.drop_column("imperium_vault_transactions", "is_reversal")
    op.drop_column("imperium_vault_transactions", "reversal_reason")
    op.drop_column("imperium_vault_transactions", "reversal_of_transaction_id")
