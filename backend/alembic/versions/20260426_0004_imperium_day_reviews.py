"""add imperium day reviews

Revision ID: 20260426_0004
Revises: 20260426_0003
Create Date: 2026-04-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260426_0004"
down_revision: str | None = "20260426_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "imperium_day_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("day_status", sa.Text(), nullable=False),
        sa.Column("energy_level", sa.Integer(), nullable=True),
        sa.Column("fatigue_level", sa.Integer(), nullable=True),
        sa.Column("sleep_quality", sa.Integer(), nullable=True),
        sa.Column("stress_level", sa.Integer(), nullable=True),
        sa.Column("mood", sa.Text(), nullable=True),
        sa.Column("main_win", sa.Text(), nullable=True),
        sa.Column("main_problem", sa.Text(), nullable=True),
        sa.Column("completed_items", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("missed_items", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("free_text", sa.Text(), nullable=True),
        sa.Column("source_event_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="imperium_day_reviews_user_id_fkey"),
        sa.UniqueConstraint(
            "user_id",
            "local_date",
            name="imperium_day_reviews_user_local_date_unique",
        ),
    )
    op.create_index(
        "imperium_day_reviews_user_created_idx",
        "imperium_day_reviews",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("imperium_day_reviews_user_created_idx", table_name="imperium_day_reviews")
    op.drop_table("imperium_day_reviews")
