"""wr rollups: daily per-domain aggregates of worker W1, enabled-workers parameter (spec WR §4 W1)

`wr_rollups_daily` : une ligne par utilisateur, jour de Paris et domaine (finance, rides, missions),
métriques JSONB recalculées (upsert) à chaque passage de W1. Pas de DDL dans la spec : table née ici.
Pulse reste un stub neutre (aucune ligne). `wr.factory_workers_enabled` (vide) : un worker codé ne
tourne que s'il y est listé (carte V18 : `workers_enabled += w1`).

Revision ID: 20261019_0091
Revises: 20261019_0090
Create Date: 2026-10-19
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261019_0091"
down_revision: str | None = "20261019_0090"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PARAMETERS = [
    ("wr.factory_workers_enabled", "wr", [], "list",
     "Workers de l'usine WR autorisés à tourner (w1_rollups, w4_anomalies, w2_causal, w3_learning, w5_docket) ; "
     "vide = aucun (bascule par worker, carte V18)."),
]


def upgrade() -> None:
    op.create_table(
        "wr_rollups_daily",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "local_date", "domain", name="wr_rollups_daily_user_date_domain_unique"),
        sa.CheckConstraint("domain IN ('finance', 'rides', 'missions')", name="wr_rollups_daily_domain_check"),
    )
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


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = ANY(%s)", ([p[0] for p in PARAMETERS],))
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
    op.drop_table("wr_rollups_daily")
