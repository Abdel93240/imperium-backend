"""imperium calendar events foundation

Revision ID: 20260512_0022
Revises: 20260511_0021
Create Date: 2026-05-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260512_0022"
down_revision: str | None = "20260511_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "imperium_calendar_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocks_time", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('event', 'deadline', 'vacation')",
            name=op.f("ck_imperium_calendar_events_imperium_calendar_events_event_type_check"),
        ),
        sa.CheckConstraint(
            "ends_at IS NULL OR ends_at >= starts_at",
            name=op.f("ck_imperium_calendar_events_imperium_calendar_events_date_range_check"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_imperium_calendar_events_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_imperium_calendar_events")),
    )
    op.create_index(
        "imperium_calendar_events_user_starts_at_idx",
        "imperium_calendar_events",
        ["user_id", "starts_at"],
        unique=False,
    )
    op.create_index(
        "imperium_calendar_events_user_event_type_idx",
        "imperium_calendar_events",
        ["user_id", "event_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("imperium_calendar_events_user_event_type_idx", table_name="imperium_calendar_events")
    op.drop_index("imperium_calendar_events_user_starts_at_idx", table_name="imperium_calendar_events")
    op.drop_table("imperium_calendar_events")
