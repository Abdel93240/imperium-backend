"""add ai task and result foundation

Revision ID: 20260430_0012
Revises: 20260430_0011
Create Date: 2026-04-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260430_0012"
down_revision: str | None = "20260430_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("source_module", sa.Text(), nullable=False),
        sa.Column("input_payload", postgresql.JSONB(), nullable=False),
        sa.Column("prepared_payload", postgresql.JSONB(), nullable=True),
        sa.Column("router_decision", postgresql.JSONB(), nullable=True),
        sa.Column("model_hint", sa.Text(), nullable=True),
        sa.Column("privacy_level", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'result_received', 'validated', 'rejected', 'failed', 'cancelled')",
            name="ai_tasks_status_check",
        ),
        sa.CheckConstraint(
            "source_module IN ('imperium', 'vector', 'vault', 'pulse', 'path', 'system')",
            name="ai_tasks_source_module_check",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="ai_tasks_user_id_fkey"),
    )
    op.create_index("ai_tasks_user_status_idx", "ai_tasks", ["user_id", "status"])
    op.create_index("ai_tasks_user_task_type_idx", "ai_tasks", ["user_id", "task_type"])
    op.create_index("ai_tasks_user_source_module_idx", "ai_tasks", ["user_id", "source_module"])
    op.create_index("ai_tasks_created_at_idx", "ai_tasks", ["created_at"])
    op.create_index(
        "ai_tasks_user_idempotency_unique_idx",
        "ai_tasks",
        ["user_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.create_table(
        "ai_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("result_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending_validation'")),
        sa.Column("result_payload", postgresql.JSONB(), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        sa.Column("model_used", sa.Text(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('received', 'pending_validation', 'accepted', 'rejected', 'superseded')",
            name="ai_results_status_check",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ai_results_confidence_range",
        ),
        sa.ForeignKeyConstraint(["task_id"], ["ai_tasks.id"], name="ai_results_task_id_fkey", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="ai_results_user_id_fkey"),
        sa.UniqueConstraint("task_id", "idempotency_key", name="ai_results_task_idempotency_unique"),
    )
    op.create_index("ai_results_task_id_idx", "ai_results", ["task_id"])
    op.create_index("ai_results_status_idx", "ai_results", ["status"])
    op.create_index("ai_results_created_at_idx", "ai_results", ["created_at"])

    op.create_table(
        "ai_result_validations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("validation_status", sa.Text(), nullable=False),
        sa.Column("validated_payload", postgresql.JSONB(), nullable=True),
        sa.Column("user_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "validation_status IN ('accepted', 'rejected', 'edited')",
            name="ai_result_validations_status_check",
        ),
        sa.ForeignKeyConstraint(
            ["result_id"],
            ["ai_results.id"],
            name="ai_result_validations_result_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["ai_tasks.id"],
            name="ai_result_validations_task_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="ai_result_validations_user_id_fkey"),
    )
    op.create_index("ai_result_validations_result_id_idx", "ai_result_validations", ["result_id"])
    op.create_index("ai_result_validations_task_id_idx", "ai_result_validations", ["task_id"])
    op.create_index("ai_result_validations_created_at_idx", "ai_result_validations", ["created_at"])


def downgrade() -> None:
    op.drop_index("ai_result_validations_created_at_idx", table_name="ai_result_validations")
    op.drop_index("ai_result_validations_task_id_idx", table_name="ai_result_validations")
    op.drop_index("ai_result_validations_result_id_idx", table_name="ai_result_validations")
    op.drop_table("ai_result_validations")

    op.drop_index("ai_results_created_at_idx", table_name="ai_results")
    op.drop_index("ai_results_status_idx", table_name="ai_results")
    op.drop_index("ai_results_task_id_idx", table_name="ai_results")
    op.drop_table("ai_results")

    op.drop_index("ai_tasks_user_idempotency_unique_idx", table_name="ai_tasks")
    op.drop_index("ai_tasks_created_at_idx", table_name="ai_tasks")
    op.drop_index("ai_tasks_user_source_module_idx", table_name="ai_tasks")
    op.drop_index("ai_tasks_user_task_type_idx", table_name="ai_tasks")
    op.drop_index("ai_tasks_user_status_idx", table_name="ai_tasks")
    op.drop_table("ai_tasks")
