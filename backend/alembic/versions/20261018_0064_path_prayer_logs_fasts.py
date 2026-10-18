"""path prayer logs (PAT-02) and fasts (PAT-05), doc 41 §7–§8

Prière marquée : une ligne par prière et par jour, jamais déduite (statut accomplished
ou not_marked_as_accomplished ; effacer le statut supprime la ligne). Jeûne : un par jour,
un seul en cours, fenêtre suhoor → iftar figée au démarrage ; fin et rupture toujours
confirmées par l'utilisateur. Pulse lit la fenêtre pour bloquer l'hydratation.

Revision ID: 20261018_0064
Revises: 20261017_0063
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261018_0064"
down_revision: str | None = "20261017_0063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.create_table(
        "path_prayer_logs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prayer_date", sa.Date(), nullable=False),
        sa.Column("prayer_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("prayed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "prayer_date", "prayer_name", name="path_prayer_logs_user_day_prayer_unique"),
        sa.CheckConstraint(f"prayer_name IN ({_in(('fajr', 'dhuhr', 'asr', 'maghrib', 'isha'))})", name="prayer_name_check"),
        sa.CheckConstraint(f"status IN ({_in(('accomplished', 'not_marked_as_accomplished'))})", name="status_check"),
        sa.CheckConstraint("status = 'accomplished' OR prayed_at IS NULL", name="prayed_at_only_accomplished"),
        sa.CheckConstraint("version >= 1", name="version_positive"),
    )
    op.create_table(
        "path_fasts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fasting_date", sa.Date(), nullable=False),
        sa.Column("fasting_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("suhoor_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("iftar_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("times_source", sa.Text(), nullable=False),
        sa.Column("hydration_daytime_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("broken_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("break_reason", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "fasting_date", name="path_fasts_user_date_unique"),
        sa.CheckConstraint(
            f"fasting_type IN ({_in(('monday_thursday', 'white_days', 'ramadan', 'custom', 'temporary'))})",
            name="fasting_type_check",
        ),
        sa.CheckConstraint(f"status IN ({_in(('active', 'ended', 'broken'))})", name="status_check"),
        sa.CheckConstraint("suhoor_at < iftar_at", name="window_order"),
        sa.CheckConstraint("status <> 'ended' OR ended_at IS NOT NULL", name="ended_has_time"),
        sa.CheckConstraint("status <> 'broken' OR broken_at IS NOT NULL", name="broken_has_time"),
        sa.CheckConstraint("version >= 1", name="version_positive"),
    )
    op.create_index(
        "path_fasts_one_active_idx", "path_fasts", ["user_id"], unique=True, postgresql_where=sa.text("status = 'active'")
    )
    op.create_index("path_fasts_user_idempotency_idx", "path_fasts", ["user_id", "idempotency_key"], unique=True)


def downgrade() -> None:
    op.drop_index("path_fasts_user_idempotency_idx", table_name="path_fasts")
    op.drop_index("path_fasts_one_active_idx", table_name="path_fasts")
    op.drop_table("path_fasts")
    op.drop_table("path_prayer_logs")
