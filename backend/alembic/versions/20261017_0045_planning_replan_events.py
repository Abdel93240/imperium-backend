"""planning replan events (rolling replan requests, proposals, decisions)

Doc 43 §3.2–§3.4, doc 59 §12.6, décisions utilisateur 2026-10-16/17 :
- demande manuelle : catégorie (doc 01) + détails obligatoires ;
- délai de 5 min entre deux replanifications (manuelles comprises) ;
- proposition déposée par le runner IA, corrigée via le chatbot, acceptée ou annulée.

Revision ID: 20261017_0045
Revises: 20261017_0044
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261017_0045"
down_revision: str | None = "20261017_0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "planning_replan_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("planning_day_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("planning_days.id"), nullable=True),
        sa.Column("daily_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("imperium_daily_plans.id"), nullable=True),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("hook_type", sa.Text(), nullable=True),
        sa.Column("reason_category", sa.Text(), nullable=True),
        sa.Column("other_reason", sa.Text(), nullable=True),
        sa.Column("reason_detail", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("ai_task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_tasks.id"), nullable=True),
        sa.Column("proposal", postgresql.JSONB(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("proposal_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("trigger IN ('manual', 'hook')", name="trigger_check"),
        sa.CheckConstraint(
            "status IN ('requested', 'proposed', 'revising', 'accepted', 'cancelled', 'failed')",
            name="status_check",
        ),
        sa.CheckConstraint(
            "reason_category IS NULL OR reason_category IN "
            "('new_event', 'wrong_estimation', 'fatigue', 'priority_shift', 'other')",
            name="reason_category_check",
        ),
        sa.CheckConstraint(
            "trigger <> 'manual' OR (reason_category IS NOT NULL AND length(btrim(coalesce(reason_detail, ''))) >= 3)",
            name="manual_reason_required",
        ),
        sa.CheckConstraint(
            "reason_category IS DISTINCT FROM 'other' OR length(btrim(coalesce(other_reason, ''))) > 0",
            name="other_reason_required",
        ),
        sa.CheckConstraint("trigger <> 'hook' OR hook_type IS NOT NULL", name="hook_type_required"),
        sa.CheckConstraint("proposal IS NULL OR jsonb_typeof(proposal) = 'array'", name="proposal_array"),
        sa.CheckConstraint("proposal_version >= 0", name="proposal_version_non_negative"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="user_idempotency_unique"),
    )
    op.create_index(
        "planning_replan_events_user_requested_idx",
        "planning_replan_events",
        ["user_id", "requested_at"],
    )
    op.create_index(
        "planning_replan_events_one_open_per_user_idx",
        "planning_replan_events",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('requested', 'proposed', 'revising')"),
    )


def downgrade() -> None:
    op.drop_index("planning_replan_events_one_open_per_user_idx", table_name="planning_replan_events")
    op.drop_index("planning_replan_events_user_requested_idx", table_name="planning_replan_events")
    op.drop_table("planning_replan_events")
