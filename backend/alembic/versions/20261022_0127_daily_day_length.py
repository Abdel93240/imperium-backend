"""daily day length: a late-started operational day does not end at midnight

`daily.day_length_hours` = 16 : sans engagement fixe, le temps restant de la sélection court jusqu'à minuit, ou
jusqu'à 16 h après le démarrage de la journée si elle a commencé tard (journée démarrée à 23 h 46 : rien ne
tenait avant minuit, constaté le 2026-10-21).

Revision ID: 20261022_0127
Revises: 20261021_0126
Create Date: 2026-10-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261022_0127"
down_revision: str | None = "20261021_0126"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version)
        VALUES (gen_random_uuid(), 'daily.day_length_hours', 'daily', '16'::jsonb, 'h',
                'Durée minimale d''une journée opérationnelle depuis son démarrage (au-delà de minuit si elle a commencé tard).',
                'seed', 1)
        ON CONFLICT ON CONSTRAINT parameters_code_version_unique DO NOTHING
        """
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = 'daily.day_length_hours'")
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
