"""cloud roles through subscription CLIs, WR P1 hypothesis pass (spec WR §3.6, §9 P1 ; doc 30 §3)

1. Paramètres semés ÉTEINTS : `ai.cloud_transport` = "off" (off|subscription|api ; subscription = CLI
   du fournisseur connectée à l'abonnement de l'utilisateur, pour les tests réels avant une clé API) et
   `ai.cloud_slot_modes` = {} ({slot_code: off|live}) ; `ai.cloud_subscription_models` = {} (modèle du
   rôle → modèle accepté par l'abonnement, le catalogue d'un abonnement différant de celui de l'API).
2. `wr.drill_max` (6) : forages au plus par passe d'hypothèses.
3. Table `wr_hypotheses` (une par digest) : sortie du contrat hypothesis_pass, journal de forage,
   modèle, jetons.
4. Job `wr.hypothesis_on_digest` (abonné à `planning.wr_digest.assembled`, semé désactivé).

Revision ID: 20261021_0119
Revises: 20261020_0118
Create Date: 2026-10-21
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261021_0119"
down_revision: str | None = "20261020_0118"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PARAMETERS = [
    ("ai.cloud_transport", "ai", "off", "json",
     "Transport des rôles cloud : off | subscription (CLI de l'abonnement, tests avant clé API) | api. Éteint."),
    ("ai.cloud_slot_modes", "ai", {}, "json",
     "Slots servis par un rôle cloud : {slot_code: off|live}. Vide = aucun."),
    ("ai.cloud_subscription_models", "ai", {}, "json",
     "Modèle du rôle → modèle accepté par l'abonnement (transport subscription seulement). Vide = identique."),
    ("wr.drill_max", "wr", 6, "count",
     "Forages au plus demandés par la passe d'hypothèses du WR (spec WR §9 P1)."),
]


def upgrade() -> None:
    op.create_table(
        "wr_hypotheses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("digest_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wr_digests.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("output", postgresql.JSONB(), nullable=False),
        sa.Column("drill_log", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("model_used", sa.Text(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("digest_id", name="wr_hypotheses_digest_unique"),
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
    op.execute(
        """
        INSERT INTO job_definitions
          (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s)
        VALUES (gen_random_uuid(), 'wr.hypothesis_on_digest', 'event_subscription', NULL,
                ARRAY['planning.wr_digest.assembled'], 'app.services.wr.hypotheses:hypothesis_on_digest_job',
                false, true, 900)
        ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM job_definitions WHERE code = 'wr.hypothesis_on_digest'")
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = ANY(%s)", ([p[0] for p in PARAMETERS],))
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
    op.drop_table("wr_hypotheses")
