"""pulse pain logs: link to the replan requested from a pain (PUL-09, doc 43 §3.1)

La replanification demandée depuis une douleur, après accord de l'utilisateur
(DECISION_demarrage_journee), garde son identifiant sur la douleur. Pas de clé étrangère
vers planning_replan_events : lien entre domaines, comme pour le Vault.

Revision ID: 20261018_0077
Revises: 20261018_0076
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261018_0077"
down_revision: str | None = "20261018_0076"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("pulse_pain_logs", sa.Column("replan_event_id", postgresql.UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    op.drop_column("pulse_pain_logs", "replan_event_id")
