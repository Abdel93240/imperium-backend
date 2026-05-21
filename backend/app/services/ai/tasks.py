import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import AIResult, AIResultValidation, AITask
from app.models.auth import User
from app.schemas.ai import AIResultCallback, AIResultValidationCreate, AITaskCreate


class AITaskNotFoundError(ValueError):
    pass


class AIResultNotFoundError(ValueError):
    pass


class AIIdempotencyConflictError(ValueError):
    pass


class AIValidationError(ValueError):
    pass


class AIStateConflictError(ValueError):
    pass


def create_ai_task(
    db: Session,
    *,
    current_user: User,
    payload: AITaskCreate,
    idempotency_key: str,
) -> tuple[AITask, bool]:
    existing = _get_existing_task_by_idempotency(
        db,
        current_user=current_user,
        idempotency_key=idempotency_key,
    )
    request_hash = _hash_payload(payload.model_dump(mode="json"))
    if existing is not None:
        existing_hash = _hash_payload(
            {
                "task_type": existing.task_type,
                "source_module": existing.source_module,
                "input_payload": existing.input_payload,
                "prepared_payload": existing.prepared_payload,
                "router_decision": existing.router_decision,
                "model_hint": existing.model_hint,
                "privacy_level": existing.privacy_level,
            }
        )
        if existing_hash != request_hash:
            raise AIIdempotencyConflictError("Idempotency key already used with different payload.")
        return existing, True

    task = AITask(
        user_id=current_user.id,
        task_type=payload.task_type,
        status="queued",
        source_module=payload.source_module,
        input_payload=payload.input_payload,
        prepared_payload=payload.prepared_payload,
        router_decision=payload.router_decision,
        model_hint=payload.model_hint,
        privacy_level=payload.privacy_level,
        idempotency_key=idempotency_key,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task, False


def get_ai_task(db: Session, *, current_user: User, task_id: UUID) -> AITask:
    task = db.get(AITask, task_id)
    if task is None or task.user_id != current_user.id:
        raise AITaskNotFoundError("AI task not found.")
    return task


def mark_ai_task_running(
    db: Session,
    *,
    current_user: User,
    task_id: UUID,
) -> tuple[AITask, bool]:
    task = get_ai_task(db, current_user=current_user, task_id=task_id)
    if task.status == "queued":
        task.status = "running"
        task.started_at = datetime.now(UTC)
        transitioned = True
    elif task.status == "running":
        transitioned = False
    else:
        raise AIStateConflictError("AI task cannot be marked running from its current state.")
    db.commit()
    db.refresh(task)
    return task, transitioned


def receive_ai_result(
    db: Session,
    *,
    task_id: UUID,
    payload: AIResultCallback,
    idempotency_key: str,
) -> tuple[AIResult, bool]:
    task = db.get(AITask, task_id)
    if task is None:
        raise AITaskNotFoundError("AI task not found.")

    request_hash = _hash_payload(payload.model_dump(mode="json"))
    existing = _get_existing_result_by_idempotency(
        db,
        task_id=task_id,
        idempotency_key=idempotency_key,
    )
    if existing is not None:
        existing_hash = _hash_payload(
            {
                "result_type": existing.result_type,
                "result_payload": existing.result_payload,
                "model_used": existing.model_used,
                "provider": existing.provider,
                "confidence": str(existing.confidence) if existing.confidence is not None else None,
                "raw_payload": existing.raw_payload,
            }
        )
        if existing_hash != request_hash:
            raise AIIdempotencyConflictError("Idempotency key already used with different payload.")
        return existing, True

    result = AIResult(
        task_id=task.id,
        user_id=task.user_id,
        result_type=payload.result_type,
        status="pending_validation",
        result_payload=payload.result_payload,
        raw_payload=payload.raw_payload,
        model_used=payload.model_used,
        provider=payload.provider,
        confidence=payload.confidence,
        idempotency_key=idempotency_key,
    )
    task.status = "result_received"
    task.completed_at = datetime.now(UTC)
    db.add(result)
    db.commit()
    db.refresh(result)
    return result, False


def validate_ai_result(
    db: Session,
    *,
    current_user: User,
    result_id: UUID,
    payload: AIResultValidationCreate,
) -> AIResultValidation:
    result = _get_ai_result_for_user(db, current_user=current_user, result_id=result_id)
    if payload.validation_status not in {"accepted", "edited"}:
        raise AIValidationError("Validation status must be accepted or edited.")
    _ensure_result_can_be_validated(result)
    validation = _create_validation(
        db,
        current_user=current_user,
        result=result,
        validation_status=payload.validation_status,
        validated_payload=payload.validated_payload,
        user_note=payload.user_note,
    )
    result.status = "accepted"
    task = db.get(AITask, result.task_id)
    if task is not None:
        task.status = "validated"
    db.commit()
    db.refresh(validation)
    return validation


def reject_ai_result(
    db: Session,
    *,
    current_user: User,
    result_id: UUID,
    payload: AIResultValidationCreate,
) -> AIResultValidation:
    result = _get_ai_result_for_user(db, current_user=current_user, result_id=result_id)
    if payload.validation_status != "rejected":
        raise AIValidationError("Validation status must be rejected.")
    _ensure_result_can_be_validated(result)
    validation = _create_validation(
        db,
        current_user=current_user,
        result=result,
        validation_status="rejected",
        validated_payload=payload.validated_payload,
        user_note=payload.user_note,
    )
    result.status = "rejected"
    task = db.get(AITask, result.task_id)
    if task is not None:
        task.status = "rejected"
    db.commit()
    db.refresh(validation)
    return validation


def fail_ai_task(
    db: Session,
    *,
    task_id: UUID,
    error_code: str,
    error_message: str,
) -> AITask:
    task = db.get(AITask, task_id)
    if task is None:
        raise AITaskNotFoundError("AI task not found.")
    task.status = "failed"
    task.failed_at = datetime.now(UTC)
    task.error_code = error_code
    task.error_message = error_message
    db.commit()
    db.refresh(task)
    return task


def _create_validation(
    db: Session,
    *,
    current_user: User,
    result: AIResult,
    validation_status: str,
    validated_payload: dict | None,
    user_note: str | None,
) -> AIResultValidation:
    validation = AIResultValidation(
        result_id=result.id,
        task_id=result.task_id,
        user_id=current_user.id,
        validation_status=validation_status,
        validated_payload=validated_payload,
        user_note=user_note,
    )
    db.add(validation)
    return validation


def _ensure_result_can_be_validated(result: AIResult) -> None:
    if result.status in {"accepted", "rejected", "superseded"}:
        raise AIValidationError("AI result has already reached a terminal validation state.")


def _get_ai_result_for_user(db: Session, *, current_user: User, result_id: UUID) -> AIResult:
    result = db.get(AIResult, result_id)
    if result is None or result.user_id != current_user.id:
        raise AIResultNotFoundError("AI result not found.")
    return result


def _get_existing_task_by_idempotency(
    db: Session,
    *,
    current_user: User,
    idempotency_key: str,
) -> AITask | None:
    return db.scalar(
        select(AITask).where(
            AITask.user_id == current_user.id,
            AITask.idempotency_key == idempotency_key,
        )
    )


def _get_existing_result_by_idempotency(
    db: Session,
    *,
    task_id: UUID,
    idempotency_key: str,
) -> AIResult | None:
    return db.scalar(
        select(AIResult).where(
            AIResult.task_id == task_id,
            AIResult.idempotency_key == idempotency_key,
        )
    )


def _hash_payload(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
