"""vector: impact des fermetures routières selon le trafic de la route (2026-10-23)

TomTom ne note pas la gravité d'une fermeture. Pour chaque fermeture d'axe numéroté (20 au plus par relevé), le flux
de circulation TomTom au milieu du tronçon donne la classe de la route (FRC0 autoroute … FRC6 rue de quartier) et la
vitesse actuelle face à la vitesse normale. Note d'impact sur 100 = importance de la route × ralentissement mesuré
(décision utilisateur : comparer l'affluence des routes fermées).

Revision ID: 20261023_0145
Revises: 20261023_0144
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261023_0145"
down_revision: str | None = "20261023_0144"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = (("frc", sa.Text()), ("current_speed", sa.Integer()), ("free_flow_speed", sa.Integer()), ("impact", sa.Integer()))


def upgrade() -> None:
    for name, kind in COLUMNS:
        op.add_column("rides_traffic_incidents", sa.Column(name, kind, nullable=True))


def downgrade() -> None:
    for name, _ in reversed(COLUMNS):
        op.drop_column("rides_traffic_incidents", name)
