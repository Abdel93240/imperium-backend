"""rides revenue entries and zone recommendations (Vector VEC-07/08/09, doc 33 §5)

Revenus saisis en session avec leur zone (la transaction reste au Vault, lien sans FK).
Recommandations « Où aller ? » déterministes sur l'historique du même créneau ; sans assez
de données, abstention (doc 33 §4.1). Retour de l'utilisateur sur chaque recommandation.

Revision ID: 20261018_0070
Revises: 20261018_0069
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261018_0070"
down_revision: str | None = "20261018_0069"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "rides_revenue_entries",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", UUID, sa.ForeignKey("rides_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transaction_id", UUID, nullable=False),
        sa.Column("zone", sa.Text(), nullable=True),
        sa.Column("zone_key", sa.Text(), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount_cents > 0", name="amount_positive"),
    )
    op.create_index("rides_revenue_entries_user_occurred_idx", "rides_revenue_entries", ["user_id", "occurred_at"])
    op.create_index("rides_revenue_entries_transaction_idx", "rides_revenue_entries", ["transaction_id"], unique=True)
    op.create_table(
        "rides_recommendations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", UUID, sa.ForeignKey("rides_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_zone", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("zone", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=False),
        sa.Column("inputs", postgresql.JSONB(), nullable=False),
        sa.Column("feedback_useful", sa.Boolean(), nullable=True),
        sa.Column("ride_user_action", sa.Text(), nullable=True),
        sa.Column("feedback_reason", sa.Text(), nullable=True),
        sa.Column("feedback_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.CheckConstraint("recommendation IN ('stay_here', 'move_to_zone', 'abstain')", name="recommendation_check"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_range"),
        sa.CheckConstraint(
            "ride_user_action IS NULL OR ride_user_action IN ('accepted', 'refused', 'missed', 'ignored')",
            name="ride_user_action_check",
        ),
        sa.CheckConstraint("(feedback_at IS NULL) = (feedback_useful IS NULL)", name="feedback_complete"),
    )
    op.create_index("rides_recommendations_user_requested_idx", "rides_recommendations", ["user_id", "requested_at"])
    op.create_index(
        "rides_recommendations_user_idempotency_idx", "rides_recommendations", ["user_id", "idempotency_key"], unique=True
    )


def downgrade() -> None:
    op.drop_index("rides_recommendations_user_idempotency_idx", table_name="rides_recommendations")
    op.drop_index("rides_recommendations_user_requested_idx", table_name="rides_recommendations")
    op.drop_table("rides_recommendations")
    op.drop_index("rides_revenue_entries_transaction_idx", table_name="rides_revenue_entries")
    op.drop_index("rides_revenue_entries_user_occurred_idx", table_name="rides_revenue_entries")
    op.drop_table("rides_revenue_entries")
