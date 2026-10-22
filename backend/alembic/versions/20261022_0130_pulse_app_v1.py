"""pulse: app V1 kit (2026-10-22) — free-text pain location, other drinks

Le kit Pulse demande « Où ressens-tu la gêne ? » en texte libre (la zone reste facultative, « other » par défaut)
et « J'ai bu » avec Eau ou Autre en texte libre (une autre boisson ne décompte jamais l'eau du stock).

Revision ID: 20261022_0130
Revises: 20261022_0129
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0130"
down_revision: str | None = "20261022_0129"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("pulse_pain_logs", sa.Column("location", sa.Text(), nullable=True))
    op.add_column("pulse_hydration_logs", sa.Column("drink", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("pulse_hydration_logs", "drink")
    op.drop_column("pulse_pain_logs", "location")
