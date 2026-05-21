"""add weekly review conversation layer

Revision ID: 20260430_0013
Revises: 20260430_0012
Create Date: 2026-04-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260430_0013"
down_revision: str | None = "20260430_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "imperium_weekly_review_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'ready'")),
        sa.Column("launched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("current_ai_task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("initial_ai_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("final_ai_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ("
            "'ready', 'launched', 'preparing_initial_summary', 'initial_summary_ready', "
            "'waiting_for_user_answer', 'integrating_answers', 'draft_ready', "
            "'revision_requested', 'final_ready', 'approved', 'stored', 'cancelled', 'failed'"
            ")",
            name="imperium_weekly_review_sessions_status_check",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="imperium_weekly_review_sessions_user_id_fkey"),
        sa.ForeignKeyConstraint(
            ["current_ai_task_id"],
            ["ai_tasks.id"],
            name="imperium_weekly_review_sessions_current_ai_task_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["initial_ai_result_id"],
            ["ai_results.id"],
            name="imperium_weekly_review_sessions_initial_ai_result_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["final_ai_result_id"],
            ["ai_results.id"],
            name="imperium_weekly_review_sessions_final_ai_result_id_fkey",
        ),
        sa.UniqueConstraint("user_id", "week_start", name="imperium_weekly_review_sessions_user_week_unique"),
    )
    op.create_index("imperium_weekly_review_sessions_user_status_idx", "imperium_weekly_review_sessions", ["user_id", "status"])
    op.create_index("imperium_weekly_review_sessions_user_week_start_idx", "imperium_weekly_review_sessions", ["user_id", "week_start"])

    op.create_table(
        "imperium_weekly_review_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("message_type", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("ai_task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ai_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "role IN ('user', 'qwen', 'system', 'opus', 'backend')",
            name="imperium_weekly_review_messages_role_check",
        ),
        sa.CheckConstraint(
            "message_type IN ("
            "'user_answer', 'clarification_question', 'initial_summary', 'draft', "
            "'revision_request', 'final_report', 'system_note'"
            ")",
            name="imperium_weekly_review_messages_type_check",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["imperium_weekly_review_sessions.id"],
            name="imperium_weekly_review_messages_session_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="imperium_weekly_review_messages_user_id_fkey"),
        sa.ForeignKeyConstraint(["ai_task_id"], ["ai_tasks.id"], name="imperium_weekly_review_messages_ai_task_id_fkey"),
        sa.ForeignKeyConstraint(["ai_result_id"], ["ai_results.id"], name="imperium_weekly_review_messages_ai_result_id_fkey"),
    )
    op.create_index("imperium_weekly_review_messages_session_created_idx", "imperium_weekly_review_messages", ["session_id", "created_at"])
    op.create_index("imperium_weekly_review_messages_user_created_idx", "imperium_weekly_review_messages", ["user_id", "created_at"])

    op.create_table(
        "imperium_weekly_review_final_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("report_payload", postgresql.JSONB(), nullable=False),
        sa.Column("report_markdown", sa.Text(), nullable=False),
        sa.Column("memory_candidates", postgresql.JSONB(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_ai_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'stored', 'superseded')",
            name="imperium_weekly_review_final_reports_status_check",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["imperium_weekly_review_sessions.id"],
            name="imperium_weekly_review_final_reports_session_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="imperium_weekly_review_final_reports_user_id_fkey"),
        sa.ForeignKeyConstraint(
            ["source_ai_result_id"],
            ["ai_results.id"],
            name="imperium_weekly_review_final_reports_source_ai_result_id_fkey",
        ),
        sa.UniqueConstraint("session_id", name="imperium_weekly_review_final_reports_session_unique"),
        sa.UniqueConstraint("user_id", "week_start", name="imperium_weekly_review_final_reports_user_week_unique"),
    )
    op.create_index("imperium_weekly_review_final_reports_user_status_idx", "imperium_weekly_review_final_reports", ["user_id", "status"])
    op.create_index("imperium_weekly_review_final_reports_user_week_idx", "imperium_weekly_review_final_reports", ["user_id", "week_start"])


def downgrade() -> None:
    op.drop_index("imperium_weekly_review_final_reports_user_week_idx", table_name="imperium_weekly_review_final_reports")
    op.drop_index("imperium_weekly_review_final_reports_user_status_idx", table_name="imperium_weekly_review_final_reports")
    op.drop_table("imperium_weekly_review_final_reports")

    op.drop_index("imperium_weekly_review_messages_user_created_idx", table_name="imperium_weekly_review_messages")
    op.drop_index("imperium_weekly_review_messages_session_created_idx", table_name="imperium_weekly_review_messages")
    op.drop_table("imperium_weekly_review_messages")

    op.drop_index("imperium_weekly_review_sessions_user_week_start_idx", table_name="imperium_weekly_review_sessions")
    op.drop_index("imperium_weekly_review_sessions_user_status_idx", table_name="imperium_weekly_review_sessions")
    op.drop_table("imperium_weekly_review_sessions")
