"""vault pressure manual corrections: postponed, handled, exceptional week (doc 11)

Journal en ajout seul ; une correction se révoque. Une correction active au plus par
échéance et par semaine.

Revision ID: 20261018_0079
Revises: 20261018_0078
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261018_0079"
down_revision: str | None = "20261018_0078"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "vault_pressure_corrections",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("upcoming_expense_id", UUID, sa.ForeignKey("upcoming_expenses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("postponed_until", sa.Date(), nullable=True),
        sa.Column("week_start", sa.Date(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("kind IN ('postponed', 'handled', 'exceptional_week')", name="kind_check"),
        sa.CheckConstraint(
            "(kind = 'exceptional_week') = (week_start IS NOT NULL AND upcoming_expense_id IS NULL)", name="target_check"
        ),
        sa.CheckConstraint("(kind = 'postponed') = (postponed_until IS NOT NULL)", name="postponed_until_check"),
        sa.CheckConstraint("week_start IS NULL OR extract(isodow from week_start) = 1", name="week_start_monday"),
        sa.CheckConstraint("length(btrim(reason)) > 0", name="reason_present"),
    )
    op.create_index("vault_pressure_corrections_user_idempotency_idx", "vault_pressure_corrections",
                    ["user_id", "idempotency_key"], unique=True)
    op.create_index("vault_pressure_corrections_one_active_expense_idx", "vault_pressure_corrections",
                    ["upcoming_expense_id"], unique=True,
                    postgresql_where=sa.text("revoked_at IS NULL AND upcoming_expense_id IS NOT NULL"))
    op.create_index("vault_pressure_corrections_one_active_week_idx", "vault_pressure_corrections",
                    ["user_id", "week_start"], unique=True,
                    postgresql_where=sa.text("revoked_at IS NULL AND week_start IS NOT NULL"))


def downgrade() -> None:
    op.drop_table("vault_pressure_corrections")
