"""wr digest on open: rollups and W4 anomalies in the digest, launch-triggered job (spec WR §9 P1, §12)

`wr.digest_anomaly_signals_cap` : nombre maximal d'anomalies W4 (signal × jour hors green) dans le
digest, les plus fortes d'abord. Job `wr.digest_on_open` (abonné à
`planning.weekly_review.launched`, semé désactivé) : assemble le digest au lancement du WR.

Revision ID: 20261019_0094
Revises: 20261019_0093
Create Date: 2026-10-19
"""

import json
from collections.abc import Sequence

from alembic import op

revision: str = "20261019_0094"
down_revision: str | None = "20261019_0093"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PARAMETERS = [
    ("wr.digest_anomaly_signals_cap", "wr", 20, "count",
     "Anomalies W4 (signal × jour hors green) au plus dans le digest, |z| décroissant (ajout, À VALIDER)."),
]


def upgrade() -> None:
    conn = op.get_bind()
    for code, domain, value, unit, rationale in PARAMETERS:
        conn.exec_driver_sql(
            """
            INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version)
            VALUES (gen_random_uuid(), %s, %s, %s::jsonb, %s, %s, 'seed', 1)
            ON CONFLICT ON CONSTRAINT parameters_code_version_unique DO NOTHING
            """,
            (code, domain, json.dumps(value), unit, rationale),
        )
    op.execute(
        """
        INSERT INTO job_definitions
          (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s)
        VALUES (gen_random_uuid(), 'wr.digest_on_open', 'event_subscription', NULL,
                ARRAY['planning.weekly_review.launched'], 'app.services.wr.digest:digest_on_open_job', false, true, 300)
        ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM job_definitions WHERE code = 'wr.digest_on_open'")
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = ANY(%s)", ([p[0] for p in PARAMETERS],))
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
