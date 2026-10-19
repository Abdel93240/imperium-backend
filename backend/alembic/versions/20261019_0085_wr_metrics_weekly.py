"""wr metrics weekly: per-user weekly WR metrics + disabled rollup job (spec WR §3.8, §7, §12)

Une ligne par utilisateur et par semaine (lundi), recalculée par le job `wr.metrics_rollup`
(semé désactivé). wr_mode porte la politique de saut : `skipped` quand aucun WR n'a été lancé
pour la semaine une fois sa fenêtre close.

Revision ID: 20261019_0085
Revises: 20261019_0084
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261019_0085"
down_revision: str | None = "20261019_0084"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COUNTERS = (
    "factory_runs", "events_processed", "chain_proposals", "patterns_new", "patterns_reinforced",
    "contradictions", "docket_created", "docket_validated", "docket_refused", "docket_deferred",
    "docket_forced_decisions", "wr_duration_min",
)


def upgrade() -> None:
    op.create_table(
        "wr_metrics_weekly",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        *[sa.Column(name, sa.Integer(), nullable=True) for name in COUNTERS],
        sa.Column("wr_mode", sa.Text(), nullable=True),
        sa.Column("cloud_cost_estimate", sa.Numeric(), nullable=True),
        sa.Column("agreement_by_slot", postgresql.JSONB(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "week_start", name="wr_metrics_weekly_user_week_unique"),
        sa.CheckConstraint("extract(isodow from week_start) = 1", name="wr_metrics_weekly_monday_check"),
        sa.CheckConstraint("wr_mode IS NULL OR wr_mode IN ('full', 'light', 'skipped')",
                           name="wr_metrics_weekly_mode_check"),
    )
    op.execute(
        """
        INSERT INTO job_definitions
          (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s)
        VALUES (gen_random_uuid(), 'wr.metrics_rollup', 'cron', '30 4 * * *', NULL,
                'app.services.wr.metrics:metrics_rollup_job', false, true, 300)
        ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM job_definitions WHERE code = 'wr.metrics_rollup'")
    op.drop_table("wr_metrics_weekly")
