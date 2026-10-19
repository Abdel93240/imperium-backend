"""daily settings flag: versioned scoring settings routes switched off at seed (spec Daily §4.5, ACT-DLY-02)

Paramètre `daily.settings_enabled` = false : `GET/PUT /api/daily/settings/scoring` coupés tant
qu'il est faux (bascule `daily_settings_enabled` de la carte). Pas de DDL : chaque réglage est une
nouvelle version d'un paramètre `df.*` (table append-only).

Revision ID: 20261019_0102
Revises: 20261019_0101
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261019_0102"
down_revision: str | None = "20261019_0101"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CODE = "daily.settings_enabled"


def upgrade() -> None:
    op.get_bind().exec_driver_sql(
        """
        INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version)
        VALUES (gen_random_uuid(), %s, 'daily', 'false'::jsonb, 'bool',
                'Réglage versionné des barèmes df.* par GET/PUT /api/daily/settings/scoring (carte ACT-DLY-02). Coupé au seed.',
                'seed', 1)
        ON CONFLICT ON CONSTRAINT parameters_code_version_unique DO NOTHING
        """,
        (CODE,),
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = %s", (CODE,))
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
