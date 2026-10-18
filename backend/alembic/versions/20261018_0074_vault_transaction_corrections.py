"""vault transaction corrections (VAU-08): corrected entry links the original

Le registre reste en ajout seul : corriger = écriture inverse de l'originale + transaction
corrigée, dans la même écriture ; la corrigée porte `corrects_transaction_id`.

Revision ID: 20261018_0074
Revises: 20261018_0073
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261018_0074"
down_revision: str | None = "20261018_0073"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "imperium_vault_transactions",
        sa.Column("corrects_transaction_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("imperium_vault_transactions.id"), nullable=True),
    )
    op.create_index(
        "imperium_vault_transactions_one_correction_idx", "imperium_vault_transactions", ["corrects_transaction_id"],
        unique=True, postgresql_where=sa.text("corrects_transaction_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("imperium_vault_transactions_one_correction_idx", table_name="imperium_vault_transactions")
    op.drop_column("imperium_vault_transactions", "corrects_transaction_id")
