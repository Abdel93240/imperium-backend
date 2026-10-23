"""vector: mesure après chaque dépose, en zone fine et créneau de 10 minutes (2026-10-23)

`rides_drop_observations` : une ligne par course terminée — où et quand la dépose a eu lieu (zone 1 / 3 / 10 km²,
créneau de 10 min, type de jour), puis ce qui a suivi : attente jusqu'à la première offre, nombre d'offres vues,
attente jusqu'à la course suivante acceptée, gain et temps de cette course, €/h du cycle suivant. C'est la valeur
mesurée qui note une zone à un créneau (décision utilisateur 2026-10-23) et la cible du futur modèle. Une pause ou la
fin de session avant la course suivante interrompt la mesure (le temps n'était plus du travail).

Revision ID: 20261023_0143
Revises: 20261023_0142
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261023_0143"
down_revision: str | None = "20261023_0142"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rides_drop_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rides_sessions.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("offer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rides_offers.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("dropped_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("drop_lat", sa.Numeric(9, 6), nullable=True),
        sa.Column("drop_lng", sa.Numeric(9, 6), nullable=True),
        sa.Column("zone_code", sa.Text(), nullable=True),
        sa.Column("zone_source", sa.Text(), nullable=True),  # gps | commune
        sa.Column("slot", sa.SmallInteger(), nullable=False),
        sa.Column("day_type", sa.Text(), nullable=False),
        sa.Column("school_holiday", sa.Boolean(), nullable=True),
        sa.Column("next_offer_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("wait_first_offer_min", sa.Numeric(6, 1), nullable=True),
        sa.Column("offers_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_offer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("next_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("wait_to_accept_min", sa.Numeric(6, 1), nullable=True),
        sa.Column("next_earning_cents", sa.Integer(), nullable=True),
        sa.Column("next_mobilized_min", sa.Integer(), nullable=True),
        sa.Column("cycle_hourly_cents", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("closed_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('open', 'closed', 'interrupted')", name="status_check"),
        sa.CheckConstraint("slot BETWEEN 0 AND 143", name="slot_range"),
        sa.UniqueConstraint("offer_id", name="offer_unique"),
    )
    op.create_index("rides_drop_observations_open_idx", "rides_drop_observations", ["session_id"],
                    postgresql_where=sa.text("status = 'open'"))
    op.create_index("rides_drop_observations_zone_idx", "rides_drop_observations", ["zone_code", "day_type", "slot"])


def downgrade() -> None:
    op.drop_index("rides_drop_observations_zone_idx", table_name="rides_drop_observations")
    op.drop_index("rides_drop_observations_open_idx", table_name="rides_drop_observations")
    op.drop_table("rides_drop_observations")
