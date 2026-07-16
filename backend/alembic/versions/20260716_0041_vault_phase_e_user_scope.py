"""vault phase e user scope

Revision ID: 20260716_0041
Revises: 20260716_0040
Create Date: 2026-07-16

Phase E Vault runtime tables must be scoped by the authenticated user. Existing
single-user rows are backfilled to the first user before the NOT NULL guards are
installed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "20260716_0041"
down_revision: str | None = "20260716_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("upcoming_expenses", sa.Column("user_id", UUID(as_uuid=True), nullable=True))
    op.add_column("weekly_finance_summaries", sa.Column("user_id", UUID(as_uuid=True), nullable=True))
    op.add_column("pressure_snapshots", sa.Column("user_id", UUID(as_uuid=True), nullable=True))

    conn = op.get_bind()
    for table_name in ("upcoming_expenses", "weekly_finance_summaries", "pressure_snapshots"):
        conn.exec_driver_sql(
            f"""
            UPDATE {table_name}
            SET user_id = (SELECT id FROM users ORDER BY created_at LIMIT 1)
            WHERE user_id IS NULL
            """
        )
        op.alter_column(table_name, "user_id", nullable=False)

    op.create_foreign_key("upcoming_expenses_user_id_fkey", "upcoming_expenses", "users", ["user_id"], ["id"])
    op.create_foreign_key(
        "weekly_finance_summaries_user_id_fkey",
        "weekly_finance_summaries",
        "users",
        ["user_id"],
        ["id"],
    )
    op.create_foreign_key("pressure_snapshots_user_id_fkey", "pressure_snapshots", "users", ["user_id"], ["id"])

    op.drop_constraint("weekly_finance_summaries_pkey", "weekly_finance_summaries", type_="primary")
    op.create_primary_key("weekly_finance_summaries_pkey", "weekly_finance_summaries", ["user_id", "week_start"])
    op.create_index(
        "upcoming_expenses_user_active_due_idx",
        "upcoming_expenses",
        ["user_id", "active", "due_date"],
    )
    op.create_index(
        "pressure_snapshots_user_computed_at_idx",
        "pressure_snapshots",
        ["user_id", sa.text("computed_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("pressure_snapshots_user_computed_at_idx", table_name="pressure_snapshots")
    op.drop_index("upcoming_expenses_user_active_due_idx", table_name="upcoming_expenses")
    op.drop_constraint("weekly_finance_summaries_pkey", "weekly_finance_summaries", type_="primary")
    op.create_primary_key("weekly_finance_summaries_pkey", "weekly_finance_summaries", ["week_start"])
    op.drop_constraint("pressure_snapshots_user_id_fkey", "pressure_snapshots", type_="foreignkey")
    op.drop_constraint("weekly_finance_summaries_user_id_fkey", "weekly_finance_summaries", type_="foreignkey")
    op.drop_constraint("upcoming_expenses_user_id_fkey", "upcoming_expenses", type_="foreignkey")
    op.drop_column("pressure_snapshots", "user_id")
    op.drop_column("weekly_finance_summaries", "user_id")
    op.drop_column("upcoming_expenses", "user_id")
