"""rides sessions and drop zones (Vector VEC-02/03/10/11, doc 59 §14)

Session VTC : une seule active, CA cible facultatif, direction stratégique, mission liée.
Revenus et dépenses = transactions Vault (source vector_manual, external_ref
`rides:{session}:…`) ; la clôture fige le CA et les dépenses de la session. Déposes
confirmées par l'utilisateur pour l'apprentissage des zones. Domaine `rides` (doc 77).

Revision ID: 20261018_0069
Revises: 20261018_0068
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261018_0069"
down_revision: str | None = "20261018_0068"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "rides_sessions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("target_ca_cents", sa.Integer(), nullable=True),
        sa.Column("strategic_direction", sa.Text(), nullable=True),
        sa.Column("mission_id", UUID, sa.ForeignKey("imperium_missions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("final_revenue_cents", sa.Integer(), nullable=True),
        sa.Column("final_expense_cents", sa.Integer(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active', 'completed')", name="status_check"),
        sa.CheckConstraint("target_ca_cents IS NULL OR target_ca_cents BETWEEN 1 AND 10000000", name="target_range"),
        sa.CheckConstraint("status <> 'completed' OR ended_at IS NOT NULL", name="completed_has_end"),
        sa.CheckConstraint("version >= 1", name="version_positive"),
    )
    op.create_index("rides_sessions_one_active_idx", "rides_sessions", ["user_id"], unique=True,
                    postgresql_where=sa.text("status = 'active'"))
    op.create_index("rides_sessions_user_started_idx", "rides_sessions", ["user_id", "started_at"])
    op.create_index("rides_sessions_user_idempotency_idx", "rides_sessions", ["user_id", "idempotency_key"], unique=True)
    op.create_table(
        "rides_drop_zones",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", UUID, sa.ForeignKey("rides_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("zone", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("gps_confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("real_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.CheckConstraint("length(btrim(zone)) BETWEEN 1 AND 120", name="zone_length"),
        sa.CheckConstraint("(latitude IS NULL) = (longitude IS NULL)", name="coordinates_pair"),
        sa.CheckConstraint("gps_confidence IS NULL OR gps_confidence BETWEEN 0 AND 1", name="confidence_range"),
        sa.CheckConstraint("real_duration_minutes IS NULL OR real_duration_minutes BETWEEN 1 AND 600", name="duration_range"),
    )
    op.create_index("rides_drop_zones_session_idx", "rides_drop_zones", ["session_id", "recorded_at"])
    op.create_index("rides_drop_zones_user_idempotency_idx", "rides_drop_zones", ["user_id", "idempotency_key"], unique=True)


def downgrade() -> None:
    op.drop_index("rides_drop_zones_user_idempotency_idx", table_name="rides_drop_zones")
    op.drop_index("rides_drop_zones_session_idx", table_name="rides_drop_zones")
    op.drop_table("rides_drop_zones")
    op.drop_index("rides_sessions_user_idempotency_idx", table_name="rides_sessions")
    op.drop_index("rides_sessions_user_started_idx", table_name="rides_sessions")
    op.drop_index("rides_sessions_one_active_idx", table_name="rides_sessions")
    op.drop_table("rides_sessions")
