"""wr digests: frozen snapshot assembled when the WR opens (spec WR §3.6, §9 P1, §13.2)

Un digest par session WR, figé à l'assemblage : top du docket par type (plafonds
`wr.digest_caps`), plafond dur `wr.digest_token_cap` (troncature par priorité).

Revision ID: 20261019_0084
Revises: 20261019_0083
Create Date: 2026-10-19
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261019_0084"
down_revision: str | None = "20261019_0083"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PARAMETERS = [
    ("wr.digest_token_cap", "wr", 40000, "tokens",
     "Plafond dur du digest WR en tokens estimés (spec WR §9 P1, §13.2)."),
    ("wr.digest_caps", "wr",
     {"chain_proposal": 12, "pattern_new": 10, "pattern_contradiction": 8, "anomaly": 10,
      "belief_review_due": 6, "plan_delta_proposal": 8},
     "items", "Plafond d'items du docket par type dans le digest (spec WR §13.2, défauts À VALIDER)."),
]


def upgrade() -> None:
    op.create_table(
        "wr_digests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("review_session_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("imperium_weekly_review_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("window_from", sa.Date(), nullable=False),
        sa.Column("window_to", sa.Date(), nullable=False),
        sa.Column("digest", postgresql.JSONB(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("review_session_id", name="wr_digests_review_session_unique"),
        sa.CheckConstraint("token_estimate >= 0", name="wr_digests_token_estimate_check"),
    )
    op.create_index("wr_digests_user_created_idx", "wr_digests", ["user_id", "created_at"])

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
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = ANY(%s)", (param_codes,))
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
    op.drop_index("wr_digests_user_created_idx", table_name="wr_digests")
    op.drop_table("wr_digests")
