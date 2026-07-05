import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import AIMemory
from app.models.auth import User
from app.models.enums import IdempotencyStatus
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumMemoryCandidateDecision
from app.schemas.ai import (
    AIMemoryArchiveRequest,
    AIMemoryDraftRead,
    AIMemoryListResponse,
    AIMemoryRead,
    AIMemorySchemaHealth,
    AIMemorySupersedeRequest,
    SUPPORTED_AI_MEMORY_SOURCE_DOMAINS,
    SUPPORTED_AI_MEMORY_TYPES,
)

T = TypeVar("T")

MEMORY_STORAGE_ENABLED_NOTE = "Vector memory schema is defined. Canonical writes wait for the embedding service."
SUPPORTED_AI_MEMORY_PRIVACY_LEVELS = frozenset({"private"})
WR_MEMORY_COMMIT_DISABLED_REASON = "weekly_review_memory_commit_waits_for_embedding_service"


class AIMemoryValidationError(ValueError):
    pass


class AIMemoryDuplicateSourceError(ValueError):
    pass


class AIMemoryOwnershipError(ValueError):
    pass


class AIMemoryNotFoundError(ValueError):
    pass


class AIMemoryIdempotencyConflictError(ValueError):
    pass


def get_ai_memory_schema_health() -> AIMemorySchemaHealth:
    return AIMemorySchemaHealth(
        storage_enabled=False,
        table_defined=True,
        embeddings_enabled=False,
        pgvector_enabled=True,
        supported_memory_types=sorted(SUPPORTED_AI_MEMORY_TYPES),
        supported_source_domains=sorted(SUPPORTED_AI_MEMORY_SOURCE_DOMAINS),
        supported_privacy_levels=sorted(SUPPORTED_AI_MEMORY_PRIVACY_LEVELS),
        note=MEMORY_STORAGE_ENABLED_NOTE,
    )


def get_ai_memories(
    db: Session,
    *,
    current_user: User,
    limit: int = 20,
    offset: int = 0,
    is_active: bool | None = True,
    memory_type: str | None = None,
    learning_element_type: str | None = None,
    source_domain: str | None = None,
    source_table: str | None = None,
    source_id: str | None = None,
    privacy_level: str | None = None,
    q: str | None = None,
) -> AIMemoryListResponse:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    query = select(AIMemory).where(AIMemory.user_id == current_user.id)
    if is_active is not None:
        query = query.where(AIMemory.is_active == is_active)
    if memory_type:
        query = query.where(AIMemory.memory_type == memory_type)
    if learning_element_type:
        query = query.where(AIMemory.learning_element_type == learning_element_type)
    if source_domain:
        query = query.where(AIMemory.source_domain == source_domain)
    if source_table:
        query = query.where(AIMemory.source_table == source_table)
    if source_id:
        query = query.where(AIMemory.source_id == source_id)
    if privacy_level:
        query = query.where(AIMemory.privacy_level == privacy_level)
    if q and q.strip():
        query = query.where(AIMemory.content.ilike(f"%{q.strip()}%"))
    query = query.order_by(AIMemory.created_at.desc()).offset(offset).limit(limit + 1)
    memories = [
        memory
        for memory in db.scalars(query)
        if _memory_matches_filters(
            memory,
            user_id=current_user.id,
            is_active=is_active,
            memory_type=memory_type,
            learning_element_type=learning_element_type,
            source_domain=source_domain,
            source_table=source_table,
            source_id=source_id,
            privacy_level=privacy_level,
            q=q,
        )
    ]
    memories = sorted(memories, key=lambda memory: memory.created_at, reverse=True)
    has_more = len(memories) > limit
    items = memories[:limit]
    return AIMemoryListResponse(
        items=[AIMemoryRead.model_validate(memory) for memory in items],
        limit=limit,
        offset=offset,
        count=len(items),
        has_more=has_more,
    )


def get_ai_memory(db: Session, *, current_user: User, memory_id: UUID) -> AIMemoryRead:
    memory = db.get(AIMemory, memory_id)
    if memory is None or memory.user_id != current_user.id:
        raise AIMemoryNotFoundError("Memory not found.")
    return AIMemoryRead.model_validate(memory)


def archive_ai_memory(
    db: Session,
    *,
    current_user: User,
    memory_id: UUID,
    payload: AIMemoryArchiveRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[AIMemoryRead, bool]:
    request_payload = payload.model_dump(mode="json")
    request_hash = _hash_payload({"action": "ai_memory.archive", "memory_id": str(memory_id), **request_payload})
    existing_key = _get_existing_idempotency(db, user_id=current_user.id, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_idempotency(existing_key, request_hash, AIMemoryRead, request_path=request_path), True

    memory = _get_memory_for_update(db, current_user=current_user, memory_id=memory_id)
    if not memory.is_active:
        raise AIMemoryValidationError("Only active memories can be archived.")
    now = datetime.now(UTC)
    memory.is_active = False
    memory.updated_at = now
    if payload.reason:
        memory.correction_reason = _bounded_text(_clean_text(payload.reason), 500)
    response = AIMemoryRead.model_validate(memory)
    _store_idempotency(
        db,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response=response,
    )
    db.commit()
    return response, False


def supersede_ai_memory(
    db: Session,
    *,
    current_user: User,
    memory_id: UUID,
    payload: AIMemorySupersedeRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[AIMemoryRead, bool]:
    request_payload = payload.model_dump(mode="json")
    request_hash = _hash_payload({"action": "ai_memory.supersede", "memory_id": str(memory_id), **request_payload})
    existing_key = _get_existing_idempotency(db, user_id=current_user.id, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_idempotency(existing_key, request_hash, AIMemoryRead, request_path=request_path), True

    memory = _get_memory_for_update(db, current_user=current_user, memory_id=memory_id)
    if not memory.is_active:
        raise AIMemoryValidationError("Only active memories can be superseded.")

    draft = AIMemoryDraftRead(
        user_id=current_user.id,
        content=_bounded_text(_clean_text(payload.content), 1200) or "",
        embedding=payload.embedding,
        embedding_model=_clean_text(payload.embedding_model) or "",
        memory_type=_clean_text(payload.memory_type) or memory.memory_type,
        learning_element_type=_clean_text(payload.learning_element_type) or memory.learning_element_type,
        source_domain=_clean_text(payload.source_domain) or memory.source_domain,
        source_table=memory.source_table,
        source_id=memory.source_id,
        confidence=_clamped_confidence(payload.confidence if payload.confidence is not None else memory.confidence),
        privacy_level=_clean_text(payload.privacy_level) or memory.privacy_level,
        is_active=True,
        supersedes_memory_id=memory.id,
        correction_reason=_bounded_text(_clean_text(payload.reason), 500),
        metadata=_sanitize_memory_metadata(
            {
                "previous_memory_id": str(memory.id),
                "supersession_reason": payload.reason,
                "payload": payload.payload,
            }
        ),
        idempotency_key=idempotency_key,
    )
    new_memory = create_ai_memory_from_draft(db, draft=draft)
    now = datetime.now(UTC)
    memory.is_active = False
    memory.updated_at = now
    response = AIMemoryRead.model_validate(new_memory)
    _store_idempotency(
        db,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response=response,
    )
    db.commit()
    return response, False


def build_memory_draft_from_weekly_review_decision(
    decision: ImperiumMemoryCandidateDecision,
    *,
    current_user_id: UUID,
) -> AIMemoryDraftRead:
    if decision.user_id != current_user_id:
        raise AIMemoryOwnershipError("Memory candidate decision not found.")
    raise AIMemoryValidationError(WR_MEMORY_COMMIT_DISABLED_REASON)


def validate_memory_draft(draft: AIMemoryDraftRead) -> None:
    if not draft.content.strip():
        raise AIMemoryValidationError("Memory content is required.")
    if not draft.embedding_model.strip():
        raise AIMemoryValidationError("Embedding model is required.")
    if len(draft.embedding) != 1024:
        raise AIMemoryValidationError("Memory embedding must contain exactly 1024 dimensions.")
    if not draft.memory_type.strip():
        raise AIMemoryValidationError("Memory type is required.")
    if not draft.source_domain.strip():
        raise AIMemoryValidationError("Source domain is required.")
    if not draft.privacy_level.strip():
        raise AIMemoryValidationError("Privacy level is required.")
    if draft.confidence is not None and (draft.confidence < 0 or draft.confidence > 1):
        raise AIMemoryValidationError("Memory confidence must be between 0 and 1.")


def create_ai_memory_from_draft(
    db: Session,
    *,
    draft: AIMemoryDraftRead,
    idempotency_key: str | None = None,
) -> AIMemory:
    validate_memory_draft(draft)
    memory = AIMemory(
        user_id=draft.user_id,
        content=draft.content.strip(),
        embedding=draft.embedding,
        embedding_model=draft.embedding_model.strip(),
        memory_type=draft.memory_type.strip(),
        learning_element_type=_clean_text(draft.learning_element_type),
        source_domain=draft.source_domain.strip(),
        source_table=_clean_text(draft.source_table),
        source_id=_clean_text(draft.source_id),
        confidence=draft.confidence,
        privacy_level=draft.privacy_level.strip(),
        is_active=draft.is_active,
        supersedes_memory_id=draft.supersedes_memory_id,
        correction_reason=_clean_text(draft.correction_reason),
        expires_at=draft.expires_at,
        metadata_json=_sanitize_memory_metadata(draft.metadata or {}),
        idempotency_key=idempotency_key or draft.idempotency_key,
    )
    db.add(memory)
    db.flush()
    return memory


def ensure_memory_source_not_committed(
    db: Session,
    *,
    user_id: UUID,
    source_domain: str,
    source_table: str | None,
    source_id: str | None,
) -> None:
    if get_existing_memory_for_source(
        db,
        user_id=user_id,
        source_domain=source_domain,
        source_table=source_table,
        source_id=source_id,
    ) is not None:
        raise AIMemoryDuplicateSourceError("Memory source has already been committed.")


def get_existing_memory_for_source(
    db: Session,
    *,
    user_id: UUID,
    source_domain: str,
    source_table: str | None,
    source_id: str | None,
) -> AIMemory | None:
    query = select(AIMemory).where(
        AIMemory.user_id == user_id,
        AIMemory.source_domain == source_domain,
        AIMemory.source_table == source_table,
        AIMemory.source_id == source_id,
    )
    return db.scalar(query)


def _clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _bounded_text(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return value[:limit].strip()


def _clamped_confidence(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        confidence = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0.5")
    if confidence < 0:
        return Decimal("0")
    if confidence > 1:
        return Decimal("1")
    return confidence.quantize(Decimal("0.0001"))


def _sanitize_memory_metadata(value: dict | None) -> dict:
    if not value:
        return {}
    unsafe_keys = {"raw_payload", "secret", "secret_prompt", "internal_prompt", "hidden_reasoning"}
    return {key: _sanitize_memory_metadata_value(item) for key, item in value.items() if key not in unsafe_keys}


def _sanitize_memory_metadata_value(value):
    if isinstance(value, dict):
        return _sanitize_memory_metadata(value)
    if isinstance(value, list):
        return [_sanitize_memory_metadata_value(item) for item in value]
    return value


def _get_memory_for_update(db: Session, *, current_user: User, memory_id: UUID) -> AIMemory:
    memory = db.get(AIMemory, memory_id)
    if memory is None or memory.user_id != current_user.id:
        raise AIMemoryNotFoundError("Memory not found.")
    return memory


def _memory_matches_filters(
    memory: AIMemory,
    *,
    user_id: UUID,
    is_active: bool | None,
    memory_type: str | None,
    learning_element_type: str | None,
    source_domain: str | None,
    source_table: str | None,
    source_id: str | None,
    privacy_level: str | None,
    q: str | None,
) -> bool:
    if memory.user_id != user_id:
        return False
    if is_active is not None and memory.is_active != is_active:
        return False
    if memory_type and memory.memory_type != memory_type:
        return False
    if learning_element_type and memory.learning_element_type != learning_element_type:
        return False
    if source_domain and memory.source_domain != source_domain:
        return False
    if source_table and memory.source_table != source_table:
        return False
    if source_id and memory.source_id != source_id:
        return False
    if privacy_level and memory.privacy_level != privacy_level:
        return False
    if q and q.strip() and q.strip().lower() not in (memory.content or "").lower():
        return False
    return True


def _get_existing_idempotency(db: Session, *, user_id: UUID, idempotency_key: str) -> IdempotencyKey | None:
    return db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.idempotency_key == idempotency_key,
        )
    )


def _handle_idempotency(existing_key: IdempotencyKey, request_hash: str, schema: type[T], *, request_path: str) -> T:
    if existing_key.request_path != request_path:
        raise AIMemoryIdempotencyConflictError("Idempotency-Key already used on a different endpoint.")
    if existing_key.request_hash != request_hash:
        raise AIMemoryIdempotencyConflictError("Idempotency key already used with different payload.")
    if existing_key.response_body is None:
        raise AIMemoryIdempotencyConflictError("Idempotency key is already processing.")
    return schema.model_validate(existing_key.response_body)


def _store_idempotency(
    db: Session,
    *,
    user_id: UUID,
    idempotency_key: str,
    request_method: str,
    request_path: str,
    request_hash: str,
    response: AIMemoryRead,
) -> None:
    db.add(
        IdempotencyKey(
            user_id=user_id,
            idempotency_key=idempotency_key,
            request_method=request_method,
            request_path=request_path,
            request_hash=request_hash,
            status=IdempotencyStatus.completed,
            response_status_code=200,
            response_body=response.model_dump(mode="json"),
        )
    )


def _hash_payload(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
