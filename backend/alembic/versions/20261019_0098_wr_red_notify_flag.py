"""wr red notify flag: the red no longer notifies until the user switches it on (spec WR §7, ACT-WR-07)

Paramètre `wr.red_notify_enabled` = false (carte V19 ACT-WR-07, bascule `wr_red_notify_enabled`) :
tant qu'il est faux, un item rouge est déposé et reste en tête de docket (`GET docket/red`), sans
notification ni event `planning.docket.red_notified`. Pas de DDL : l'accusé de réception réutilise
`notifications.acked_at`.

Revision ID: 20261019_0098
Revises: 20261019_0097
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261019_0098"
down_revision: str | None = "20261019_0097"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CODE = "wr.red_notify_enabled"


def upgrade() -> None:
    op.get_bind().exec_driver_sql(
        """
        INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version)
        VALUES (gen_random_uuid(), %s, 'wr', 'false'::jsonb, 'bool',
                'Notification immédiate des items rouges du docket (spec WR §7, carte ACT-WR-07). Éteinte au seed.',
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
