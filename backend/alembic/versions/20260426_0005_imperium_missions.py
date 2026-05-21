"""add imperium missions

Revision ID: 20260426_0005
Revises: 20260426_0004
Create Date: 2026-04-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260426_0005"
down_revision: str | None = "20260426_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "imperium_missions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("priority_level", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("planned_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("planned_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completion_note", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("user_reported_signals", postgresql.JSONB(), nullable=True),
        sa.Column("ai_usable_reason", sa.Boolean(), nullable=True),
        sa.Column("created_by_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ended_by_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('active', 'completed', 'failed', 'cancelled')",
            name="imperium_missions_status_check",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="imperium_missions_user_id_fkey"),
        sa.ForeignKeyConstraint(
            ["created_by_event_id"],
            ["events.id"],
            name="imperium_missions_created_by_event_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["ended_by_event_id"],
            ["events.id"],
            name="imperium_missions_ended_by_event_id_fkey",
        ),
    )
    op.create_index(
        "imperium_missions_one_active_per_user_idx",
        "imperium_missions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index("imperium_missions_user_status_idx", "imperium_missions", ["user_id", "status"])
    op.create_index("imperium_missions_started_at_idx", "imperium_missions", ["started_at"])


def downgrade() -> None:
    op.drop_index("imperium_missions_started_at_idx", table_name="imperium_missions")
    op.drop_index("imperium_missions_user_status_idx", table_name="imperium_missions")
    op.drop_index("imperium_missions_one_active_per_user_idx", table_name="imperium_missions")
    op.drop_table("imperium_missions")
