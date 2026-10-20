"""pulse procedures P1-P10, procedure runs, proposals, procedure AI slots (spec Pulse §3.3, §7, §8, §13 ;
V10 ACT-PLS-15 suite)

1. `pulse_procedures` : les 10 cartes du §7 semées INACTIVES (étapes et slots sérialisés). Un seul
   mécanisme (runner backend) ; seule P1 a ses étapes code écrites, les autres s'arrêtent en `aborted`.
2. `pulse_procedure_runs` : une exécution par procédure nommée (file `queued` → runner), journal des étapes.
3. `pulse_proposals` : sortie refusable (no-override). En essai à blanc, la proposition est écrite
   `dry_run` et JAMAIS présentée ; seule une décision explicite de l'utilisateur applique un effet.
4. Slots IA des procédures semés dans `ai_slot_transition` avec leurs tiers initiaux du §7.
5. Job `pulse.procedure_runner` (cron */5, désactivé) ; paramètre `pulse.proposals_enabled` false.

Revision ID: 20261020_0111
Revises: 20261020_0110
Create Date: 2026-10-20
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261020_0111"
down_revision: str | None = "20261020_0110"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def _step(order: int, kind: str, ref: str, on_fail: str = "abort") -> dict:
    return {"order": order, "type": kind, "ref": ref, "on_fail": on_fail}


def _slot(tier: str, schema: str, max_tokens: int = 3000) -> dict:
    return {"tier": tier, "output_schema_ref": schema, "max_input_tokens": max_tokens}


# (code, nom, but, déclencheurs, étapes, slots) — spec Pulse §7.
PROCEDURES = [
    ("adapt_training_session", "Adapter la séance", "Adapter une séance prévue à l'état du jour (coups légaux).",
     ["dispatch", "pre_session", "signal"],
     [_step(1, "code", "p1.load"), _step(2, "code", "p1.legal_menu"), _step(3, "llm_slot", "pulse.p1.choose_move", "fallback"),
      _step(4, "code", "p1.validate"), _step(5, "user_gate", "p1.proposal"), _step(6, "code", "p1.apply")],
     {"pulse.p1.choose_move": _slot("local_default", "move_choice")}),
    ("diet_change_assessment", "Évaluer un changement de régime", "Juger un régime contre le dossier santé, paire par paire.",
     ["conversational"],
     [_step(1, "code", "p2.resolve"), _step(2, "code", "p2.load"), _step(3, "code", "p2.pairs"),
      _step(4, "llm_slot", "pulse.p2.pair_verdict"), _step(5, "code", "p2.aggregate"),
      _step(6, "llm_slot", "pulse.p2.synthesis"), _step(7, "user_gate", "p2.proposal"), _step(8, "code", "p2.apply")],
     {"pulse.p2.pair_verdict": _slot("local_default", "pair_verdict"),
      "pulse.p2.synthesis": _slot("routed", "diet_synthesis")}),
    ("new_training_program", "Nouveau programme", "Concevoir un programme depuis des objectifs pondérés.",
     ["conversational"],
     [_step(1, "code", "p3.objectives"), _step(2, "code", "p3.catalogue"), _step(3, "llm_slot", "pulse.p3.design"),
      _step(4, "code", "p3.validate"), _step(5, "user_gate", "p3.proposal")],
     {"pulse.p3.design": _slot("cloud_forced", "program_design")}),
    ("injury_or_pain", "Douleur ou blessure", "Traduire une douleur en restrictions et adapter les séances à venir.",
     ["signal", "conversational"],
     [_step(1, "code", "p4.severity_gate"), _step(2, "llm_slot", "pulse.p4.interpret"), _step(3, "code", "p4.injury"),
      _step(4, "subprocedure", "adapt_training_session"), _step(5, "user_gate", "p4.proposal")],
     {"pulse.p4.interpret": _slot("local_default", "pain_interpretation")}),
    ("medical_document_ingest", "Lire un document médical", "Extraire un bilan avec contre-lecture sur le critique.",
     ["signal"],
     [_step(1, "code", "p5.text"), _step(2, "llm_slot", "pulse.p5.extract"), _step(3, "code", "p5.normalize"),
      _step(4, "llm_slot", "pulse.p5.second_read"), _step(5, "user_gate", "p5.validation")],
     {"pulse.p5.extract": _slot("local_default", "lab_extraction"),
      "pulse.p5.second_read": _slot("cloud_forced", "lab_extraction")}),
    ("weekly_reconciliation", "Bilan de semaine", "Bilan adhérence et dette, cibles et plan repas de la semaine.",
     ["scheduled"],
     [_step(1, "code", "p6.review"), _step(2, "code", "p6.targets"), _step(3, "llm_slot", "pulse.p6.review"),
      _step(4, "code", "p6.solver"), _step(5, "user_gate", "p6.batch")],
     {"pulse.p6.review": _slot("local_default", "weekly_review_notes")}),
    ("monthly_revision", "Révision mensuelle", "Transitions de phase et ajustements du mésocycle.",
     ["scheduled"],
     [_step(1, "code", "p7.features"), _step(2, "llm_slot", "pulse.p7.revise"), _step(3, "code", "p7.validate"),
      _step(4, "user_gate", "p7.proposal")],
     {"pulse.p7.revise": _slot("cloud_forced", "program_design")}),
    ("scientific_review", "Revue scientifique", "Confronter paramètres et fiches validées au consensus courant.",
     ["scheduled"],
     [_step(1, "code", "p8.export"), _step(2, "llm_slot", "pulse.p8.review"), _step(3, "user_gate", "p8.diffs"),
      _step(4, "code", "p8.apply")],
     {"pulse.p8.review": _slot("cloud_forced", "parameter_diffs")}),
    ("exploration_pass", "Passe d'exploration", "Proposer de nouveaux signaux depuis des agrégats.",
     ["scheduled"],
     [_step(1, "code", "p9.export"), _step(2, "llm_slot", "pulse.p9.explore"), _step(3, "user_gate", "p9.signals")],
     {"pulse.p9.explore": _slot("cloud_forced", "signal_proposals")}),
    ("missing_sheet", "Fiche manquante", "Rédiger une fiche du corpus en brouillon, à valider.",
     ["subprocedure", "conversational"],
     [_step(1, "llm_slot", "pulse.p10.draft"), _step(2, "code", "p10.insert_draft"), _step(3, "user_gate", "p10.validation")],
     {"pulse.p10.draft": _slot("routed", "corpus_sheet")}),
]

PARAMETERS = [
    ("pulse.proposals_enabled", "pulse", False, "bool",
     "Routes des propositions Pulse servies (liste et décision) ; aucune n'est présentée en essai à blanc."),
]


def upgrade() -> None:
    op.create_table(
        "pulse_procedures",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("name_fr", sa.Text(), nullable=False),
        sa.Column("purpose_fr", sa.Text(), nullable=False),
        sa.Column("trigger_types", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("steps", postgresql.JSONB(), nullable=False),
        sa.Column("llm_slots", postgresql.JSONB(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "pulse_procedure_runs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("procedure_id", UUID, sa.ForeignKey("pulse_procedures.id"), nullable=False),
        sa.Column("procedure_version", sa.Integer(), nullable=False),
        sa.Column("dispatch_id", UUID, sa.ForeignKey("pulse_dispatch_log.id", ondelete="SET NULL"), nullable=True),
        sa.Column("trigger_event_id", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.Text(), nullable=True),
        sa.Column("inputs", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("steps_log", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('queued', 'running', 'waiting_user', 'completed', 'aborted', 'failed')",
                           name="pulse_procedure_runs_status_check"),
    )
    op.create_index("pulse_procedure_runs_user_created_idx", "pulse_procedure_runs", ["user_id", "created_at"])
    op.create_index("pulse_procedure_runs_queued_idx", "pulse_procedure_runs", ["created_at"],
                    postgresql_where=sa.text("status = 'queued'"))
    op.create_table(
        "pulse_proposals",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("procedure_run_id", UUID, sa.ForeignKey("pulse_procedure_runs.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("summary_fr", sa.Text(), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("presented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_explanation", sa.Text(), nullable=True),
        sa.Column("modified_payload", postgresql.JSONB(), nullable=True),
        sa.Column("applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('session_adaptation', 'diet_change', 'program', 'meal_plan', 'monitoring', 'corpus_sheet', "
            "'parameter_update', 'signal_definition', 'doctor_advice')", name="pulse_proposals_kind_check"),
        sa.CheckConstraint("decision IS NULL OR decision IN ('accepted', 'refused', 'modified', 'expired')",
                           name="pulse_proposals_decision_check"),
        sa.CheckConstraint("(decision IS NULL) = (decided_at IS NULL)", name="pulse_proposals_decided_check"),
        sa.CheckConstraint("decision IS DISTINCT FROM 'refused' OR user_explanation IS NOT NULL",
                           name="pulse_proposals_refusal_explained"),
        sa.CheckConstraint("decision IS DISTINCT FROM 'modified' OR modified_payload IS NOT NULL",
                           name="pulse_proposals_modified_payload"),
        sa.CheckConstraint("NOT (dry_run AND presented_at IS NOT NULL)", name="pulse_proposals_dry_run_hidden"),
        sa.CheckConstraint("applied = (applied_at IS NOT NULL)", name="pulse_proposals_applied_check"),
        sa.CheckConstraint("NOT applied OR decision IN ('accepted', 'modified')", name="pulse_proposals_applied_decided"),
    )
    op.create_index("pulse_proposals_user_pending_idx", "pulse_proposals", ["user_id", "presented_at"],
                    postgresql_where=sa.text("decision IS NULL"))
    conn = op.get_bind()
    for code, name, purpose, triggers, steps, slots in PROCEDURES:
        conn.exec_driver_sql(
            """
            INSERT INTO pulse_procedures (id, code, name_fr, purpose_fr, trigger_types, steps, llm_slots, version, active)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s::jsonb, %s::jsonb, 1, false)
            ON CONFLICT (code) DO NOTHING
            """,
            (code, name, purpose, triggers, json.dumps(steps), json.dumps(slots)),
        )
        for slot_code, slot in slots.items():
            conn.exec_driver_sql(
                """
                INSERT INTO ai_slot_transition
                  (id, slot_code, domain, tier, audit_sample_pct, agreement_target_pct, output_schema_ref, notes_fr)
                VALUES (gen_random_uuid(), %s, 'pulse', %s, 100, 92, %s, %s)
                ON CONFLICT ON CONSTRAINT ai_slot_transition_slot_code_unique DO NOTHING
                """,
                (slot_code, slot["tier"], slot["output_schema_ref"], f"Procédure {code} (spec Pulse §7)."),
            )
    conn.exec_driver_sql(
        """
        INSERT INTO job_definitions
          (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s)
        VALUES (gen_random_uuid(), 'pulse.procedure_runner', 'cron', '*/5 * * * *', NULL,
                'app.services.pulse.procedures:runner_job', false, true, 120)
        ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING
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
    op.execute("DELETE FROM job_definitions WHERE code = 'pulse.procedure_runner'")
    slots = [slot for *_, slot_map in PROCEDURES for slot in slot_map]
    conn.exec_driver_sql("DELETE FROM ai_audit_samples WHERE slot_code = ANY(%s)", (slots,))
    conn.exec_driver_sql("DELETE FROM ai_slot_transition WHERE slot_code = ANY(%s)", (slots,))
    op.drop_table("pulse_proposals")
    op.drop_table("pulse_procedure_runs")
    op.drop_table("pulse_procedures")
