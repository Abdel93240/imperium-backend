"""vector: adresses complètes des offres (2026-10-23)

`rides_offers.pickup_address` et `destination_address` : l'adresse lue sur l'offre Bolt (rue comprise), gardée sur le
serveur de l'utilisateur ; décision utilisateur 2026-10-23 (la position GPS de prise en charge et de dépose la donnait
déjà). Le prénom et la note du client ne sont jamais lus.

Revision ID: 20261023_0141
Revises: 20261023_0140
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261023_0141"
down_revision: str | None = "20261023_0140"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("rides_offers", sa.Column("pickup_address", sa.Text(), nullable=True))
    op.add_column("rides_offers", sa.Column("destination_address", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("rides_offers", "destination_address")
    op.drop_column("rides_offers", "pickup_address")
