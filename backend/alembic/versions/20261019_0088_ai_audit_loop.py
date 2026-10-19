"""ai audit loop: seeded slots, sample idempotency, weekly agreement view, decay parameters (doc 78 F1-13)

Spec WR §3.7, §10, §13.1 ; spec Daily §8.2-8.3 ; spec Pulse §13. Les 10 slots WR et les 2 slots
Daily sont semés avec audit 100 % et cible 92 %. La contre-lecture elle-même (appel cloud) n'est PAS
codée ici : ce lot enregistre ses résultats, mesure l'agreement par slot et par semaine, et propose
une décroissance que seul l'utilisateur applique (`POST /api/wr/admin/transition`). Job
`wr.audit_weekly` semé désactivé.

Revision ID: 20261019_0088
Revises: 20261019_0087
Create Date: 2026-10-19
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261019_0088"
down_revision: str | None = "20261019_0087"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (slot_code, domain, tier initial, rôle) — spec WR §10 et spec Daily §13.
SLOTS = [
    ("wr.probe_gen", "wr", "local_default", "Sondes divergentes quotidiennes."),
    ("wr.pair_verdict", "wr", "local_default", "Verdicts pairés quotidiens."),
    ("wr.pattern_extract", "wr", "local_default", "Extraction d'apprentissages."),
    ("wr.identity", "wr", "local_default", "Confrontation d'identité."),
    ("wr.hypothesis_pass", "wr", "cloud_forced", "Hypothèses cross-domaines et agenda."),
    ("wr.investigation", "wr", "cloud_forced", "Enquêtes dirigées multi-sauts."),
    ("wr.conjunctive", "wr", "cloud_forced", "Synthèse conjonctive hebdomadaire."),
    ("wr.plan_delta", "wr", "cloud_forced", "Deltas de plan hebdomadaires."),
    ("wr.plan_regen", "wr", "cloud_forced", "Régénérations de plan (choc, mensuel)."),
    ("wr.exit_audit", "wr", "cloud_forced", "Consolidation de la vérité validée."),
    ("daily.disruption_classify", "daily", "local_default", "Classement d'une perturbation du jour."),
    ("daily.conflict_arbitrate", "daily", "local_default", "Arbitrage d'un conflit d'obligatoires."),
]

PARAMETERS = [
    ("ai.audit_decay_weeks", "ai", 3, "weeks",
     "Semaines closes consécutives à agreement >= cible avant de proposer une décroissance (spec WR §3.7)."),
    ("ai.audit_min_samples_week", "ai", 5, "count",
     "Contre-lectures minimum dans une semaine pour qu'elle compte (ajout, À VALIDER)."),
    ("ai.audit_decay_factor", "ai", 0.5, "ratio",
     "Facteur appliqué au taux d'audit proposé (ajout, À VALIDER : la spec ne fixe pas le pas)."),
    ("ai.audit_floor_pct", "ai", 5, "%",
     "Taux d'audit plancher sous lequel aucune décroissance n'est proposée (ajout, À VALIDER)."),
]


def upgrade() -> None:
    op.add_column("ai_audit_samples", sa.Column("cloud_model", sa.Text(), nullable=True))
    op.add_column("ai_audit_samples", sa.Column("disagreement_class", sa.Text(), nullable=True))
    op.create_index(
        "ai_audit_samples_slot_run_unique", "ai_audit_samples", ["slot_code", "run_ref"], unique=True,
        postgresql_where=sa.text("run_ref IS NOT NULL"),
    )
    op.execute(
        """
        CREATE VIEW v_ai_slot_agreement_weekly AS
        SELECT slot_code,
               DATE_TRUNC('week', created_at AT TIME ZONE 'Europe/Paris')::DATE AS week_start,
               COUNT(*) AS samples,
               COUNT(*) FILTER (WHERE agreement) AS agreed,
               ROUND(100.0 * COUNT(*) FILTER (WHERE agreement) / COUNT(*), 1) AS agreement_pct
        FROM ai_audit_samples
        WHERE agreement IS NOT NULL
        GROUP BY 1, 2
        """
    )
    conn = op.get_bind()
    for slot_code, domain, tier, role in SLOTS:
        conn.exec_driver_sql(
            """
            INSERT INTO ai_slot_transition
              (id, slot_code, domain, tier, audit_sample_pct, agreement_target_pct, notes_fr)
            VALUES (gen_random_uuid(), %s, %s, %s, 100, 92, %s)
            ON CONFLICT ON CONSTRAINT ai_slot_transition_slot_code_unique DO NOTHING
            """,
            (slot_code, domain, tier, role),
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
    op.execute(
        """
        INSERT INTO job_definitions
          (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s)
        VALUES (gen_random_uuid(), 'wr.audit_weekly', 'cron', '15 5 * * 1', NULL,
                'app.services.ai.audit_loop:audit_weekly_job', false, true, 120)
        ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM job_definitions WHERE code = 'wr.audit_weekly'")
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = ANY(%s)", ([p[0] for p in PARAMETERS],))
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
    # Un slot déjà contre-lu garde sa ligne : ses échantillons y sont rattachés.
    conn.exec_driver_sql(
        "DELETE FROM ai_slot_transition t WHERE t.slot_code = ANY(%s) "
        "AND NOT EXISTS (SELECT 1 FROM ai_audit_samples s WHERE s.slot_code = t.slot_code)",
        ([s[0] for s in SLOTS],),
    )
    op.execute("DROP VIEW v_ai_slot_agreement_weekly")
    op.drop_index("ai_audit_samples_slot_run_unique", table_name="ai_audit_samples")
    op.drop_column("ai_audit_samples", "disagreement_class")
    op.drop_column("ai_audit_samples", "cloud_model")
