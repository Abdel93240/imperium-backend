"""wr monthly regen job: monthly anti-drift regeneration of the plan, seeded disabled (spec WR §8.3, ACT-WR-21)

Job `wr.monthly_regen` (cron le 1er du mois à 05:00, À VALIDER face au doc 52 §8 / DV-5), semé
désactivé. Même contrat que le choc (§8.1) avec origin=monthly_regen : version `proposed`, jamais
activée seule ; essai à blanc tant que `real_ai_enabled` est faux. Pas de DDL.

Revision ID: 20261019_0100
Revises: 20261019_0099
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261019_0100"
down_revision: str | None = "20261019_0099"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO job_definitions
          (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s)
        VALUES (gen_random_uuid(), 'wr.monthly_regen', 'cron', '0 5 1 * *', NULL,
                'app.services.wr.plan:monthly_regen_job', false, true, 300)
        ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM job_definitions WHERE code = 'wr.monthly_regen'")
