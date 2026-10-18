"""planning daily plan versions: living plan history, one row per accepted replan (doc 43 §20, D4)

Revision ID: 20261018_0080
Revises: 20261018_0079
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261018_0080"
down_revision: str | None = "20261018_0079"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "planning_daily_plan_versions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("daily_plan_id", UUID, sa.ForeignKey("imperium_daily_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("plan_blocks", postgresql.JSONB(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("trigger", sa.Text(), nullable=True),
        sa.Column("source_replan_event_id", UUID, sa.ForeignKey("planning_replan_events.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("daily_plan_id", "version", name="planning_daily_plan_versions_plan_version_unique"),
        sa.CheckConstraint("version >= 0", name="version_non_negative"),
        sa.CheckConstraint("jsonb_typeof(plan_blocks) = 'array'", name="plan_blocks_array"),
    )


def downgrade() -> None:
    op.drop_table("planning_daily_plan_versions")
