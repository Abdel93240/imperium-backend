"""add imperium priority rules

Revision ID: 20260426_0006
Revises: 20260426_0005
Create Date: 2026-04-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260426_0006"
down_revision: str | None = "20260426_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "imperium_priority_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("priority_key", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("rank_order", sa.Integer(), nullable=False),
        sa.Column("importance_score", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("updated_by_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("rank_order > 0", name="imperium_priority_rules_rank_order_positive"),
        sa.CheckConstraint(
            "importance_score IS NULL OR (importance_score >= 1 AND importance_score <= 100)",
            name="imperium_priority_rules_importance_score_range",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="imperium_priority_rules_user_id_fkey"),
        sa.ForeignKeyConstraint(
            ["updated_by_event_id"],
            ["events.id"],
            name="imperium_priority_rules_updated_by_event_id_fkey",
        ),
    )
    op.create_index(
        "imperium_priority_rules_active_rank_unique_idx",
        "imperium_priority_rules",
        ["user_id", "rank_order"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "imperium_priority_rules_active_key_unique_idx",
        "imperium_priority_rules",
        ["user_id", "priority_key"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "imperium_priority_rules_user_active_rank_idx",
        "imperium_priority_rules",
        ["user_id", "is_active", "rank_order"],
    )


def downgrade() -> None:
    op.drop_index("imperium_priority_rules_user_active_rank_idx", table_name="imperium_priority_rules")
    op.drop_index("imperium_priority_rules_active_key_unique_idx", table_name="imperium_priority_rules")
    op.drop_index("imperium_priority_rules_active_rank_unique_idx", table_name="imperium_priority_rules")
    op.drop_table("imperium_priority_rules")
