"""rides sessions: link to the replan requested after a VTC session (VEC-11, doc 43 §3.1)

La replanification demandée par l'utilisateur après la clôture d'une session VTC garde son
identifiant sur la session. Pas de clé étrangère vers planning_replan_events : lien entre
domaines, comme pour la douleur (0077).

Revision ID: 20261018_0081
Revises: 20261018_0080
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261018_0081"
down_revision: str | None = "20261018_0080"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("rides_sessions", sa.Column("replan_event_id", postgresql.UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    op.drop_column("rides_sessions", "replan_event_id")
