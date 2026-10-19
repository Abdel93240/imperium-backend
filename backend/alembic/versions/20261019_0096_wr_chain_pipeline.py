"""wr chain pipeline: W2 causal discovery tables and notable-event criteria (spec WR §3.3, §5, §13.3)

DDL de la spec + user_id partout, `created_at`, `chain_assemblies.dry_run` et `.created_at`.
`chain_assemblies` est l'antichambre : rien n'entre dans le graphe causal réel (events, E2) avant
la Phase 5. Critères de sélection des events notables : paramètre éditable `wr.notable_criteria`
(jamais de code en dur, jamais un modèle qui choisit). Paramètres `wr.chain_window_days` 90,
`wr.chain_topn` 10, `wr.chain_min_confidence` 60 (seed spec §13.2, À VALIDER).

Revision ID: 20261019_0096
Revises: 20261019_0095
Create Date: 2026-10-19
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261019_0096"
down_revision: str | None = "20261019_0095"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)

NOTABLE_CRITERIA = {
    "event_types": ["planning.mission.aborted", "planning.replan.requested", "finance.pressure.corrected"],
    "red_flag_event_types": ["planning.docket.red_notified"],
    "user_question_event_types": [],
    "anomaly_min_band": "orange",
    "anomaly_domains": {"finance": ["finance."], "rides": ["rides."], "missions": ["planning.mission."]},
    "max_targets_per_run": 10,
}
PARAMETERS = [
    ("wr.chain_window_days", "wr", 90, "days", "Fenêtre d'antériorité des causes candidates (spec WR §5.2, §13.2, À VALIDER)."),
    ("wr.chain_topn", "wr", 10, "count", "Candidats retenus après rerank pour le verdict pairé (spec WR §5.2, À VALIDER)."),
    ("wr.chain_min_confidence", "wr", 60, "score",
     "Confiance minimale d'un verdict pour devenir un lien proposé (spec WR §5.4, À VALIDER)."),
    ("wr.notable_criteria", "wr", NOTABLE_CRITERIA, "json",
     "Critères déterministes des events notables de W2 : types notables, red flags, questions, anomalie W4 du "
     "même jour et domaine (spec WR §4, §13.3, À VALIDER)."),
]


def upgrade() -> None:
    op.create_table(
        "chain_probes",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_event_id", UUID, sa.ForeignKey("events.id"), nullable=False),
        sa.Column("probe_text", sa.Text(), nullable=False),
        sa.Column("probe_kind", sa.Text(), nullable=False),
        sa.Column("generated_by", sa.Text(), nullable=False),
        sa.Column("run_id", UUID, sa.ForeignKey("wr_worker_runs.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("probe_kind IN ('causal_hypothesis', 'entity_expansion')", name="chain_probes_kind_check"),
    )
    op.create_index("chain_probes_target_idx", "chain_probes", ["target_event_id"])
    op.create_table(
        "chain_candidates",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_event_id", UUID, sa.ForeignKey("events.id"), nullable=False),
        sa.Column("candidate_event_id", UUID, sa.ForeignKey("events.id"), nullable=False),
        sa.Column("channels", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("probe_id", UUID, sa.ForeignKey("chain_probes.id"), nullable=True),
        sa.Column("similarity", sa.Numeric(), nullable=True),
        sa.Column("passed_hard_filters", sa.Boolean(), nullable=False),
        sa.Column("rerank_score", sa.Numeric(), nullable=True),
        sa.Column("retained", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("target_event_id", "candidate_event_id", name="chain_candidates_pair_unique"),
        sa.CheckConstraint("channels <@ ARRAY['vector_classic', 'vector_probe', 'graph', 'metadata']::text[]",
                           name="chain_candidates_channels_check"),
    )
    op.create_table(
        "chain_pair_verdicts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("candidate_id", UUID, sa.ForeignKey("chain_candidates.id"), nullable=False),
        sa.Column("verdict", sa.Text(), nullable=False),
        sa.Column("mechanism_fr", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("model_used", sa.Text(), nullable=False),
        sa.Column("run_id", UUID, nullable=True),
        sa.Column("valid", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("verdict IN ('direct_cause', 'favoring_condition', 'correlation', 'no_link')",
                           name="chain_pair_verdicts_verdict_check"),
        sa.CheckConstraint("char_length(mechanism_fr) <= 200", name="chain_pair_verdicts_mechanism_check"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 100", name="chain_pair_verdicts_confidence_check"),
    )
    op.create_table(
        "chain_assemblies",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_event_id", UUID, sa.ForeignKey("events.id"), nullable=False),
        sa.Column("proposed_links", postgresql.JSONB(), nullable=False),
        sa.Column("conflicts", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("docket_item_id", UUID, sa.ForeignKey("wr_docket_items.id"), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('pending_validation', 'validated', 'refused')", name="chain_assemblies_status_check"),
        sa.CheckConstraint("jsonb_typeof(proposed_links) = 'array'", name="chain_assemblies_links_array"),
        sa.CheckConstraint("jsonb_typeof(conflicts) = 'array'", name="chain_assemblies_conflicts_array"),
    )
    op.create_index("chain_assemblies_docket_idx", "chain_assemblies", ["docket_item_id"])
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
    op.drop_table("chain_assemblies")
    op.drop_table("chain_pair_verdicts")
    op.drop_table("chain_candidates")
    op.drop_table("chain_probes")
