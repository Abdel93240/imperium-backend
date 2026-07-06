"""add append-only guards to imperium vault transactions

Revision ID: 20260706_0033
Revises: 20260705_0032
Create Date: 2026-07-06
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260706_0033"
down_revision: str | None = "20260705_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = "20260426_0003"


def upgrade() -> None:
    op.execute(
        """
        CREATE TRIGGER imperium_vault_transactions_append_only_guard
        BEFORE UPDATE OR DELETE ON imperium_vault_transactions
        FOR EACH ROW EXECUTE FUNCTION prevent_append_only_update_delete();
        """
    )
    op.execute(
        """
        CREATE TRIGGER imperium_vault_transactions_append_only_truncate_guard
        BEFORE TRUNCATE ON imperium_vault_transactions
        FOR EACH STATEMENT EXECUTE FUNCTION prevent_append_only_truncate();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS imperium_vault_transactions_append_only_truncate_guard "
        "ON imperium_vault_transactions"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS imperium_vault_transactions_append_only_guard "
        "ON imperium_vault_transactions"
    )
