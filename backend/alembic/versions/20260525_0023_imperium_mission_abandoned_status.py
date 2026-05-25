"""allow abandoned imperium mission status

Revision ID: 20260525_0023
Revises: 20260512_0022
Create Date: 2026-05-25
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260525_0023"
down_revision: str | None = "20260512_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MISSION_STATUS_CHECK = "status IN ('backlog', 'active', 'completed', 'failed', 'abandoned', 'cancelled')"
LEGACY_MISSION_STATUS_CHECK = "status IN ('backlog', 'active', 'completed', 'failed', 'cancelled')"


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_imperium_missions_imperium_missions_status_check"),
        "imperium_missions",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_imperium_missions_imperium_missions_status_check"),
        "imperium_missions",
        MISSION_STATUS_CHECK,
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_imperium_missions_imperium_missions_status_check"),
        "imperium_missions",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_imperium_missions_imperium_missions_status_check"),
        "imperium_missions",
        LEGACY_MISSION_STATUS_CHECK,
    )
