"""pulse pain logs (journal des douleurs PUL-09, doc 40 §16) sous consentement « pain »

Zone (liste fermée), côté, intensité 0..10, type, gêne, impact sur la séance, séance
liée facultative. Donnée d'entrée pour l'adaptation des séances, jamais un diagnostic.
Suppression réelle ; les événements ne portent que des identifiants (doc 08 PULSE-004).

Revision ID: 20261017_0062
Revises: 20261017_0061
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261017_0062"
down_revision: str | None = "20261017_0061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
ZONES = (
    "head", "neck", "shoulder", "upper_back", "lower_back", "chest", "abdomen", "arm", "elbow", "wrist", "hand", "hip",
    "thigh", "knee", "calf", "ankle", "foot", "other",
)


def upgrade() -> None:
    zones = ", ".join(f"'{zone}'" for zone in ZONES)
    op.create_table(
        "pulse_pain_logs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body_zone", sa.Text(), nullable=False),
        sa.Column("side", sa.Text(), nullable=True),
        sa.Column("severity", sa.SmallInteger(), nullable=False),
        sa.Column("pain_type", sa.Text(), nullable=True),
        sa.Column("limitation_notes", sa.Text(), nullable=True),
        sa.Column("workout_impact", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("workout_id", UUID, sa.ForeignKey("pulse_workouts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("noted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(f"body_zone IN ({zones})", name="body_zone_check"),
        sa.CheckConstraint("side IS NULL OR side IN ('left', 'right', 'both')", name="side_check"),
        sa.CheckConstraint("severity BETWEEN 0 AND 10", name="severity_range"),
    )
    op.create_index("pulse_pain_logs_user_noted_idx", "pulse_pain_logs", ["user_id", "noted_at"])
    op.create_index("pulse_pain_logs_user_idempotency_idx", "pulse_pain_logs", ["user_id", "idempotency_key"], unique=True)


def downgrade() -> None:
    op.drop_index("pulse_pain_logs_user_idempotency_idx", table_name="pulse_pain_logs")
    op.drop_index("pulse_pain_logs_user_noted_idx", table_name="pulse_pain_logs")
    op.drop_table("pulse_pain_logs")
