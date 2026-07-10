"""add open wallet to imperium vault transactions

Revision ID: 20260710_0037
Revises: 20260707_0036
Create Date: 2026-07-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260710_0037"
down_revision: str | None = "20260707_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "imperium_vault_transactions",
        sa.Column("wallet", sa.Text(), nullable=False, server_default="cash"),
    )


def downgrade() -> None:
    op.drop_column("imperium_vault_transactions", "wallet")
