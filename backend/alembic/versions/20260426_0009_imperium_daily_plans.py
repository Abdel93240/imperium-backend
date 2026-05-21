"""add imperium daily plans

Revision ID: 20260426_0009
Revises: 20260426_0008
Create Date: 2026-04-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260426_0009"
down_revision: str | None = "20260426_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "imperium_daily_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False, server_default="Europe/Paris"),
        sa.Column("plan_status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("focus_priority_key", sa.Text(), nullable=True),
        sa.Column("current_mission_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("generated_from", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("plan_blocks", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "plan_status IN ('draft', 'active', 'completed', 'cancelled')",
            name="imperium_daily_plans_status_check",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(plan_blocks) = 'array'",
            name="imperium_daily_plans_plan_blocks_array_check",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="imperium_daily_plans_user_id_fkey"),
        sa.ForeignKeyConstraint(
            ["current_mission_id"],
            ["imperium_missions.id"],
            name="imperium_daily_plans_current_mission_id_fkey",
        ),
        sa.UniqueConstraint("user_id", "local_date", name="imperium_daily_plans_user_local_date_unique"),
    )
    op.create_index("imperium_daily_plans_user_local_date_idx", "imperium_daily_plans", ["user_id", "local_date"])
    op.create_index("imperium_daily_plans_user_status_idx", "imperium_daily_plans", ["user_id", "plan_status"])


def downgrade() -> None:
    op.drop_index("imperium_daily_plans_user_status_idx", table_name="imperium_daily_plans")
    op.drop_index("imperium_daily_plans_user_local_date_idx", table_name="imperium_daily_plans")
    op.drop_table("imperium_daily_plans")
