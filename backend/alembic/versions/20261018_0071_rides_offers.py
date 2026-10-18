"""rides offers: proposed rides, user decision and real outcome (doc 57 §5, §6, §11 ; doc 33 §8)

Une ligne par course proposée pendant une session : variables saisies (prix, distances,
durées, zones, majoration…) et calculées (€/h affiché, €/km, créneau, contexte de session),
décision de l'utilisateur (donnée de comportement, jamais cible d'apprentissage), résultat
réel des courses acceptées (gain ÷ temps mobilisé à la minute = cible). Aucun verdict tant
que le modèle n'est pas entraîné.

Revision ID: 20261018_0071
Revises: 20261018_0070
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261018_0071"
down_revision: str | None = "20261018_0070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "rides_offers",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", UUID, sa.ForeignKey("rides_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("offered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("distance_km", sa.Numeric(7, 2), nullable=True),
        sa.Column("estimated_duration_min", sa.Integer(), nullable=True),
        sa.Column("approach_distance_km", sa.Numeric(7, 2), nullable=True),
        sa.Column("approach_duration_min", sa.Integer(), nullable=True),
        sa.Column("surge_multiplier", sa.Numeric(4, 2), nullable=True),
        sa.Column("pickup_zone", sa.Text(), nullable=True),
        sa.Column("destination_zone", sa.Text(), nullable=True),
        sa.Column("payment_type", sa.Text(), nullable=True),
        sa.Column("ride_type", sa.Text(), nullable=False),
        sa.Column("features", postgresql.JSONB(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("actual_earning_cents", sa.Integer(), nullable=True),
        sa.Column("mobilized_minutes", sa.Integer(), nullable=True),
        sa.Column("actual_hourly_rate_cents", sa.Integer(), nullable=True),
        sa.Column("outcome", postgresql.JSONB(), nullable=True),
        sa.Column("revenue_transaction_id", UUID, nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.CheckConstraint("price_cents BETWEEN 1 AND 1000000", name="price_range"),
        sa.CheckConstraint("platform IN ('bolt', 'uber', 'heetch', 'other')", name="platform_check"),
        sa.CheckConstraint("ride_type IN ('immediate', 'scheduled')", name="ride_type_check"),
        sa.CheckConstraint("source IN ('manual', 'ocr')", name="source_check"),
        sa.CheckConstraint("decision IS NULL OR decision IN ('accepted', 'refused', 'missed')", name="decision_check"),
        sa.CheckConstraint("(decision IS NULL) = (decided_at IS NULL)", name="decision_has_time"),
        sa.CheckConstraint("actual_hourly_rate_cents IS NULL OR decision = 'accepted'", name="outcome_only_accepted"),
        sa.CheckConstraint("mobilized_minutes IS NULL OR mobilized_minutes > 0", name="mobilized_positive"),
        sa.CheckConstraint("version >= 1", name="version_positive"),
    )
    op.create_index("rides_offers_session_idx", "rides_offers", ["session_id", "offered_at"])
    op.create_index("rides_offers_user_offered_idx", "rides_offers", ["user_id", "offered_at"])
    op.create_index("rides_offers_user_idempotency_idx", "rides_offers", ["user_id", "idempotency_key"], unique=True)


def downgrade() -> None:
    op.drop_index("rides_offers_user_idempotency_idx", table_name="rides_offers")
    op.drop_index("rides_offers_user_offered_idx", table_name="rides_offers")
    op.drop_index("rides_offers_session_idx", table_name="rides_offers")
    op.drop_table("rides_offers")
