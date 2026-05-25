"""add imperium pulse entries

Revision ID: 20260525_0028
Revises: 20260525_0027
Create Date: 2026-05-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260525_0028"
down_revision: str | None = "20260525_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "imperium_pulse_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("sleep_hours", sa.Numeric(4, 2), nullable=True),
        sa.Column("energy_level", sa.SmallInteger(), nullable=True),
        sa.Column("fatigue_level", sa.SmallInteger(), nullable=True),
        sa.Column("weight_kg", sa.Numeric(5, 2), nullable=True),
        sa.Column("workout_done", sa.Boolean(), nullable=True),
        sa.Column("workout_type", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "sleep_hours IS NULL OR (sleep_hours >= 0 AND sleep_hours <= 24)",
            name="imperium_pulse_entries_sleep_hours_range",
        ),
        sa.CheckConstraint(
            "energy_level IS NULL OR (energy_level >= 1 AND energy_level <= 10)",
            name="imperium_pulse_entries_energy_level_range",
        ),
        sa.CheckConstraint(
            "fatigue_level IS NULL OR (fatigue_level >= 1 AND fatigue_level <= 10)",
            name="imperium_pulse_entries_fatigue_level_range",
        ),
        sa.CheckConstraint(
            "weight_kg IS NULL OR weight_kg > 0",
            name="imperium_pulse_entries_weight_kg_positive",
        ),
        sa.CheckConstraint(
            "workout_done IS DISTINCT FROM false OR workout_type IS NULL",
            name="imperium_pulse_entries_workout_type_requires_workout_done",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="imperium_pulse_entries_user_id_fkey"),
        sa.UniqueConstraint("user_id", "entry_date", name="imperium_pulse_entries_user_entry_date_unique"),
    )
    op.create_index(
        "imperium_pulse_entries_user_entry_date_desc_idx",
        "imperium_pulse_entries",
        ["user_id", sa.text("entry_date DESC")],
    )


def downgrade() -> None:
    op.drop_index("imperium_pulse_entries_user_entry_date_desc_idx", table_name="imperium_pulse_entries")
    op.drop_table("imperium_pulse_entries")
