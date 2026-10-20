"""local AI slot switch (off|shadow|live per slot), longer timeouts for the Pulse runners (décision : IA locale)

1. Paramètre `ai.local_slot_modes` ({slot_code: off|shadow|live}) semé VIDE : aucun slot n'appelle
   l'exécuteur local tant qu'il n'est pas nommé ici. Seuls les slots `local_default` peuvent l'être.
2. `pulse.dispatch_runner` et `pulse.procedure_runner` : timeout 120 → 600 s (un appel local prend
   quelques secondes ; chaque passe traite au plus 3 éléments quand un slot local est allumé).

Revision ID: 20261020_0114
Revises: 20261020_0113
Create Date: 2026-10-20
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261020_0114"
down_revision: str | None = "20261020_0113"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOBS = "('pulse.dispatch_runner', 'pulse.procedure_runner')"


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version)
        VALUES (gen_random_uuid(), 'ai.local_slot_modes', 'ai', '{}'::jsonb, 'json',
                'Slots servis par l''exécuteur local : {slot_code: off|shadow|live}. Vide = aucun.', 'seed', 1)
        ON CONFLICT ON CONSTRAINT parameters_code_version_unique DO NOTHING
        """
    )
    op.execute(f"UPDATE job_definitions SET timeout_s = 600 WHERE code IN {JOBS}")


def downgrade() -> None:
    op.execute(f"UPDATE job_definitions SET timeout_s = 120 WHERE code IN {JOBS}")
    op.execute("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    op.execute("DELETE FROM parameters WHERE code = 'ai.local_slot_modes'")
    op.execute("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
