from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import SessionDep
from app.core.internal_webhooks import (
    InternalWebhookContext,
    verify_internal_webhook,
)
from app.core.config import get_settings
from app.models.auth import User
from app.schemas.ai import AIResultCallback, AIResultCallbackResponse, QwenSmokeRequest, QwenWeeklySummary
from app.schemas.weekly_review import WeeklyReviewAttachAIResultRequest, WeeklyReviewSessionRead
from app.services.ai.providers.qwen import QwenClient, QwenProviderError
from app.services.ai.tasks import AIIdempotencyConflictError, AITaskNotFoundError, receive_ai_result
from app.services.imperium.weekly_review_conversation import (
    WeeklyReviewAIResultConflictError,
    WeeklyReviewIdempotencyConflictError,
    WeeklyReviewSessionNotFoundError,
    WeeklyReviewStateConflictError,
    attach_ai_result_to_session,
    mock_weekly_review_summary,
)
from app.services.imperium.weekly_review_state import (
    IdempotencyConflictError,
    InvalidWeekStartError,
    mark_weekly_review_ready,
)

router = APIRouter()


@router.post("/webhook-test")
def verify_internal_webhook_test(
    context: Annotated[InternalWebhookContext, Depends(verify_internal_webhook)],
) -> dict[str, str | bool]:
    """Verification-only endpoint for internal webhook security skeleton."""
    return {
        "status": "ok",
        "accepted": True,
        "idempotency_key": context.idempotency_key,
    }


@router.post("/weekly-review/ready")
def mark_weekly_review_ready_route(
    week_start: date,
    context: Annotated[InternalWebhookContext, Depends(verify_internal_webhook)],
    db: SessionDep,
) -> dict:
    settings = get_settings()
    if settings.imperium_canonical_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Canonical user is not configured.",
        )
    current_user = db.get(User, settings.imperium_canonical_user_id)
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Canonical user not found.")
    try:
        mark_weekly_review_ready(
            db,
            current_user=current_user,
            week_start=week_start,
            idempotency_key=context.idempotency_key,
            request_method="POST",
            request_path="/api/internal/weekly-review/ready",
        )
    except InvalidWeekStartError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except IdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return {"status": "ok", "week_start": str(week_start), "ready": True}


@router.post("/ai/tasks/{task_id}/result", response_model=AIResultCallbackResponse)
def receive_ai_task_result_route(
    task_id: UUID,
    payload: AIResultCallback,
    context: Annotated[InternalWebhookContext, Depends(verify_internal_webhook)],
    db: SessionDep,
) -> AIResultCallbackResponse:
    try:
        result, _duplicate = receive_ai_result(
            db,
            task_id=task_id,
            payload=payload,
            idempotency_key=context.idempotency_key,
        )
    except AITaskNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AIIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return AIResultCallbackResponse(
        status="ok",
        task_id=task_id,
        result_id=result.id,
        result_status=result.status,
        idempotency_key=context.idempotency_key,
    )


@router.post("/ai/qwen/smoke", response_model=QwenWeeklySummary)
def internal_qwen_smoke_route(
    payload: QwenSmokeRequest,
    context: Annotated[InternalWebhookContext, Depends(verify_internal_webhook)],
) -> QwenWeeklySummary:
    """Internal dry-run bridge for n8n WR workflow contract testing only."""
    _ = context
    if payload.task_type != "weekly_report.summary" or payload.mode != "weekly_summary":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Internal Qwen smoke only supports weekly_report.summary in weekly_summary mode.",
        )
    try:
        return QwenClient().generate_weekly_summary(input_payload=payload.input_payload)
    except QwenProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/weekly-review/{session_id}/attach-ai-result", response_model=WeeklyReviewSessionRead)
def attach_weekly_review_ai_result_route(
    session_id: UUID,
    payload: WeeklyReviewAttachAIResultRequest,
    context: Annotated[InternalWebhookContext, Depends(verify_internal_webhook)],
    db: SessionDep,
) -> WeeklyReviewSessionRead:
    try:
        result, _duplicate = attach_ai_result_to_session(
            db,
            session_id=session_id,
            payload=payload,
            idempotency_key=context.idempotency_key,
            request_method="POST",
            request_path=f"/api/internal/weekly-review/{session_id}/attach-ai-result",
        )
    except WeeklyReviewSessionNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (WeeklyReviewAIResultConflictError, WeeklyReviewIdempotencyConflictError, WeeklyReviewStateConflictError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return result


@router.post("/weekly-review/{session_id}/mock-ai-summary", response_model=WeeklyReviewSessionRead)
def mock_weekly_review_ai_summary_route(
    session_id: UUID,
    payload: AIResultCallback,
    context: Annotated[InternalWebhookContext, Depends(verify_internal_webhook)],
    db: SessionDep,
) -> WeeklyReviewSessionRead:
    """Temporary mock-only endpoint for local WR/n8n contract smoke testing."""
    settings = get_settings()
    if settings.environment not in {"local", "test"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not available in this environment.")

    try:
        result, _duplicate = mock_weekly_review_summary(
            db,
            session_id=session_id,
            payload=payload,
            idempotency_key=context.idempotency_key,
            request_method="POST",
            request_path=f"/api/internal/weekly-review/{session_id}/mock-ai-summary",
        )
    except WeeklyReviewSessionNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (WeeklyReviewAIResultConflictError, WeeklyReviewIdempotencyConflictError, WeeklyReviewStateConflictError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return result
