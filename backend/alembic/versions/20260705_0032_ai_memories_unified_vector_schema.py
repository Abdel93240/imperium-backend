"""recreate ai memories as unified vector memory

Revision ID: 20260705_0032
Revises: 20260526_0031
Create Date: 2026-07-05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import UserDefinedType

revision: str = "20260705_0032"
down_revision: str | None = "20260526_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


class Vector1024(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **_kw) -> str:
        return "vector(1024)"


def upgrade() -> None:
    op.drop_table("ai_memories")
    op.create_table(
        "ai_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector1024(), nullable=False),
        sa.Column("embedding_model", sa.Text(), nullable=False),
        sa.Column("memory_type", sa.Text(), nullable=False),
        sa.Column("learning_element_type", sa.Text(), nullable=True),
        sa.Column("source_domain", sa.Text(), nullable=False),
        sa.Column("source_table", sa.Text(), nullable=True),
        sa.Column("source_id", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("privacy_level", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("supersedes_memory_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correction_reason", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ai_memories_confidence_range"),
        sa.ForeignKeyConstraint(["supersedes_memory_id"], ["ai_memories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ai_memories_embedding_hnsw_idx",
        "ai_memories",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ai_memories_user_source_domain_type_active_idx",
        "ai_memories",
        ["user_id", "source_domain", "memory_type", "is_active"],
    )
    op.create_index("ai_memories_user_privacy_active_idx", "ai_memories", ["user_id", "privacy_level", "is_active"])
    op.create_index("ai_memories_source_table_id_idx", "ai_memories", ["source_table", "source_id"])
    op.create_index("ai_memories_expires_at_idx", "ai_memories", ["expires_at"])
    op.create_index("ai_memories_user_created_idx", "ai_memories", ["user_id", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_index("ai_memories_user_created_idx", table_name="ai_memories")
    op.drop_index("ai_memories_expires_at_idx", table_name="ai_memories")
    op.drop_index("ai_memories_source_table_id_idx", table_name="ai_memories")
    op.drop_index("ai_memories_user_privacy_active_idx", table_name="ai_memories")
    op.drop_index("ai_memories_user_source_domain_type_active_idx", table_name="ai_memories")
    op.drop_index("ai_memories_embedding_hnsw_idx", table_name="ai_memories")
    op.drop_table("ai_memories")

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
