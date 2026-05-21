"""Prevent duplicate Decision Framework mission scores per source.

Revision ID: 20260511_0021
Revises: 20260511_0020
Create Date: 2026-05-11
"""

from __future__ import annotations

from alembic import op


revision: str = "20260511_0021"
down_revision: str | None = "20260511_0020"
branch_labels: str | None = None
depends_on: str | None = None


INDEX_NAME = "imperium_mission_scores_user_mission_source_unique_idx"


def upgrade() -> None:
    op.create_index(
        INDEX_NAME,
        "imperium_mission_scores",
        ["user_id", "mission_id", "source"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="imperium_mission_scores")
