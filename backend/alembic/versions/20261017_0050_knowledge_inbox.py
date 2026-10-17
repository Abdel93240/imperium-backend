"""knowledge inbox (Nourrir l'IA): items, retained sources, runner job

Doc 70 §6–§12 ; décisions utilisateur 2026-10-15/16. Un élément regroupe un texte de
contexte et zéro, un ou plusieurs fichiers sources (toujours conservés, pointeur
abstrait, VPS en V1). Le job ai.knowledge_inbox (semé désactivé) analyse les éléments
et vectorise ceux que l'utilisateur a validés.

Revision ID: 20261017_0050
Revises: 20261017_0049
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261017_0050"
down_revision: str | None = "20261017_0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JOB_CODE = "ai.knowledge_inbox"


def upgrade() -> None:
    op.create_table(
        "knowledge_inbox_items",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entry_app", sa.Text(), nullable=False, server_default=sa.text("'imperium'")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("context_text", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'uploading'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("extraction_draft", postgresql.JSONB(), nullable=True),
        sa.Column("extraction_final", postgresql.JSONB(), nullable=True),
        sa.Column("destination", sa.Text(), nullable=True),
        sa.Column("created_entity_type", sa.Text(), nullable=True),
        sa.Column("created_entity_id", UUID, nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("vectorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("entry_app IN ('imperium', 'vector', 'vault', 'pulse', 'path')", name="entry_app_check"),
        sa.CheckConstraint(
            "status IN ('uploading', 'to_analyze', 'analyzing', 'to_validate', 'validated', 'vectorized', 'failed', 'deleted')",
            name="status_check",
        ),
        sa.CheckConstraint("destination IS NULL OR destination IN ('memory', 'project')", name="destination_check"),
        sa.CheckConstraint("created_entity_type IS NULL OR created_entity_type IN ('project')", name="created_entity_type_check"),
    )
    op.create_index("knowledge_inbox_items_user_status_idx", "knowledge_inbox_items", ["user_id", "status"])
    op.create_index(
        "knowledge_inbox_items_user_idempotency_idx",
        "knowledge_inbox_items",
        ["user_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_table(
        "knowledge_inbox_documents",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", UUID, sa.ForeignKey("knowledge_inbox_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("storage_pointer", sa.Text(), nullable=True),
        sa.Column("storage_location", sa.Text(), nullable=False, server_default=sa.text("'vps_local'")),
        sa.Column("source_retained_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("kind IN ('document', 'image', 'audio', 'video')", name="kind_check"),
        sa.CheckConstraint("storage_location IN ('vps_local', 'nas')", name="storage_location_check"),
        sa.CheckConstraint("size_bytes >= 0", name="size_non_negative"),
    )
    op.create_index("knowledge_inbox_documents_item_idx", "knowledge_inbox_documents", ["item_id"])
    op.get_bind().exec_driver_sql(
        """
        INSERT INTO job_definitions
          (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s)
        VALUES (gen_random_uuid(), %s, 'event_subscription', NULL, %s, %s, false, true, 600)
        ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING
        """,
        (JOB_CODE, ["inbox.document.uploaded", "inbox.document.validated"],
         "app.services.ai.knowledge_inbox_runner:knowledge_inbox_job"),
    )


def downgrade() -> None:
    op.get_bind().exec_driver_sql("DELETE FROM job_definitions WHERE code = %s", (JOB_CODE,))
    op.drop_index("knowledge_inbox_documents_item_idx", table_name="knowledge_inbox_documents")
    op.drop_table("knowledge_inbox_documents")
    op.drop_index("knowledge_inbox_items_user_idempotency_idx", table_name="knowledge_inbox_items")
    op.drop_index("knowledge_inbox_items_user_status_idx", table_name="knowledge_inbox_items")
    op.drop_table("knowledge_inbox_items")
