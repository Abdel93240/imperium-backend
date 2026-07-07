"""add events depth

Revision ID: 20260707_0036
Revises: 20260707_0035
Create Date: 2026-07-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260707_0036"
down_revision: str | None = "20260707_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("events", sa.Column("depth", sa.Integer(), nullable=True))
    op.create_check_constraint(
        op.f("ck_events_depth_positive_check"),
        "events",
        "depth IS NULL OR depth >= 1",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_events_depth_positive_check"), "events", type_="check")
    op.drop_column("events", "depth")
