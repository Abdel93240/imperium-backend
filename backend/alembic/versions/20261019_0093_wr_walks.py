"""wr walks: docket walker sessions with mode and attention budget (spec WR §9 P4, §13.2)

Une marche par session WR (unique) : mode full|light choisi par l'utilisateur, budget en minutes
figé au départ depuis `wr.budget_min` ({full: 45, light: 15}, seed spec §13.2), début, clôture.
Le mode de la marche alimente `wr_metrics_weekly.wr_mode`.

Revision ID: 20261019_0093
Revises: 20261019_0092
Create Date: 2026-10-19
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261019_0093"
down_revision: str | None = "20261019_0092"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PARAMETERS = [
    ("wr.budget_min", "wr", {"full": 45, "light": 15}, "min",
     "Budget d'attention du walker par mode (spec WR §9 P4, §13.2, défaut À VALIDER)."),
]


def upgrade() -> None:
    op.create_table(
        "wr_walks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("review_session_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("imperium_weekly_review_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("budget_min", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("review_session_id", name="wr_walks_review_session_unique"),
        sa.CheckConstraint("mode IN ('full', 'light')", name="wr_walks_mode_check"),
        sa.CheckConstraint("budget_min > 0", name="wr_walks_budget_check"),
        sa.CheckConstraint("closed_at IS NULL OR closed_at >= started_at", name="wr_walks_closed_check"),
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
    op.drop_table("wr_walks")
