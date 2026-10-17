"""mission dashboard fields: estimated_minutes, failure_reason_code, annex_of_mission_id

Décisions utilisateur 2026-10-16/17 :
- estimated_minutes : durée estimée, nullable, > 0 (doc 43 §5.2) ;
- failure_reason_code : no_time | too_tired | not_relevant | impediment (doc 52 §10) ;
- annex_of_mission_id : missions annexes V1 allégées (doc 53 §3.1).

Revision ID: 20261017_0043
Revises: 20260923_0042
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261017_0043"
down_revision: str | None = "20260923_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("imperium_missions", sa.Column("estimated_minutes", sa.Integer(), nullable=True))
    op.add_column("imperium_missions", sa.Column("failure_reason_code", sa.Text(), nullable=True))
    op.add_column(
        "imperium_missions",
        sa.Column(
            "annex_of_mission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("imperium_missions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "imperium_missions_estimated_minutes_positive",
        "imperium_missions",
        "estimated_minutes IS NULL OR estimated_minutes > 0",
    )
    op.create_check_constraint(
        "imperium_missions_failure_reason_code_check",
        "imperium_missions",
        "failure_reason_code IS NULL OR failure_reason_code IN ('no_time', 'too_tired', 'not_relevant', 'impediment')",
    )
    op.create_check_constraint(
        "imperium_missions_annex_not_self",
        "imperium_missions",
        "annex_of_mission_id IS NULL OR annex_of_mission_id <> id",
    )
    op.create_index(
        "imperium_missions_annex_of_idx",
        "imperium_missions",
        ["annex_of_mission_id"],
        postgresql_where=sa.text("annex_of_mission_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("imperium_missions_annex_of_idx", table_name="imperium_missions")
    op.drop_constraint("imperium_missions_annex_not_self", "imperium_missions", type_="check")
    op.drop_constraint("imperium_missions_failure_reason_code_check", "imperium_missions", type_="check")
    op.drop_constraint("imperium_missions_estimated_minutes_positive", "imperium_missions", type_="check")
    op.drop_column("imperium_missions", "annex_of_mission_id")
    op.drop_column("imperium_missions", "failure_reason_code")
    op.drop_column("imperium_missions", "estimated_minutes")
