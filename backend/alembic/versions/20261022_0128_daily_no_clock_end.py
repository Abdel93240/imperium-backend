"""daily: no clock end for the day (user decision 2026-10-22) — remove `daily.day_length_hours`

Une journée Imperium dure tant que ses missions l'exigent : sans engagement fixe, la sélection regarde les 24 h
qui viennent ; le réglage de durée minimale (migration 0127) n'a plus de sens.

Revision ID: 20261022_0128
Revises: 20261022_0127
Create Date: 2026-10-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261022_0128"
down_revision: str | None = "20261022_0127"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = 'daily.day_length_hours'")
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")


def downgrade() -> None:
    op.execute(
        """
        INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version)
        VALUES (gen_random_uuid(), 'daily.day_length_hours', 'daily', '16'::jsonb, 'h',
                'Durée minimale d''une journée opérationnelle depuis son démarrage (au-delà de minuit si elle a commencé tard).',
                'seed', 1)
        ON CONFLICT ON CONSTRAINT parameters_code_version_unique DO NOTHING
        """
    )
