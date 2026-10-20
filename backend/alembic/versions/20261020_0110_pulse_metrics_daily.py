"""pulse daily metrics, interpreter AI slot, nightly rollup job (spec Pulse §3.9, §13, §14 ; V11 ACT-PLS-27)

1. `pulse_metrics_daily` : une ligne par utilisateur et jour de Paris (la spec n'avait que `metric_date`).
   NULL = pas encore mesurable (propositions et solveur non codés).
2. Slot `pulse.interpreter` semé dans `ai_slot_transition` (local_default, audit 100 %, cible 92 %) :
   l'agreement hebdo et la proposition de décroissance passent par le job partagé `wr.audit_weekly`
   (aucun job d'audit Pulse dédié, qui doublerait les notifications).
3. Job `pulse.metrics_rollup` (cron 00:45 UTC, semé désactivé) : recalcule les deux derniers jours clos.

Revision ID: 20261020_0110
Revises: 20261020_0109
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261020_0110"
down_revision: str | None = "20261020_0109"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
COUNTS = ("dispatches", "skipped_passes", "dispatches_useful", "dispatches_useless", "missed_reports",
          "escalations", "invalid_fallbacks", "red_flags")
NOT_YET = ("proposals", "accepted", "refused", "modified", "solver_runs", "solver_infeasible")


def upgrade() -> None:
    op.create_table(
        "pulse_metrics_daily",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        *[sa.Column(name, sa.Integer(), nullable=False) for name in COUNTS],
        *[sa.Column(name, sa.Integer(), nullable=True) for name in NOT_YET],
        sa.Column("agreement_by_slot", postgresql.JSONB(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "metric_date", name="pulse_metrics_daily_user_date_unique"),
    )
    op.execute(
        """
        INSERT INTO ai_slot_transition
          (id, slot_code, domain, tier, audit_sample_pct, agreement_target_pct, notes_fr)
        VALUES (gen_random_uuid(), 'pulse.interpreter', 'pulse', 'local_default', 100, 92,
                'Interprète Pulse : nomme les procédures depuis le board figé (spec Pulse §6).')
        ON CONFLICT ON CONSTRAINT ai_slot_transition_slot_code_unique DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO job_definitions
          (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s)
        VALUES (gen_random_uuid(), 'pulse.metrics_rollup', 'cron', '45 0 * * *', NULL,
                'app.services.pulse.metrics:rollup_job', false, true, 120)
        ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM job_definitions WHERE code = 'pulse.metrics_rollup'")
    op.execute("DELETE FROM ai_audit_samples WHERE slot_code = 'pulse.interpreter'")
    op.execute("DELETE FROM ai_slot_transition WHERE slot_code = 'pulse.interpreter'")
    op.drop_table("pulse_metrics_daily")
