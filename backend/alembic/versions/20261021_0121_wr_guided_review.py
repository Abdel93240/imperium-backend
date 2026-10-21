"""wr guided review: question relevance, follow-up cap, single report rewrite, CLI cost (spec WR §9 P2-P5)

- `wr.question_relevance_min` = 40 : une question de l'agenda (ou une relance) n'est posée que si sa
  pertinence (0-100) atteint ce seuil ;
- `wr.questions_max` = 30 : plafond de sécurité des questions retenues ;
- `wr.followups_max` = 6 : relances au plus sur un même sujet ;
- `wr.report_revisions_max` = 1 : réécritures du rapport après corrections ;
- `ai.usd_eur_rate` = 0.86 : conversion du coût estimé par la CLI d'abonnement (USD) en euros ;
- slot `wr.report_revision` (cloud_forced, domaine wr) : réécriture du rapport, servi seulement si
  `ai.cloud_slot_modes` le met en live (sinon le slot de l'audit de sortie la fait).

Revision ID: 20261021_0121
Revises: 20261021_0120
Create Date: 2026-10-21
"""

import json
from collections.abc import Sequence

from alembic import op

revision: str = "20261021_0121"
down_revision: str | None = "20261021_0120"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PARAMETERS = [
    ("wr.question_relevance_min", "wr", 40, "%",
     "Pertinence minimale (0-100) d'une question ou d'une relance pour être posée pendant le WR."),
    ("wr.questions_max", "wr", 30, "count", "Questions au plus retenues pour un WR (plafond de sécurité)."),
    ("wr.followups_max", "wr", 6, "count", "Relances au plus sur un même sujet pendant le WR."),
    ("wr.report_revisions_max", "wr", 1, "count", "Réécritures du rapport du WR après corrections."),
    ("ai.usd_eur_rate", "ai", 0.86, "ratio",
     "Conversion USD → EUR du coût estimé par la CLI d'abonnement, pour le journal des appels."),
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
        INSERT INTO ai_slot_transition
          (id, slot_code, domain, tier, audit_sample_pct, agreement_target_pct, notes_fr)
        VALUES (gen_random_uuid(), 'wr.report_revision', 'wr', 'cloud_forced', 100, 92,
                'Réécriture du rapport du WR avec les corrections de l''utilisateur.')
        ON CONFLICT ON CONSTRAINT ai_slot_transition_slot_code_unique DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM ai_slot_transition WHERE slot_code = 'wr.report_revision'")
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = ANY(%s)", ([p[0] for p in PARAMETERS],))
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
