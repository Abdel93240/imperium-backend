"""pulse workouts (séances de sport PUL-05/PUL-06, doc 40 §13.1–§13.2)

Séance planifiée à la main (titre, heure, durée, intensité, exercices, matériel,
mission liée facultative), démarrée, terminée (séries, intensité ressentie,
exercices sautés avec raison) ou sautée avec raison. Modification sous version.

Revision ID: 20261017_0059
Revises: 20261017_0058
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261017_0059"
down_revision: str | None = "20261017_0058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "pulse_workouts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("planned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("intensity", sa.Text(), nullable=True),
        sa.Column("exercises", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("equipment", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source_mission_id", UUID, sa.ForeignKey("imperium_missions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("intensity_score", sa.SmallInteger(), nullable=True),
        sa.Column("body_state_at_start", sa.Text(), nullable=True),
        sa.Column("notes_post_workout", sa.Text(), nullable=True),
        sa.Column("skip_reason", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("closing_idempotency_key", sa.Text(), nullable=True),
        sa.Column("closing_request_hash", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('planned', 'in_progress', 'completed', 'skipped')", name="status_check"),
        sa.CheckConstraint("intensity IS NULL OR intensity IN ('low', 'medium', 'high')", name="intensity_check"),
        sa.CheckConstraint("length(btrim(title)) > 0", name="title_not_blank"),
        sa.CheckConstraint("duration_minutes IS NULL OR duration_minutes BETWEEN 1 AND 600", name="duration_range"),
        sa.CheckConstraint(
            "actual_duration_minutes IS NULL OR actual_duration_minutes BETWEEN 1 AND 600", name="actual_duration_range"
        ),
        sa.CheckConstraint("intensity_score IS NULL OR intensity_score BETWEEN 1 AND 10", name="intensity_score_range"),
        sa.CheckConstraint("version >= 1", name="version_positive"),
    )
    op.create_index("pulse_workouts_user_planned_idx", "pulse_workouts", ["user_id", "planned_at"])
    op.create_index("pulse_workouts_user_idempotency_idx", "pulse_workouts", ["user_id", "idempotency_key"], unique=True)


def downgrade() -> None:
    op.drop_index("pulse_workouts_user_idempotency_idx", table_name="pulse_workouts")
    op.drop_index("pulse_workouts_user_planned_idx", table_name="pulse_workouts")
    op.drop_table("pulse_workouts")
