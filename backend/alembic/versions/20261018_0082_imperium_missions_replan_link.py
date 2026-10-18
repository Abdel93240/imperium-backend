"""imperium missions: link to the replan requested after a failed or cancelled mission (doc 43 §3.1)

Le replan demandé depuis une mission ratée (automatique selon les réglages, ou accepté par
l'utilisateur) ou annulée (toujours à la demande) garde son identifiant sur la mission.

Revision ID: 20261018_0082
Revises: 20261018_0081
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261018_0082"
down_revision: str | None = "20261018_0081"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "imperium_missions",
        sa.Column("replan_event_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("planning_replan_events.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("imperium_missions", "replan_event_id")
