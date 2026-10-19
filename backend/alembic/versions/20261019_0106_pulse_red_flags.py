"""pulse red flags RF1-RF5 + contractual view v_pulse_active_blocks + Daily G5 wiring (spec Pulse §3.5, §11 ; V9 ACT-PLS-09, V29 ACT-DLY-05)

1. `pulse_red_flag_rules` (global, §3.5) : les 5 règles du §11 semées INACTIVES (`active=false`) ; la
   bascule ACT-PLS-09 les active EN BLOC par SQL. Aucune route ne les modifie (non désactivables par
   une sortie de modèle).
2. `pulse_red_flag_events` (+ user_id) : levée avec preuve (identifiants et valeurs, jamais le texte
   libre), acquittement, résolution utilisateur (`dismissed_with_reason` exige une raison). Un seul
   événement ouvert par (règle, sujet).
3. Vue `v_pulse_active_blocks` {user_id, block_kind, min_physical_load, since, source_ref} : seule
   lecture permise à Daily G5 (FINDINGS C-4, PATCH_DAILY D-7) ; un red flag `advise_doctor_and_pause_training`
   non résolu bloque l'entraînement.
4. Paramètres : `daily.g5_enabled` false (ACT-DLY-05), `daily.pulse_block_load` 4 (carte V29).

Revision ID: 20261019_0106
Revises: 20261019_0105
Create Date: 2026-10-19
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261019_0106"
down_revision: str | None = "20261019_0105"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)

# Mots-clés graves (§11, À VALIDER) : comparés sans accents ni casse.
SYMPTOM_KEYWORDS = [
    "douleur thoracique", "douleur poitrine", "douleur a la poitrine", "oppression thoracique", "malaise",
    "essoufflement anormal", "perte de connaissance", "evanouissement", "syncope", "palpitations",
]

RULES = [
    ("RF_lab_out_of_range", "Valeur de bilan hors plage non résolue.",
     {"source": "lab", "field": "out_of_range", "op": "is_true", "strong_if_pct_outside": 20},
     "advise", "advise_doctor",
     "Valeur hors plage sur ton bilan : à montrer à un médecin. Je n'ajuste rien sur cette base."),
    ("RF_rhr_sustained", "FC de repos élevée plusieurs jours de suite.",
     {"source": "signal", "signal": "resting_hr_delta", "op": ">=", "value": 8, "consecutive_days": 3},
     "advise_strong", "advise_doctor", "FC repos anormalement élevée depuis 3 jours : consulte."),
    ("RF_severe_pain", "Douleur sévère en cours.",
     {"source": "pain", "field": "severity", "op": ">=", "value": 8, "open_only": True},
     "urgent", "advise_doctor_and_pause_training",
     "Douleur sévère : consulte un médecin avant de reprendre l'entraînement. Les séances sont en pause."),
    ("RF_weight_drop", "Perte de poids rapide non planifiée.",
     {"source": "body", "field": "weight_kg", "op": "trend_pct_per_month_lt", "value": -1.5, "window_days": 28,
      "min_span_days": 14},
     "advise", "advise_doctor", "Perte de poids rapide non planifiée : parles-en à un médecin."),
    ("RF_symptom_keywords", "Mots-clés graves dans une douleur en cours.",
     {"source": "pain", "field": "text", "op": "contains_any", "keywords": SYMPTOM_KEYWORDS, "open_only": True},
     "urgent", "advise_doctor_and_pause_training",
     "Symptôme à prendre au sérieux : consultation immédiate recommandée. Les séances sont en pause."),
]

PARAMETERS = [
    ("daily.g5_enabled", "daily", False, "bool",
     "Porte G5 : lit v_pulse_active_blocks au lieu du stub passant ; carte ACT-DLY-05."),
    ("daily.pulse_block_load", "daily", 4, "level",
     "Charge physique à partir de laquelle un blocage Pulse rejette une mission (carte V29, À VALIDER)."),
]


def upgrade() -> None:
    op.create_table(
        "pulse_red_flag_rules",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("description_fr", sa.Text(), nullable=False),
        sa.Column("condition", postgresql.JSONB(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("message_fr", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("code", name="pulse_red_flag_rules_code_unique"),
        sa.CheckConstraint("severity IN ('advise', 'advise_strong', 'urgent')", name="pulse_red_flag_rules_severity_check"),
        sa.CheckConstraint("action IN ('advise_doctor', 'advise_doctor_and_pause_training', 'urgent_message')",
                           name="pulse_red_flag_rules_action_check"),
        sa.CheckConstraint("jsonb_typeof(condition) = 'object'", name="pulse_red_flag_rules_condition_object"),
    )
    op.create_table(
        "pulse_red_flag_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_id", UUID, sa.ForeignKey("pulse_red_flag_rules.id"), nullable=False),
        sa.Column("subject_ref", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("raised_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("acknowledged_by_user_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("resolution_reason", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("severity IN ('advise', 'advise_strong', 'urgent')", name="pulse_red_flag_events_severity_check"),
        sa.CheckConstraint("resolution IS NULL OR resolution IN ('doctor_consulted', 'resolved', 'dismissed_with_reason')",
                           name="pulse_red_flag_events_resolution_check"),
        sa.CheckConstraint("(resolution IS NULL) = (resolved_at IS NULL)", name="pulse_red_flag_events_resolved_pair"),
        sa.CheckConstraint("resolution IS DISTINCT FROM 'dismissed_with_reason' "
                           "OR char_length(btrim(coalesce(resolution_reason, ''))) > 0",
                           name="pulse_red_flag_events_dismiss_reason"),
        sa.CheckConstraint("jsonb_typeof(evidence) = 'object'", name="pulse_red_flag_events_evidence_object"),
    )
    op.create_index("pulse_red_flag_events_open_unique", "pulse_red_flag_events", ["user_id", "rule_id", "subject_ref"],
                    unique=True, postgresql_where=sa.text("resolved_at IS NULL"))
    op.create_index("pulse_red_flag_events_user_raised_idx", "pulse_red_flag_events", ["user_id", "raised_at"])
    conn = op.get_bind()
    for code, description, condition, severity, action, message in RULES:
        conn.exec_driver_sql(
            """
            INSERT INTO pulse_red_flag_rules (id, code, description_fr, condition, severity, action, message_fr, active)
            VALUES (gen_random_uuid(), %s, %s, %s::jsonb, %s, %s, %s, false)
            ON CONFLICT ON CONSTRAINT pulse_red_flag_rules_code_unique DO NOTHING
            """,
            (code, description, json.dumps(condition, ensure_ascii=False), severity, action, message),
        )
    op.execute(
        """
        CREATE VIEW v_pulse_active_blocks AS
        SELECT e.user_id,
               'pause_training'::text AS block_kind,
               COALESCE((SELECT (p.value #>> '{}')::int FROM v_parameters_current p
                         WHERE p.code = 'daily.pulse_block_load'), 4) AS min_physical_load,
               e.raised_at AS since,
               e.id AS source_ref
        FROM pulse_red_flag_events e
        JOIN pulse_red_flag_rules r ON r.id = e.rule_id
        WHERE e.resolved_at IS NULL AND r.action = 'advise_doctor_and_pause_training'
        """
    )
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
    op.execute("DROP VIEW IF EXISTS v_pulse_active_blocks")
    op.drop_table("pulse_red_flag_events")
    op.drop_table("pulse_red_flag_rules")
