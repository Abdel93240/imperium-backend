"""add weekly review memory candidate decisions

Revision ID: 20260501_0015
Revises: 20260430_0014
Create Date: 2026-05-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260501_0015"
down_revision: str | None = "20260430_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "imperium_memory_candidate_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", sa.Text(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), server_default=sa.text("'weekly_review'"), nullable=False),
        sa.Column("original_candidate", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("edited_candidate", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "decision IN ('approved', 'rejected', 'edited')",
            name="imperium_memory_candidate_decisions_decision_check",
        ),
        sa.CheckConstraint(
            "source IN ('weekly_review')",
            name="imperium_memory_candidate_decisions_source_check",
        ),
        sa.ForeignKeyConstraint(["report_id"], ["imperium_weekly_review_final_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["imperium_weekly_review_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "report_id",
            "candidate_id",
            name="uq_mem_candidate_decision_user_report_candidate",
        ),
    )
    op.create_index(
        "imperium_memory_candidate_decisions_user_created_idx",
        "imperium_memory_candidate_decisions",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "imperium_memory_candidate_decisions_user_decision_idx",
        "imperium_memory_candidate_decisions",
        ["user_id", "decision"],
    )
    op.create_index(
        "imperium_memory_candidate_decisions_report_idx",
        "imperium_memory_candidate_decisions",
        ["report_id"],
    )
    op.create_index(
        "imperium_memory_candidate_decisions_session_idx",
        "imperium_memory_candidate_decisions",
        ["session_id"],
    )
    op.create_index(
        "imperium_memory_candidate_decisions_candidate_idx",
        "imperium_memory_candidate_decisions",
        ["candidate_id"],
    )


def downgrade() -> None:
    op.drop_index("imperium_memory_candidate_decisions_candidate_idx", table_name="imperium_memory_candidate_decisions")
    op.drop_index("imperium_memory_candidate_decisions_session_idx", table_name="imperium_memory_candidate_decisions")
    op.drop_index("imperium_memory_candidate_decisions_report_idx", table_name="imperium_memory_candidate_decisions")
    op.drop_index("imperium_memory_candidate_decisions_user_decision_idx", table_name="imperium_memory_candidate_decisions")
    op.drop_index("imperium_memory_candidate_decisions_user_created_idx", table_name="imperium_memory_candidate_decisions")
    op.drop_table("imperium_memory_candidate_decisions")
