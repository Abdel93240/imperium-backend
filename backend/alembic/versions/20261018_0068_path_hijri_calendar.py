"""path hijri calendar: confirmed month starts and personal religious events (doc 41 14-V3)

Le calendrier se calcule (calendrier tabulaire) ; le début d'un mois dépend de
l'observation : tant qu'il n'est pas confirmé par l'utilisateur, une date est affichée en
double (J et J+1). `path_hijri_month_starts` garde les débuts confirmés ;
`path_calendar_events` les événements personnels (une année précise ou chaque année).

Revision ID: 20261018_0068
Revises: 20261018_0067
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261018_0068"
down_revision: str | None = "20261018_0067"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "path_hijri_month_starts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hijri_year", sa.Integer(), nullable=False),
        sa.Column("hijri_month", sa.Integer(), nullable=False),
        sa.Column("first_day", sa.Date(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "hijri_year", "hijri_month", name="path_hijri_month_starts_user_month_unique"),
        sa.CheckConstraint("hijri_month BETWEEN 1 AND 12", name="month_range"),
        sa.CheckConstraint("hijri_year BETWEEN 1300 AND 1700", name="year_range"),
    )
    op.create_table(
        "path_calendar_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("hijri_year", sa.Integer(), nullable=True),
        sa.Column("hijri_month", sa.Integer(), nullable=False),
        sa.Column("hijri_day", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("length(btrim(label)) BETWEEN 1 AND 120", name="label_length"),
        sa.CheckConstraint("hijri_month BETWEEN 1 AND 12", name="month_range"),
        sa.CheckConstraint("hijri_day BETWEEN 1 AND 30", name="day_range"),
        sa.CheckConstraint("hijri_year IS NULL OR hijri_year BETWEEN 1300 AND 1700", name="year_range"),
    )
    op.create_index(
        "path_calendar_events_user_idempotency_idx", "path_calendar_events", ["user_id", "idempotency_key"], unique=True
    )


def downgrade() -> None:
    op.drop_index("path_calendar_events_user_idempotency_idx", table_name="path_calendar_events")
    op.drop_table("path_calendar_events")
    op.drop_table("path_hijri_month_starts")
