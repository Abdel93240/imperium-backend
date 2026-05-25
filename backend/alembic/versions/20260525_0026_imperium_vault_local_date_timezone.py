"""add local date and timezone to imperium vault transactions

Revision ID: 20260525_0026
Revises: 20260525_0025
Create Date: 2026-05-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260525_0026"
down_revision: str | None = "20260525_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("imperium_vault_transactions", sa.Column("local_date", sa.Date(), nullable=True))
    op.add_column("imperium_vault_transactions", sa.Column("timezone", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE imperium_vault_transactions
        SET
            local_date = (occurred_at AT TIME ZONE 'UTC')::date,
            timezone = 'UTC'
        WHERE local_date IS NULL OR timezone IS NULL
        """
    )
    op.alter_column("imperium_vault_transactions", "local_date", nullable=False)
    op.alter_column("imperium_vault_transactions", "timezone", nullable=False)
    op.create_index(
        "imperium_vault_transactions_user_local_date_idx",
        "imperium_vault_transactions",
        ["user_id", sa.text("local_date DESC")],
    )


def downgrade() -> None:
    op.drop_index("imperium_vault_transactions_user_local_date_idx", table_name="imperium_vault_transactions")
    op.drop_column("imperium_vault_transactions", "timezone")
    op.drop_column("imperium_vault_transactions", "local_date")
