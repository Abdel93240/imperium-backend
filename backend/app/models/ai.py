from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Numeric, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.postgres_types import Vector1024
from app.db.base import Base, UUIDPrimaryKeyMixin


class AITask(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'result_received', 'validated', 'rejected', 'failed', 'cancelled')",
            name="ai_tasks_status_check",
        ),
        CheckConstraint(
            "source_module IN ('imperium', 'vector', 'vault', 'pulse', 'path', 'system')",
            name="ai_tasks_source_module_check",
        ),
        Index("ai_tasks_user_status_idx", "user_id", "status"),
        Index("ai_tasks_user_task_type_idx", "user_id", "task_type"),
        Index("ai_tasks_user_source_module_idx", "user_id", "source_module"),
        Index("ai_tasks_created_at_idx", "created_at"),
        Index(
            "ai_tasks_user_idempotency_unique_idx",
            "user_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    task_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued", server_default=text("'queued'"))
    source_module: Mapped[str] = mapped_column(Text, nullable=False)
    input_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    prepared_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    router_decision: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    model_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    privacy_level: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class AIResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_results"
    __table_args__ = (
        CheckConstraint(
            "status IN ('received', 'pending_validation', 'accepted', 'rejected', 'superseded')",
            name="ai_results_status_check",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ai_results_confidence_range",
        ),
        UniqueConstraint("task_id", "idempotency_key", name="ai_results_task_idempotency_unique"),
        Index("ai_results_task_id_idx", "task_id"),
        Index("ai_results_status_idx", "status"),
        Index("ai_results_created_at_idx", "created_at"),
    )

    task_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    result_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="pending_validation",
        server_default=text("'pending_validation'"),
    )
    result_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    model_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AIResultValidation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_result_validations"
    __table_args__ = (
        CheckConstraint(
            "validation_status IN ('accepted', 'rejected', 'edited')",
            name="ai_result_validations_status_check",
        ),
        Index("ai_result_validations_result_id_idx", "result_id"),
        Index("ai_result_validations_task_id_idx", "task_id"),
        Index("ai_result_validations_created_at_idx", "created_at"),
    )

    result_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    validation_status: Mapped[str] = mapped_column(Text, nullable=False)
    validated_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    user_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class AIMemory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_memories"
    __table_args__ = (
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ai_memories_confidence_range"),
        Index(
            "ai_memories_embedding_hnsw_idx",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ai_memories_user_source_domain_type_active_idx", "user_id", "source_domain", "memory_type", "is_active"),
        Index("ai_memories_user_privacy_active_idx", "user_id", "privacy_level", "is_active"),
        Index("ai_memories_source_table_id_idx", "source_table", "source_id"),
        Index("ai_memories_expires_at_idx", "expires_at"),
        Index("ai_memories_user_created_idx", "user_id", text("created_at DESC")),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector1024(), nullable=False)
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False)
    memory_type: Mapped[str] = mapped_column(Text, nullable=False)
    learning_element_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_domain: Mapped[str] = mapped_column(Text, nullable=False)
    source_table: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    privacy_level: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    supersedes_memory_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_memories.id", ondelete="SET NULL"),
        nullable=True,
    )
    correction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class KnowledgeInboxItem(UUIDPrimaryKeyMixin, Base):
    """Élément transmis à l'IA (doc 70) : contexte + sources, brouillon puis version validée."""

    __tablename__ = "knowledge_inbox_items"
    __table_args__ = (
        CheckConstraint("entry_app IN ('imperium', 'vector', 'vault', 'pulse', 'path')", name="entry_app_check"),
        CheckConstraint(
            "status IN ('uploading', 'to_analyze', 'analyzing', 'to_validate', 'validated', 'vectorized', 'failed', 'deleted')",
            name="status_check",
        ),
        CheckConstraint("destination IS NULL OR destination IN ('memory', 'project')", name="destination_check"),
        CheckConstraint("created_entity_type IS NULL OR created_entity_type IN ('project')", name="created_entity_type_check"),
        Index("knowledge_inbox_items_user_status_idx", "user_id", "status"),
        Index(
            "knowledge_inbox_items_user_idempotency_idx",
            "user_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # Provenance UI seulement : ne restreint jamais l'usage de la connaissance (doc 70 §2).
    entry_app: Mapped[str] = mapped_column(Text, nullable=False, default="imperium", server_default=text("'imperium'"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    context_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="uploading", server_default=text("'uploading'"))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_draft: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extraction_final: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    destination: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_entity_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_entity_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    vectorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class KnowledgeInboxDocument(UUIDPrimaryKeyMixin, Base):
    """Fichier source d'un élément, toujours conservé (pointeur abstrait, doc 70 §4)."""

    __tablename__ = "knowledge_inbox_documents"
    __table_args__ = (
        CheckConstraint("kind IN ('document', 'image', 'audio', 'video')", name="kind_check"),
        CheckConstraint("storage_location IN ('vps_local', 'nas')", name="storage_location_check"),
        CheckConstraint("size_bytes >= 0", name="size_non_negative"),
        Index("knowledge_inbox_documents_item_idx", "item_id"),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("knowledge_inbox_items.id", ondelete="CASCADE"), nullable=False
    )
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    storage_pointer: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_location: Mapped[str] = mapped_column(Text, nullable=False, default="vps_local", server_default=text("'vps_local'"))
    source_retained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
