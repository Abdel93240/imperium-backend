"""add imperium path items

Revision ID: 20260426_0008
Revises: 20260426_0007
Create Date: 2026-04-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260426_0008"
down_revision: str | None = "20260426_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "imperium_path_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False, server_default="Europe/Paris"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("priority_key", sa.Text(), nullable=True),
        sa.Column("planned_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("planned_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False, server_default="manual"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skip_reason", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("skipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('planned', 'in_progress', 'completed', 'skipped', 'cancelled')",
            name="imperium_path_items_status_check",
        ),
        sa.CheckConstraint(
            "source IN ('manual', 'system', 'ai_planned')",
            name="imperium_path_items_source_check",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="imperium_path_items_user_id_fkey"),
    )
    op.create_index("imperium_path_items_user_local_date_idx", "imperium_path_items", ["user_id", "local_date"])
    op.create_index("imperium_path_items_user_status_idx", "imperium_path_items", ["user_id", "status"])
    op.create_index(
        "imperium_path_items_user_planned_start_idx",
        "imperium_path_items",
        ["user_id", "planned_start"],
    )
    op.create_index(
        "imperium_path_items_user_local_date_sort_idx",
        "imperium_path_items",
        ["user_id", "local_date", "sort_order"],
    )


def downgrade() -> None:
    op.drop_index("imperium_path_items_user_local_date_sort_idx", table_name="imperium_path_items")
    op.drop_index("imperium_path_items_user_planned_start_idx", table_name="imperium_path_items")
    op.drop_index("imperium_path_items_user_status_idx", table_name="imperium_path_items")
    op.drop_index("imperium_path_items_user_local_date_idx", table_name="imperium_path_items")
    op.drop_table("imperium_path_items")
