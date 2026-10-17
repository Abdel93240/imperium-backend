"""imperium projects, routines and routine checks; project fields on missions

Doc 71 §3, §4.1, §8 ; doc 01 (project_*, routine_*) ; décisions utilisateur 2026-10-15/16/17.
Noms canoniques fixés ici (doc 05 : pas de `projects` générique).

Revision ID: 20261017_0047
Revises: 20261017_0046
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261017_0047"
down_revision: str | None = "20261017_0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.create_table(
        "imperium_projects",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("rank_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'open'")),
        sa.Column("source", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("progress_percent", sa.Integer(), nullable=True),
        sa.Column("progress_why", sa.Text(), nullable=True),
        sa.Column("progress_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completion_method", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("status IN ('open', 'completed', 'deleted')", name="status_check"),
        sa.CheckConstraint("source IN ('manual', 'chatbot')", name="source_check"),
        sa.CheckConstraint("length(btrim(title)) > 0", name="title_not_blank"),
        sa.CheckConstraint("rank_order > 0", name="rank_positive"),
        sa.CheckConstraint("progress_percent IS NULL OR (progress_percent >= 0 AND progress_percent <= 100)", name="progress_range"),
        sa.CheckConstraint("completion_method IS NULL OR completion_method IN ('suggested', 'manual')", name="completion_method_check"),
    )
    op.create_index("imperium_projects_user_status_rank_idx", "imperium_projects", ["user_id", "status", "rank_order"])
    op.create_index(
        "imperium_projects_user_idempotency_idx",
        "imperium_projects",
        ["user_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.add_column("imperium_missions", sa.Column("project_id", UUID, sa.ForeignKey("imperium_projects.id"), nullable=True))
    op.add_column("imperium_missions", sa.Column("project_position", sa.Integer(), nullable=True))
    op.add_column("imperium_missions", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("imperium_missions", sa.Column("notes", sa.Text(), nullable=True))
    op.create_index(
        "imperium_missions_project_position_idx",
        "imperium_missions",
        ["project_id", "project_position"],
        postgresql_where=sa.text("project_id IS NOT NULL"),
    )

    op.create_table(
        "imperium_routines",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("frequency", sa.Text(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("priority", sa.Text(), nullable=False, server_default=sa.text("'medium'")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("pinned_weekday", sa.SmallInteger(), nullable=True),
        sa.Column("pinned_month_day", sa.SmallInteger(), nullable=True),
        sa.Column("pinned_time", sa.Time(), nullable=True),
        sa.Column("anchor_date", sa.Date(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("frequency IN ('daily', 'weekly', 'biweekly', 'monthly')", name="frequency_check"),
        sa.CheckConstraint("priority IN ('low', 'medium', 'high')", name="priority_check"),
        sa.CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        sa.CheckConstraint("estimated_minutes IS NULL OR estimated_minutes > 0", name="estimated_minutes_positive"),
        sa.CheckConstraint("pinned_weekday IS NULL OR (pinned_weekday >= 1 AND pinned_weekday <= 7)", name="pinned_weekday_range"),
        sa.CheckConstraint("pinned_month_day IS NULL OR (pinned_month_day >= 1 AND pinned_month_day <= 31)", name="pinned_month_day_range"),
    )
    op.create_index("imperium_routines_user_active_idx", "imperium_routines", ["user_id", "active"])
    op.create_index(
        "imperium_routines_user_idempotency_idx",
        "imperium_routines",
        ["user_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.create_table(
        "imperium_routine_checks",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("routine_id", UUID, sa.ForeignKey("imperium_routines.id"), nullable=False),
        sa.Column("planning_day_id", UUID, sa.ForeignKey("planning_days.id"), nullable=True),
        sa.Column("operational_date", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("status IN ('planned', 'done', 'missed')", name="status_check"),
        sa.UniqueConstraint("routine_id", "operational_date", name="routine_day_unique"),
    )
    op.create_index("imperium_routine_checks_user_date_idx", "imperium_routine_checks", ["user_id", "operational_date"])


def downgrade() -> None:
    op.drop_index("imperium_routine_checks_user_date_idx", table_name="imperium_routine_checks")
    op.drop_table("imperium_routine_checks")
    op.drop_index("imperium_routines_user_idempotency_idx", table_name="imperium_routines")
    op.drop_index("imperium_routines_user_active_idx", table_name="imperium_routines")
    op.drop_table("imperium_routines")
    op.drop_index("imperium_missions_project_position_idx", table_name="imperium_missions")
    op.drop_column("imperium_missions", "notes")
    op.drop_column("imperium_missions", "description")
    op.drop_column("imperium_missions", "project_position")
    op.drop_column("imperium_missions", "project_id")
    op.drop_index("imperium_projects_user_idempotency_idx", table_name="imperium_projects")
    op.drop_index("imperium_projects_user_status_rank_idx", table_name="imperium_projects")
    op.drop_table("imperium_projects")
