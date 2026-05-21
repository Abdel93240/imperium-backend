"""add imperium weekly review states

Revision ID: 20260427_0010
Revises: 20260426_0009
Create Date: 2026-04-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260427_0010"
down_revision: str | None = "20260426_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "imperium_weekly_review_states",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("ready", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("launched", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("launched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("analysis_status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("analysis_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="imperium_weekly_review_states_user_id_fkey",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "user_id",
            "week_start",
            name="imperium_weekly_review_states_user_week_start_unique",
        ),
    )
    op.create_index(
        "imperium_weekly_review_states_user_week_start_idx",
        "imperium_weekly_review_states",
        ["user_id", "week_start"],
    )
    op.create_index(
        "imperium_weekly_review_states_user_ready_true_idx",
        "imperium_weekly_review_states",
        ["user_id", "ready"],
        postgresql_where=sa.text("ready = TRUE"),
    )


def downgrade() -> None:
    op.drop_index("imperium_weekly_review_states_user_ready_true_idx", table_name="imperium_weekly_review_states")
    op.drop_index("imperium_weekly_review_states_user_week_start_idx", table_name="imperium_weekly_review_states")
    op.drop_table("imperium_weekly_review_states")
