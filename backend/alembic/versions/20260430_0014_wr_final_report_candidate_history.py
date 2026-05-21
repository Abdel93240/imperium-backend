"""allow historical weekly review final report candidates

Revision ID: 20260430_0014
Revises: 20260430_0013
Create Date: 2026-04-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260430_0014"
down_revision: str | None = "20260430_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ACTIVE_STATUS_SQL = "status IN ('draft', 'approved', 'stored')"


def upgrade() -> None:
    op.drop_constraint(
        "imperium_weekly_review_final_reports_session_unique",
        "imperium_weekly_review_final_reports",
        type_="unique",
    )
    op.drop_constraint(
        "imperium_weekly_review_final_reports_user_week_unique",
        "imperium_weekly_review_final_reports",
        type_="unique",
    )
    op.create_index(
        "uq_wr_final_reports_active_session",
        "imperium_weekly_review_final_reports",
        ["session_id"],
        unique=True,
        postgresql_where=sa.text(ACTIVE_STATUS_SQL),
    )
    op.create_index(
        "uq_wr_final_reports_active_user_week",
        "imperium_weekly_review_final_reports",
        ["user_id", "week_start"],
        unique=True,
        postgresql_where=sa.text(ACTIVE_STATUS_SQL),
    )


def downgrade() -> None:
    # Downgrade can fail if multiple historical superseded candidates exist
    # for the same session/week after this migration has been used.
    op.drop_index("uq_wr_final_reports_active_user_week", table_name="imperium_weekly_review_final_reports")
    op.drop_index("uq_wr_final_reports_active_session", table_name="imperium_weekly_review_final_reports")
    op.create_unique_constraint(
        "imperium_weekly_review_final_reports_user_week_unique",
        "imperium_weekly_review_final_reports",
        ["user_id", "week_start"],
    )
    op.create_unique_constraint(
        "imperium_weekly_review_final_reports_session_unique",
        "imperium_weekly_review_final_reports",
        ["session_id"],
    )
