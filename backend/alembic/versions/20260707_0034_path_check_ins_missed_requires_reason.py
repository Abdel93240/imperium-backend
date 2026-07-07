"""require reason for missed path check-ins

Revision ID: 20260707_0034
Revises: 20260706_0033
Create Date: 2026-07-07
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260707_0034"
down_revision: str | None = "20260706_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "imperium_path_check_ins_missed_requires_reason",
        "imperium_path_check_ins",
        "status <> 'missed' OR (reason IS NOT NULL AND trim(reason) <> '')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "imperium_path_check_ins_missed_requires_reason",
        "imperium_path_check_ins",
        type_="check",
    )
