"""add operational planning days

Revision ID: 20260923_0042
Revises: 20260716_0041
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260923_0042"
down_revision: str | None = "20260716_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "planning_days",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("start_local_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("felt_energy", sa.SmallInteger(), nullable=False),
        sa.Column("day_review_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "felt_energy >= 1 AND felt_energy <= 5",
            name="felt_energy_range",
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="finished_after_started",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="planning_days_user_id_fkey"),
        sa.ForeignKeyConstraint(
            ["day_review_id"],
            ["imperium_day_reviews.id"],
            name="planning_days_day_review_id_fkey",
        ),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="planning_days_user_idempotency_key_unique",
        ),
    )
    op.create_index(
        "planning_days_one_open_per_user_idx",
        "planning_days",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("finished_at IS NULL"),
    )
    op.create_index(
        "planning_days_user_started_at_idx",
        "planning_days",
        ["user_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("planning_days_user_started_at_idx", table_name="planning_days")
    op.drop_index("planning_days_one_open_per_user_idx", table_name="planning_days")
    op.drop_table("planning_days")
