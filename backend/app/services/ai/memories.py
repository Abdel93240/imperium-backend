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
    AIMemoryListResponse,
    AIMemoryRead,
    AIMemoryDraftRead,
    AIMemorySchemaHealth,
    AIMemorySupersedeRequest,
    SUPPORTED_AI_MEMORY_KINDS,
    SUPPORTED_AI_MEMORY_SCOPES,
)

T = TypeVar("T")

MEMORY_STORAGE_ENABLED_NOTE = "Explicit user-triggered memory commit is enabled. Semantic vector indexing is disabled."
SUPPORTED_AI_MEMORY_STATUSES = frozenset({"active", "archived", "superseded", "deleted"})
SUPPORTED_AI_MEMORY_VISIBILITY = frozenset({"private"})
DEFAULT_MEMORY_KIND = "operational_signal"
DEFAULT_MEMORY_SCOPE = "weekly_review"


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
        storage_enabled=True,
        table_defined=True,
        embeddings_enabled=False,
        pgvector_enabled=False,
        supported_kinds=sorted(SUPPORTED_AI_MEMORY_KINDS),
        supported_scopes=sorted(SUPPORTED_AI_MEMORY_SCOPES),
        supported_statuses=sorted(SUPPORTED_AI_MEMORY_STATUSES),
        supported_visibility=sorted(SUPPORTED_AI_MEMORY_VISIBILITY),
        note=MEMORY_STORAGE_ENABLED_NOTE,
    )


def get_ai_memories(
    db: Session,
    *,
    current_user: User,
    limit: int = 20,
    offset: int = 0,
    status: str | None = "active",
    kind: str | None = None,
    scope: str | None = None,
    source_module: str | None = None,
    source_type: str | None = None,
    source_report_id: UUID | None = None,
    source_session_id: UUID | None = None,
    source_candidate_id: str | None = None,
    source_decision_id: UUID | None = None,
    q: str | None = None,
) -> AIMemoryListResponse:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    query = select(AIMemory).where(AIMemory.user_id == current_user.id)
    if status and status != "all":
        query = query.where(AIMemory.status == status)
    if kind:
        query = query.where(AIMemory.kind == kind)
    if scope:
        query = query.where(AIMemory.scope == scope)
    if source_module:
        query = query.where(AIMemory.source_module == source_module)
    if source_type:
        query = query.where(AIMemory.source_type == source_type)
    if source_report_id:
        query = query.where(AIMemory.source_report_id == source_report_id)
    if source_session_id:
        query = query.where(AIMemory.source_session_id == source_session_id)
    if source_candidate_id:
        query = query.where(AIMemory.source_candidate_id == source_candidate_id)
    if source_decision_id:
        query = query.where(AIMemory.source_decision_id == source_decision_id)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        query = query.where(AIMemory.title.ilike(pattern) | AIMemory.content.ilike(pattern))
    query = query.order_by(AIMemory.created_at.desc()).offset(offset).limit(limit + 1)
    memories = [
        memory
        for memory in db.scalars(query)
        if _memory_matches_filters(
            memory,
            user_id=current_user.id,
            status=status,
            kind=kind,
            scope=scope,
            source_module=source_module,
            source_type=source_type,
            source_report_id=source_report_id,
            source_session_id=source_session_id,
            source_candidate_id=source_candidate_id,
            source_decision_id=source_decision_id,
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
    if memory.status != "active":
        raise AIMemoryValidationError("Only active memories can be archived.")
    now = datetime.now(UTC)
    memory.status = "archived"
    memory.archived_at = now
    memory.updated_at = now
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
    if memory.status != "active":
        raise AIMemoryValidationError("Only active memories can be superseded.")

    kind = payload.kind or memory.kind
    scope = payload.scope or memory.scope
    confidence = _clamped_confidence(payload.confidence if payload.confidence is not None else memory.confidence)
    draft = AIMemoryDraftRead(
        user_id=current_user.id,
        source_module=memory.source_module,
        source_type="memory_supersession",
        source_id=str(memory.id),
        source_report_id=memory.source_report_id,
        source_session_id=memory.source_session_id,
        source_candidate_id=memory.source_candidate_id,
        source_decision_id=None,
        kind=kind,
        scope=scope,
        title=_bounded_text(_clean_text(payload.title), 160) or memory.title,
        content=_bounded_text(_clean_text(payload.content), 1200) or "",
        confidence=confidence,
        status="active",
        visibility="private",
        metadata_json=_sanitize_memory_metadata(
            {
                "previous_memory_id": str(memory.id),
                "supersession_reason": payload.reason,
                "payload": payload.payload,
            }
        ),
    )
    new_memory = create_ai_memory_from_draft(db, draft=draft, idempotency_key=idempotency_key)
    now = datetime.now(UTC)
    memory.status = "superseded"
    memory.superseded_by_id = new_memory.id
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
    if decision.decision == "rejected":
        raise AIMemoryValidationError("Rejected memory candidate decisions cannot become memory.")
    if decision.decision not in {"approved", "edited"}:
        raise AIMemoryValidationError("Only approved or edited memory candidate decisions can become memory.")

    candidate = decision.edited_candidate if decision.decision == "edited" and decision.edited_candidate else decision.original_candidate
    if not isinstance(candidate, dict):
        raise AIMemoryValidationError("Memory candidate payload is invalid.")

    kind = _clean_text(candidate.get("kind")) or DEFAULT_MEMORY_KIND
    scope = _clean_text(candidate.get("proposed_memory_scope")) or DEFAULT_MEMORY_SCOPE
    title = _bounded_text(_clean_text(candidate.get("title")), 160)
    content = _bounded_text(_clean_text(candidate.get("content")), 1200)
    confidence = _clamped_confidence(candidate.get("confidence"))

    draft = AIMemoryDraftRead(
        user_id=decision.user_id,
        source_module="weekly_review",
        source_type="memory_candidate_decision",
        source_id=str(decision.id),
        source_report_id=decision.report_id,
        source_session_id=decision.session_id,
        source_candidate_id=decision.candidate_id,
        source_decision_id=decision.id,
        kind=kind,
        scope=scope,
        title=title or "",
        content=content or "",
        confidence=confidence,
        status="active",
        visibility="private",
        metadata_json=_sanitize_memory_metadata(
            {
                "decision": decision.decision,
                "decision_source": decision.source,
                "candidate_id": decision.candidate_id,
            }
        ),
    )
    validate_memory_draft(draft)
    return draft


def validate_memory_draft(draft: AIMemoryDraftRead) -> None:
    if not draft.title.strip():
        raise AIMemoryValidationError("Memory title is required.")
    if not draft.content.strip():
        raise AIMemoryValidationError("Memory content is required.")
    if draft.kind not in SUPPORTED_AI_MEMORY_KINDS:
        raise AIMemoryValidationError("Unsupported memory kind.")
    if draft.scope not in SUPPORTED_AI_MEMORY_SCOPES:
        raise AIMemoryValidationError("Unsupported memory scope.")
    if draft.status not in SUPPORTED_AI_MEMORY_STATUSES:
        raise AIMemoryValidationError("Unsupported memory status.")
    if draft.visibility not in SUPPORTED_AI_MEMORY_VISIBILITY:
        raise AIMemoryValidationError("Unsupported memory visibility.")
    if draft.confidence < 0 or draft.confidence > 1:
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
        source_module=draft.source_module,
        source_type=draft.source_type,
        source_id=draft.source_id,
        source_report_id=draft.source_report_id,
        source_session_id=draft.source_session_id,
        source_candidate_id=draft.source_candidate_id,
        source_decision_id=draft.source_decision_id,
        kind=draft.kind,
        scope=draft.scope,
        title=draft.title.strip(),
        content=draft.content.strip(),
        confidence=draft.confidence,
        status=draft.status,
        visibility=draft.visibility,
        metadata_json=_sanitize_memory_metadata(draft.metadata_json or {}),
        idempotency_key=idempotency_key,
    )
    db.add(memory)
    db.flush()
    return memory


def ensure_memory_source_not_committed(
    db: Session,
    *,
    user_id: UUID,
    source_module: str,
    source_type: str,
    source_decision_id: UUID | None,
    source_id: str,
) -> None:
    query = select(AIMemory).where(
        AIMemory.user_id == user_id,
        AIMemory.source_module == source_module,
        AIMemory.source_type == source_type,
    )
    if source_decision_id is not None:
        query = query.where(AIMemory.source_decision_id == source_decision_id)
    else:
        query = query.where(AIMemory.source_id == source_id)
    if db.scalar(query) is not None:
        raise AIMemoryDuplicateSourceError("Memory source has already been committed.")


def get_existing_memory_for_source(
    db: Session,
    *,
    user_id: UUID,
    source_module: str,
    source_type: str,
    source_decision_id: UUID | None,
    source_id: str,
) -> AIMemory | None:
    query = select(AIMemory).where(
        AIMemory.user_id == user_id,
        AIMemory.source_module == source_module,
        AIMemory.source_type == source_type,
    )
    if source_decision_id is not None:
        query = query.where(AIMemory.source_decision_id == source_decision_id)
    else:
        query = query.where(AIMemory.source_id == source_id)
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


def _clamped_confidence(value: object) -> Decimal:
    try:
        confidence = Decimal(str(value if value is not None else "0.5"))
    except (InvalidOperation, ValueError):
        confidence = Decimal("0.5")
    if confidence < 0:
        return Decimal("0")
    if confidence > 1:
        return Decimal("1")
    return confidence.quantize(Decimal("0.0001"))


def _sanitize_memory_metadata(value: dict) -> dict:
    unsafe_keys = {"raw_payload", "secret", "secret_prompt", "internal_prompt", "hidden_reasoning"}
    return {
        key: _sanitize_memory_metadata_value(item)
        for key, item in value.items()
        if key not in unsafe_keys
    }


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
    status: str | None,
    kind: str | None,
    scope: str | None,
    source_module: str | None,
    source_type: str | None,
    source_report_id: UUID | None,
    source_session_id: UUID | None,
    source_candidate_id: str | None,
    source_decision_id: UUID | None,
    q: str | None,
) -> bool:
    if memory.user_id != user_id:
        return False
    if status and status != "all" and memory.status != status:
        return False
    if kind and memory.kind != kind:
        return False
    if scope and memory.scope != scope:
        return False
    if source_module and memory.source_module != source_module:
        return False
    if source_type and memory.source_type != source_type:
        return False
    if source_report_id and memory.source_report_id != source_report_id:
        return False
    if source_session_id and memory.source_session_id != source_session_id:
        return False
    if source_candidate_id and memory.source_candidate_id != source_candidate_id:
        return False
    if source_decision_id and memory.source_decision_id != source_decision_id:
        return False
    if q and q.strip():
        needle = q.strip().lower()
        if needle not in (memory.title or "").lower() and needle not in (memory.content or "").lower():
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
