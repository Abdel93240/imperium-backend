"""wr docket: shared docket items + priority parameters (spec WR §3.1, §7, §13 ; doc 78 F2-11)

Le docket est la file des points à trancher par l'utilisateur. Table partagée d'emblée (R3) :
WR, Daily, Vector et Pulse y déposent. Priorité, portage et décision forcée sont paramétrés
(`wr.docket_halflife_days`, `wr.docket_max_defers`), jamais en dur.

Revision ID: 20261019_0083
Revises: 20261018_0082
Create Date: 2026-10-19
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261019_0083"
down_revision: str | None = "20261018_0082"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PARAMETERS = [
    ("wr.docket_halflife_days", "wr", 14, "days",
     "Demi-vie de la fraîcheur d'un item du docket (spec WR §7, défaut À VALIDER)."),
    ("wr.docket_max_defers", "wr", 3, "count",
     "Reports consécutifs avant décision forcée (spec WR §7, défaut À VALIDER)."),
]

ITEM_TYPES = (
    "chain_proposal", "pattern_new", "pattern_contradiction", "anomaly", "belief_review_due",
    "user_question", "plan_delta_proposal", "autoaccept_spotcheck", "investigation_result", "red_flag_ref",
)


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def upgrade() -> None:
    op.create_table(
        "wr_docket_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("item_type", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("title_fr", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column("impact_estimate", sa.Integer(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False, server_default="normal"),
        sa.Column("priority", sa.Numeric(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("consecutive_defers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("force_decision", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("source_worker", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.CheckConstraint(_in("item_type", ITEM_TYPES), name="wr_docket_items_item_type_check"),
        sa.CheckConstraint(
            _in("domain", ("pulse", "wr", "daily", "vector", "path", "vault", "imperium", "system")),
            name="wr_docket_items_domain_check",
        ),
        sa.CheckConstraint("confidence IS NULL OR confidence BETWEEN 0 AND 100", name="wr_docket_items_confidence_check"),
        sa.CheckConstraint("impact_estimate BETWEEN 1 AND 5", name="wr_docket_items_impact_check"),
        sa.CheckConstraint(_in("severity", ("normal", "elevated", "red")), name="wr_docket_items_severity_check"),
        sa.CheckConstraint(
            _in("status", ("pending", "presented", "validated", "refused", "deferred", "archived")),
            name="wr_docket_items_status_check",
        ),
        sa.CheckConstraint("consecutive_defers >= 0", name="wr_docket_items_defers_check"),
        sa.CheckConstraint(
            _in("source_worker", ("w1", "w2", "w3", "w4", "phase1", "phase3", "manual")),
            name="wr_docket_items_source_worker_check",
        ),
    )
    op.create_index("wr_docket_items_user_status_idx", "wr_docket_items", ["user_id", "status"])
    op.create_index("wr_docket_items_user_severity_idx", "wr_docket_items", ["user_id", "severity"])

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
    param_codes = [parameter[0] for parameter in PARAMETERS]
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql(
            "DELETE FROM parameters WHERE code = ANY(%s) AND version = 1 AND origin = 'seed'",
            (param_codes,),
        )
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
    op.drop_index("wr_docket_items_user_severity_idx", table_name="wr_docket_items")
    op.drop_index("wr_docket_items_user_status_idx", table_name="wr_docket_items")
    op.drop_table("wr_docket_items")
