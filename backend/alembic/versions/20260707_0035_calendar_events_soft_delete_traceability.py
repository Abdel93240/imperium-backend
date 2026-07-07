"""calendar events soft delete traceability

Revision ID: 20260707_0035
Revises: 20260707_0034
Create Date: 2026-07-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260707_0035"
down_revision: str | None = "20260707_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "imperium_calendar_events",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("imperium_calendar_events", sa.Column("deleted_by", sa.Text(), nullable=True))
    op.add_column("imperium_calendar_events", sa.Column("deletion_reason", sa.Text(), nullable=True))
    op.add_column("imperium_calendar_events", sa.Column("created_by", sa.Text(), nullable=True))
    op.add_column("imperium_calendar_events", sa.Column("updated_by", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("imperium_calendar_events", "updated_by")
    op.drop_column("imperium_calendar_events", "created_by")
    op.drop_column("imperium_calendar_events", "deletion_reason")
    op.drop_column("imperium_calendar_events", "deleted_by")
    op.drop_column("imperium_calendar_events", "deleted_at")
