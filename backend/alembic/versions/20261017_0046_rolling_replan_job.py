"""seed runner job imperium.rolling_replan

Abonné à planning.replan.requested et planning.replan.revision_requested (doc 43 §3.2).
Comme les autres jobs du socle, il est semé DÉSACTIVÉ (enabled=false) : l'activation
suit la feuille d'activation (doc 76), avec le drapeau global runner_enabled.

Revision ID: 20261017_0046
Revises: 20261017_0045
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261017_0046"
down_revision: str | None = "20261017_0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_CODE = "imperium.rolling_replan"
EVENT_TYPES = ["planning.replan.requested", "planning.replan.revision_requested"]
HANDLER_REF = "app.services.imperium.replan_runner:rolling_replan_job"


def upgrade() -> None:
    op.get_bind().exec_driver_sql(
        """
        INSERT INTO job_definitions
          (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s)
        VALUES (gen_random_uuid(), %s, 'event_subscription', NULL, %s, %s, false, true, 120)
        ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING
        """,
        (JOB_CODE, EVENT_TYPES, HANDLER_REF),
    )


def downgrade() -> None:
    op.get_bind().exec_driver_sql("DELETE FROM job_definitions WHERE code = %s", (JOB_CODE,))
