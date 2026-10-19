"""wr pattern extractions and memory confrontations: W3 dry-run log (spec WR §3.4, §6.1-6.2, §13.4-13.5)

`wr_pattern_extractions` (ajout, pas de DDL dans la spec : la spec insère directement dans
ai_memories) : journal des patterns extraits à la clôture d'un épisode, avec les erreurs de
canonicité et le prédicat de contexte validé par le code (null si invalide). `memory_confrontations` :
DDL de la spec + user_id, extraction_id, dry_run ; `neighbor_memory_id` nullable (aucun voisin =
`unrelated`). AUCUNE écriture dans ai_memories ici : l'extension croyances attend l'arbitrage DV-1
et le commit mémoire la carte V25 (ACT-SYS-15). Paramètres `wr.episode_criteria` et
`wr.identity_topk` 5 (seed spec §13.2, À VALIDER).

Revision ID: 20261019_0097
Revises: 20261019_0096
Create Date: 2026-10-19
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261019_0097"
down_revision: str | None = "20261019_0096"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)

EPISODE_CRITERIA = {
    "event_types": ["planning.mission.completed", "planning.mission.aborted", "planning.wr_walk.closed"],
    "decided_with_note": True,
    "max_episodes_per_run": 20,
}
PARAMETERS = [
    ("wr.episode_criteria", "wr", EPISODE_CRITERIA, "json",
     "Clôtures d'épisode qui déclenchent W3 : types d'events, décision du docket expliquée (spec WR §4 W3, "
     "§6.1, À VALIDER)."),
    ("wr.identity_topk", "wr", 5, "count", "Voisins mémoire confrontés à un pattern extrait (spec WR §6.2, À VALIDER)."),
]


def upgrade() -> None:
    op.create_table(
        "wr_pattern_extractions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("episode_event_id", UUID, sa.ForeignKey("events.id"), nullable=False),
        sa.Column("statement_fr", sa.Text(), nullable=False),
        sa.Column("pattern_domain", sa.Text(), nullable=False),
        sa.Column("context_predicate", postgresql.JSONB(), nullable=True),
        sa.Column("predicate_rejected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("evidence_event_ids", postgresql.ARRAY(UUID), nullable=False),
        sa.Column("suggested_confidence", sa.Integer(), nullable=False),
        sa.Column("canonical_errors", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("model_used", sa.Text(), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("suggested_confidence BETWEEN 0 AND 100", name="wr_pattern_extractions_confidence_check"),
    )
    op.create_index("wr_pattern_extractions_episode_idx", "wr_pattern_extractions", ["episode_event_id"])
    op.create_table(
        "memory_confrontations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("extraction_id", UUID, sa.ForeignKey("wr_pattern_extractions.id"), nullable=False),
        sa.Column("new_statement", sa.Text(), nullable=False),
        sa.Column("neighbor_memory_id", UUID, sa.ForeignKey("ai_memories.id"), nullable=True),
        sa.Column("relation", sa.Text(), nullable=False),
        sa.Column("rationale_fr", sa.Text(), nullable=False),
        sa.Column("applied_effect", sa.Text(), nullable=False),
        sa.Column("model_used", sa.Text(), nullable=False),
        sa.Column("run_id", UUID, nullable=True),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("relation IN ('duplicate', 'reinforces', 'refines', 'contradicts', 'unrelated')",
                           name="memory_confrontations_relation_check"),
        sa.CheckConstraint(
            "applied_effect IN ('increment', 'new_pattern', 'refine_link', 'docket_contradiction', 'none')",
            name="memory_confrontations_effect_check"),
        sa.CheckConstraint("neighbor_memory_id IS NOT NULL OR relation = 'unrelated'",
                           name="memory_confrontations_neighbor_check"),
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
    op.drop_table("memory_confrontations")
    op.drop_table("wr_pattern_extractions")
