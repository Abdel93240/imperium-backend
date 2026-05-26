"""add allowed source_module constraint for imperium events

Revision ID: 20260526_0030
Revises: 20260526_0029
Create Date: 2026-05-26
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260526_0030"
down_revision: str | None = "20260526_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "imperium_events_source_module_allowed_check",
        "imperium_events",
        "source_module IN ('mission', 'vault', 'path', 'pulse', 'vector', "
        "'dashboard', 'daily_plan', 'system', 'manual')",
    )


def downgrade() -> None:
    op.drop_constraint("imperium_events_source_module_allowed_check", "imperium_events", type_="check")
