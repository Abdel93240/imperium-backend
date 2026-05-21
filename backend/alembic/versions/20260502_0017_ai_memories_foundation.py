"""add ai memories foundation

Revision ID: 20260502_0017
Revises: 20260501_0016
Create Date: 2026-05-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260502_0017"
down_revision: str | None = "20260501_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_module", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("source_report_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_candidate_id", sa.Text(), nullable=True),
        sa.Column("source_decision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("visibility", sa.Text(), server_default=sa.text("'private'"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.CheckConstraint("source_module IN ('weekly_review')", name="ai_memories_source_module_check"),
        sa.CheckConstraint(
            "kind IN ("
            "'behavior_pattern', 'blocker', 'weekly_commitment', 'preference', "
            "'operational_signal', 'risk', 'achievement', 'constraint', 'strategy_note'"
            ")",
            name="ai_memories_kind_check",
        ),
        sa.CheckConstraint(
            "scope IN ("
            "'user_profile', 'operating_pattern', 'weekly_review', 'module_signal', "
            "'user_preference', 'strategy', 'health', 'finance', 'vtc'"
            ")",
            name="ai_memories_scope_check",
        ),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ai_memories_confidence_range"),
        sa.CheckConstraint("status IN ('active', 'archived', 'superseded', 'deleted')", name="ai_memories_status_check"),
        sa.CheckConstraint("visibility IN ('private')", name="ai_memories_visibility_check"),
        sa.ForeignKeyConstraint(["source_decision_id"], ["imperium_memory_candidate_decisions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_report_id"], ["imperium_weekly_review_final_reports.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_session_id"], ["imperium_weekly_review_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["superseded_by_id"], ["ai_memories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ai_memories_user_created_idx", "ai_memories", ["user_id", sa.text("created_at DESC")])
    op.create_index(
        "ai_memories_user_status_created_idx",
        "ai_memories",
        ["user_id", "status", sa.text("created_at DESC")],
    )
    op.create_index("ai_memories_user_kind_idx", "ai_memories", ["user_id", "kind"])
    op.create_index("ai_memories_user_scope_idx", "ai_memories", ["user_id", "scope"])
    op.create_index("ai_memories_source_module_type_idx", "ai_memories", ["source_module", "source_type"])
    op.create_index("ai_memories_source_report_idx", "ai_memories", ["source_report_id"])
    op.create_index("ai_memories_source_session_idx", "ai_memories", ["source_session_id"])
    op.create_index("ai_memories_source_candidate_idx", "ai_memories", ["source_candidate_id"])
    op.create_index("ai_memories_source_decision_idx", "ai_memories", ["source_decision_id"])
    op.create_index(
        "uq_ai_memories_source_decision",
        "ai_memories",
        ["user_id", "source_module", "source_type", "source_decision_id"],
        unique=True,
        postgresql_where=sa.text("source_decision_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_ai_memories_source_decision", table_name="ai_memories")
    op.drop_index("ai_memories_source_decision_idx", table_name="ai_memories")
    op.drop_index("ai_memories_source_candidate_idx", table_name="ai_memories")
    op.drop_index("ai_memories_source_session_idx", table_name="ai_memories")
    op.drop_index("ai_memories_source_report_idx", table_name="ai_memories")
    op.drop_index("ai_memories_source_module_type_idx", table_name="ai_memories")
    op.drop_index("ai_memories_user_scope_idx", table_name="ai_memories")
    op.drop_index("ai_memories_user_kind_idx", table_name="ai_memories")
    op.drop_index("ai_memories_user_status_created_idx", table_name="ai_memories")
    op.drop_index("ai_memories_user_created_idx", table_name="ai_memories")
    op.drop_table("ai_memories")
