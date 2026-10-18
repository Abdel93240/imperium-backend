"""vault wallet snapshots (VAU-10, doc 42 §8) and paid upcoming expenses (VAU-11, doc 42 §10)

Soldes réels saisis à la main (cash, banque, crypto en contre-valeur EUR) : la pression lit
le dernier relevé plus les transactions cash/banque passées depuis. Dépense à venir payée :
date et transaction Vault liée (sans FK, registre en ajout seul).

Revision ID: 20261018_0073
Revises: 20261018_0072
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261018_0073"
down_revision: str | None = "20261018_0072"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "vault_wallet_snapshots",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("cash_cents", sa.Integer(), nullable=False),
        sa.Column("bank_cents", sa.Integer(), nullable=False),
        sa.Column("crypto_cents", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False, server_default="manual"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("cash_cents >= 0", name="cash_not_negative"),
        sa.CheckConstraint("crypto_cents >= 0", name="crypto_not_negative"),
        sa.CheckConstraint("source IN ('manual', 'sync')", name="source_check"),
    )
    op.create_index("vault_wallet_snapshots_user_recorded_idx", "vault_wallet_snapshots", ["user_id", sa.text("recorded_at DESC")])
    op.create_index(
        "vault_wallet_snapshots_user_idempotency_idx", "vault_wallet_snapshots", ["user_id", "idempotency_key"], unique=True
    )
    op.add_column("upcoming_expenses", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("upcoming_expenses", sa.Column("paid_transaction_id", UUID, nullable=True))


def downgrade() -> None:
    op.drop_column("upcoming_expenses", "paid_transaction_id")
    op.drop_column("upcoming_expenses", "paid_at")
    op.drop_index("vault_wallet_snapshots_user_idempotency_idx", table_name="vault_wallet_snapshots")
    op.drop_index("vault_wallet_snapshots_user_recorded_idx", table_name="vault_wallet_snapshots")
    op.drop_table("vault_wallet_snapshots")
