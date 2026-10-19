"""wr auto-accept classes: user-activated classes, docket link, spot-check rate (spec WR §9 P4, §13.8)

Table née vide : seule l'utilisateur active une classe (item_type + domaine éventuel + slot IA dont
l'agreement doit tenir sa cible + confiance minimale). Un item qui la remplit à son dépôt est validé
d'office et `wr.spotcheck_pct` % d'entre eux sont re-présentés en `autoaccept_spotcheck`.

Revision ID: 20261019_0089
Revises: 20261019_0088
Create Date: 2026-10-19
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261019_0089"
down_revision: str | None = "20261019_0088"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Jamais auto-acceptables : le contrôle lui-même, un renvoi vers un rouge, une question posée à l'utilisateur.
ITEM_TYPES = (
    "chain_proposal", "pattern_new", "pattern_contradiction", "anomaly", "belief_review_due",
    "plan_delta_proposal", "investigation_result",
)
DOMAINS = ("pulse", "wr", "daily", "vector", "path", "vault", "imperium", "system")
PARAMETERS = [
    ("wr.spotcheck_pct", "wr", 10, "%",
     "Part des items auto-acceptés re-présentés en contrôle autoaccept_spotcheck (spec WR §9 P4, §13)."),
]


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def upgrade() -> None:
    op.create_table(
        "wr_autoaccept_classes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("item_type", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("slot_code", sa.Text(), sa.ForeignKey("ai_slot_transition.slot_code"), nullable=False),
        sa.Column("min_confidence", sa.Integer(), nullable=False),
        sa.Column("rationale_fr", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(_in("item_type", ITEM_TYPES), name="wr_autoaccept_classes_item_type_check"),
        sa.CheckConstraint(f"domain IS NULL OR {_in('domain', DOMAINS)}", name="wr_autoaccept_classes_domain_check"),
        sa.CheckConstraint("min_confidence BETWEEN 0 AND 100", name="wr_autoaccept_classes_confidence_check"),
        sa.CheckConstraint("enabled OR disabled_at IS NOT NULL", name="wr_autoaccept_classes_disabled_at_check"),
    )
    op.execute(
        "CREATE UNIQUE INDEX wr_autoaccept_classes_enabled_unique ON wr_autoaccept_classes "
        "(user_id, item_type, COALESCE(domain, '')) WHERE enabled"
    )
    op.add_column(
        "wr_docket_items",
        sa.Column("autoaccept_class_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("wr_autoaccept_classes.id"), nullable=True),
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
    op.drop_column("wr_docket_items", "autoaccept_class_id")
    op.drop_table("wr_autoaccept_classes")
