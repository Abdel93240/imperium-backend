from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Numeric, Text, UniqueConstraint, text
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
