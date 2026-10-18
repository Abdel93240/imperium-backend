"""path adhkar routines/counters and quran progress/plans (doc 41 §11, §12)

Adhkar : routines activées par l'utilisateur (8 actives au plus, côté service), compteur par
période (jour, semaine ISO, prière du jour), appuis idempotents (clés distinctes = sommes).
Coran : point de reprise validé (page 1–604), objectif quotidien, khatm confirmé, plan de
lecture (un seul actif). Rien n'est jamais déduit du temps passé ou de l'écran.

Revision ID: 20261018_0067
Revises: 20261018_0066
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261018_0067"
down_revision: str | None = "20261018_0066"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TYPES = "'morning', 'evening', 'istighfar', 'salawat', 'tasbih', 'tahmid', 'takbir', 'personal'"


def _user():
    return sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


def _now(name: str):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    op.create_table(
        "path_adhkar_routines",
        sa.Column("id", UUID, primary_key=True),
        _user(),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("adhkar_type", sa.Text(), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("frequency", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        _now("created_at"),
        _now("updated_at"),
        sa.CheckConstraint("length(btrim(label)) BETWEEN 1 AND 64", name="label_length"),
        sa.CheckConstraint(f"adhkar_type IN ({TYPES})", name="adhkar_type_check"),
        sa.CheckConstraint("frequency IN ('daily', 'weekly', 'per_prayer')", name="frequency_check"),
        sa.CheckConstraint("target_count BETWEEN 1 AND 10000", name="target_range"),
        sa.CheckConstraint("version >= 1", name="version_positive"),
    )
    op.create_index("path_adhkar_routines_user_active_idx", "path_adhkar_routines", ["user_id", "active"])
    op.create_index(
        "path_adhkar_routines_user_idempotency_idx", "path_adhkar_routines", ["user_id", "idempotency_key"], unique=True
    )
    op.create_table(
        "path_adhkar_counts",
        sa.Column("id", UUID, primary_key=True),
        _user(),
        sa.Column("routine_id", UUID, sa.ForeignKey("path_adhkar_routines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_key", sa.Text(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_reached_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reset_at", sa.DateTime(timezone=True), nullable=True),
        _now("updated_at"),
        sa.UniqueConstraint("routine_id", "period_key", name="path_adhkar_counts_routine_period_unique"),
        sa.CheckConstraint("count >= 0", name="count_not_negative"),
    )
    op.create_index("path_adhkar_counts_user_period_idx", "path_adhkar_counts", ["user_id", "period_key"])
    op.create_table(
        "path_adhkar_increments",
        sa.Column("id", UUID, primary_key=True),
        _user(),
        sa.Column("routine_id", UUID, sa.ForeignKey("path_adhkar_routines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_key", sa.Text(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        _now("created_at"),
        sa.CheckConstraint("amount BETWEEN 1 AND 1000", name="amount_range"),
        sa.CheckConstraint("source IN ('tap', 'voice')", name="source_check"),
    )
    op.create_index(
        "path_adhkar_increments_user_idempotency_idx", "path_adhkar_increments", ["user_id", "idempotency_key"], unique=True
    )
    op.create_table(
        "path_quran_progress",
        sa.Column("id", UUID, primary_key=True),
        _user(),
        sa.Column("last_validated_page", sa.Integer(), nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("daily_objective_pages", sa.Integer(), nullable=True),
        sa.Column("khatm_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        _now("updated_at"),
        sa.UniqueConstraint("user_id", name="path_quran_progress_user_unique"),
        sa.CheckConstraint("last_validated_page BETWEEN 1 AND 604", name="page_range"),
        sa.CheckConstraint("daily_objective_pages IS NULL OR daily_objective_pages BETWEEN 1 AND 604", name="objective_range"),
        sa.CheckConstraint("khatm_count >= 0", name="khatm_not_negative"),
        sa.CheckConstraint("version >= 1", name="version_positive"),
    )
    op.create_table(
        "path_quran_plans",
        sa.Column("id", UUID, primary_key=True),
        _user(),
        sa.Column("plan_type", sa.Text(), nullable=False),
        sa.Column("pages_per_day", sa.Integer(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("start_page", sa.Integer(), nullable=False),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        _now("created_at"),
        sa.CheckConstraint("plan_type IN ('daily_pages', 'finish_in_days', 'juz_based')", name="plan_type_check"),
        sa.CheckConstraint("pages_per_day BETWEEN 1 AND 604", name="pages_per_day_range"),
        sa.CheckConstraint("start_page BETWEEN 1 AND 604", name="start_page_range"),
        sa.CheckConstraint("plan_type <> 'finish_in_days' OR end_date IS NOT NULL", name="finish_has_end_date"),
    )
    op.create_index(
        "path_quran_plans_one_active_idx", "path_quran_plans", ["user_id"], unique=True, postgresql_where=sa.text("active")
    )
    op.create_index("path_quran_plans_user_idempotency_idx", "path_quran_plans", ["user_id", "idempotency_key"], unique=True)


def downgrade() -> None:
    op.drop_index("path_quran_plans_user_idempotency_idx", table_name="path_quran_plans")
    op.drop_index("path_quran_plans_one_active_idx", table_name="path_quran_plans")
    op.drop_table("path_quran_plans")
    op.drop_table("path_quran_progress")
    op.drop_index("path_adhkar_increments_user_idempotency_idx", table_name="path_adhkar_increments")
    op.drop_table("path_adhkar_increments")
    op.drop_index("path_adhkar_counts_user_period_idx", table_name="path_adhkar_counts")
    op.drop_table("path_adhkar_counts")
    op.drop_index("path_adhkar_routines_user_idempotency_idx", table_name="path_adhkar_routines")
    op.drop_index("path_adhkar_routines_user_active_idx", table_name="path_adhkar_routines")
    op.drop_table("path_adhkar_routines")
