"""scope event_id uniqueness per user

Revision ID: 20260430_0011
Revises: 20260427_0010
Create Date: 2026-04-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260430_0011"
down_revision: str | None = "20260427_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("events_event_id_unique", "events", type_="unique")
    op.create_unique_constraint("events_user_event_id_unique", "events", ["user_id", "event_id"])


def downgrade() -> None:
    op.drop_constraint("events_user_event_id_unique", "events", type_="unique")
    op.create_unique_constraint("events_event_id_unique", "events", ["event_id"])
