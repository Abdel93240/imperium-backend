"""imperium user settings

Doc 43 §15, doc 65 §8.5 ; décisions utilisateur 2026-10-15/16/17 (pas d'heure de popup,
pas de notification de check-in, mode IA Équilibré par défaut, délai de replan 5 min,
conservation du chat 90 jours).

Revision ID: 20261017_0049
Revises: 20261017_0048
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261017_0049"
down_revision: str | None = "20261017_0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _flag(name: str) -> sa.Column:
    return sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.text("true"))


def upgrade() -> None:
    op.create_table(
        "imperium_user_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        _flag("bubble_enabled"),
        _flag("notifications_enabled"),
        _flag("notify_weekly_review"),
        _flag("notify_mission_reminders"),
        _flag("notify_red_alerts"),
        _flag("morning_popup_enabled"),
        sa.Column("ai_mode", sa.Text(), nullable=False, server_default=sa.text("'equilibre'")),
        sa.Column("replan_on_failure_urgent", sa.Text(), nullable=False, server_default=sa.text("'replan'")),
        sa.Column("replan_on_failure_other", sa.Text(), nullable=False, server_default=sa.text("'ask'")),
        sa.Column("replan_debounce_minutes", sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column("chat_retention_days", sa.Integer(), nullable=False, server_default=sa.text("90")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="user_unique"),
        sa.CheckConstraint("ai_mode IN ('strict', 'equilibre', 'souple')", name="ai_mode_check"),
        sa.CheckConstraint("replan_on_failure_urgent IN ('replan', 'ask')", name="failure_urgent_check"),
        sa.CheckConstraint("replan_on_failure_other IN ('replan', 'ask')", name="failure_other_check"),
        sa.CheckConstraint("replan_debounce_minutes >= 1 AND replan_debounce_minutes <= 120", name="debounce_range"),
        sa.CheckConstraint("chat_retention_days IN (30, 60, 90, 180, 365)", name="retention_choices"),
    )


def downgrade() -> None:
    op.drop_table("imperium_user_settings")
