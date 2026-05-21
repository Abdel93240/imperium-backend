import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai import AIMemory, AIResult, AITask
from app.models.auth import User
from app.models.enums import IdempotencyStatus
from app.models.idempotency import IdempotencyKey
from app.models.imperium import (
    ImperiumMemoryCandidateDecision,
    ImperiumWeeklyReviewFinalReport,
    ImperiumWeeklyReviewMessage,
    ImperiumWeeklyReviewSession,
)
from app.schemas.weekly_review import (
    WeeklyReviewAnswerRequest,
    WeeklyReviewAttachAIResultRequest,
    WeeklyReviewAIResultDebugSummary,
    WeeklyReviewAIResultSummary,
    WeeklyReviewAITaskSummary,
    WeeklyReviewActionDescriptor,
    WeeklyReviewCancelRequest,
    WeeklyReviewChatConfirmRequest,
    WeeklyReviewChatTimelineItem,
    WeeklyReviewConversationFlags,
    WeeklyReviewConversationRead,
    WeeklyReviewCurrentResponse,
    WeeklyReviewDebugStatusRead,
    WeeklyReviewDraftCreate,
    WeeklyReviewDraftRejectRequest,
    WeeklyReviewDraftRead,
    WeeklyReviewDraftReviewState,
    WeeklyReviewFinalApproveRequest,
    WeeklyReviewFinalReportRead,
    WeeklyReviewFinalReportSummary,
    WeeklyReviewHistoryItem,
    WeeklyReviewHistoryResponse,
    WeeklyReviewMemoryCandidateRead,
    WeeklyReviewMemoryCandidateApproveRequest,
    WeeklyReviewMemoryCandidateDecisionRead,
    WeeklyReviewMemoryCandidateDecisionsResponse,
    WeeklyReviewMemoryCandidateEditRequest,
    WeeklyReviewMemoryCandidateRejectRequest,
    WeeklyReviewMemoryCandidatesPreviewResponse,
    WeeklyReviewMemoryCandidatesResponse,
    WeeklyReviewMemoryCommitCandidateRead,
    WeeklyReviewMemoryCommitDryRunRead,
    WeeklyReviewMemoryCommitDryRunRequest,
    WeeklyReviewMemoryAlreadyCommittedItem,
    WeeklyReviewMemoryCommitItem,
    WeeklyReviewMemoryCommitRead,
    WeeklyReviewMemoryCommitRequest,
    WeeklyReviewMemoryCommitPreviewRead,
    WeeklyReviewMessageRead,
    WeeklyReviewRevisionRequest,
    WeeklyReviewSessionRead,
    WeeklyReviewStoredFinalReportSummary,
    WeeklyReviewStoredFinalReportsResponse,
    WeeklyReviewVisibleAIState,
    week_end_for,
)
from app.schemas.ai import AIResultCallback
from app.services.ai.memories import (
    AIMemoryOwnershipError,
    AIMemoryValidationError,
    build_memory_draft_from_weekly_review_decision,
    create_ai_memory_from_draft,
    get_existing_memory_for_source,
)
from app.services.ai.tasks import receive_ai_result
from app.services.integrations.n8n_client import (
    N8NConfigurationError,
    N8NRequestError,
    n8n_is_configured,
    trigger_n8n_webhook,
)

T = TypeVar("T", bound=BaseModel)

COMPATIBLE_AI_RESULT_TYPES = {
    "weekly_report.summary",
    "weekly_report.questions",
    "weekly_report.draft",
    "weekly_report.final",
    "weekly_report.revision",
}
ANSWER_INTEGRATION_TASK_TYPE = "weekly_report.answers.integrate"
ACTIVE_FINAL_REPORT_STATUSES = {"draft", "approved", "stored"}
MUTABLE_ACTIVE_FINAL_REPORT_STATUSES = {"draft", "approved"}
CLOSED_SESSION_STATUSES = {"stored", "cancelled", "failed"}
FINAL_REPORT_PRIORITY = {"stored": 0, "approved": 1, "draft": 2, "superseded": 3}
MEMORY_CANDIDATE_KINDS = {
    "behavior_pattern",
    "blocker",
    "weekly_commitment",
    "preference",
    "operational_signal",
    "risk",
    "achievement",
}
MEMORY_CANDIDATE_SCOPES = {
    "user_profile",
    "operating_pattern",
    "weekly_review",
    "module_signal",
}
MEMORY_CANDIDATE_NOTE = "Memory candidates are proposals only. Nothing has been written to memory."
MEMORY_COMMIT_READY_NOTE = "Commit readiness only. Nothing has been written to memory."
MEMORY_COMMIT_DRY_RUN_NOTE = "Dry run only. Nothing has been written to memory."
WR_FINAL_CONFIRMATION_PROMPT = "As-tu autre chose à ajouter avant que je prépare le rapport final ?"


class WeeklyReviewConversationError(ValueError):
    pass


class InvalidWeekStartError(WeeklyReviewConversationError):
    pass


class WeeklyReviewSessionNotFoundError(WeeklyReviewConversationError):
    pass


class WeeklyReviewFinalReportNotFoundError(WeeklyReviewConversationError):
    pass


class WeeklyReviewStateConflictError(WeeklyReviewConversationError):
    pass


class WeeklyReviewIdempotencyConflictError(WeeklyReviewConversationError):
    pass


class WeeklyReviewAIResultConflictError(WeeklyReviewConversationError):
    pass


def get_or_create_weekly_review_session(
    db: Session,
    *,
    current_user: User,
    week_start: date,
) -> ImperiumWeeklyReviewSession:
    _validate_week_start(week_start)
    session = _get_session_by_week(db, current_user=current_user, week_start=week_start)
    if session is not None:
        return session

    session = ImperiumWeeklyReviewSession(
        user_id=current_user.id,
        week_start=week_start,
        week_end=week_end_for(week_start),
        status="ready",
    )
    db.add(session)
    db.flush()
    return session


def get_weekly_review_session(
    db: Session,
    *,
    current_user: User,
    week_start: date,
) -> ImperiumWeeklyReviewSession | None:
    _validate_week_start(week_start)
    return _get_session_by_week(db, current_user=current_user, week_start=week_start)


def launch_weekly_review_session(
    db: Session,
    *,
    current_user: User,
    week_start: date,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[WeeklyReviewSessionRead, bool]:
    _validate_week_start(week_start)
    request_hash = _hash_payload({"action": "weekly_review.launch", "week_start": week_start.isoformat()})
    existing_key = _get_existing_idempotency(db, user_id=current_user.id, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_idempotency(existing_key, request_hash, WeeklyReviewSessionRead, request_path=request_path), True

    created_ai_task: AITask | None = None
    session = get_or_create_weekly_review_session(db, current_user=current_user, week_start=week_start)
    if session.status in {"cancelled", "failed", "approved", "stored"}:
        raise WeeklyReviewStateConflictError("Weekly review session cannot be launched from its current state.")

    if session.launched_at is None:
        session.launched_at = datetime.now(UTC)
    if session.status == "ready":
        session.status = "preparing_initial_summary"
    if session.current_ai_task_id is None:
        ai_task = AITask(
            user_id=current_user.id,
            task_type="weekly_report.interactive.start",
            status="queued",
            source_module="imperium",
            input_payload={
                "week_start": week_start.isoformat(),
                "week_end": session.week_end.isoformat(),
            },
            privacy_level="medium",
        )
        db.add(ai_task)
        db.flush()
        session.current_ai_task_id = ai_task.id
        ai_task.prepared_payload = prepare_weekly_review_n8n_trigger_payload(session=session, ai_task=ai_task)
        created_ai_task = ai_task
    else:
        ai_task = db.get(AITask, session.current_ai_task_id)
        if ai_task is not None and ai_task.prepared_payload is None:
            ai_task.prepared_payload = prepare_weekly_review_n8n_trigger_payload(session=session, ai_task=ai_task)

    db.flush()
    response = WeeklyReviewSessionRead.model_validate(session)
    _store_idempotency(
        db,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=201,
        response=response,
    )
    db.commit()
    if created_ai_task is not None:
        settings = get_settings()
        _trigger_weekly_review_n8n_if_enabled(
            db,
            ai_task=created_ai_task,
            path=settings.wr_n8n_qwen_dry_run_webhook_path,
            idempotency_key_prefix="wr_n8n_trigger",
        )
    return response, False


def prepare_weekly_review_n8n_trigger_payload(
    *,
    session: ImperiumWeeklyReviewSession,
    ai_task: AITask,
) -> dict[str, str]:
    return {
        "task_id": str(ai_task.id),
        "session_id": str(session.id),
        "task_type": "weekly_report.interactive.start",
        "week_start": session.week_start.isoformat(),
        "week_end": session.week_end.isoformat(),
        "callback_url": f"/api/internal/ai/tasks/{ai_task.id}/result",
        "wr_attach_url": f"/api/internal/weekly-review/{session.id}/attach-ai-result",
    }


def prepare_weekly_review_answers_integrate_payload(
    *,
    session: ImperiumWeeklyReviewSession,
    message: ImperiumWeeklyReviewMessage,
    ai_task: AITask,
    trigger_type: str,
) -> dict[str, str | None]:
    return {
        "task_id": str(ai_task.id),
        "session_id": str(session.id),
        "task_type": ANSWER_INTEGRATION_TASK_TYPE,
        "source": "backend_wr_answer",
        "trigger_type": trigger_type,
        "source_ref_type": "weekly_review_session",
        "source_ref_id": str(session.id),
        "week_start": session.week_start.isoformat(),
        "week_end": session.week_end.isoformat(),
        "user_message_id": str(message.id),
        "user_answer": message.content,
        "latest_user_answer_message_id": str(message.id),
        "latest_initial_ai_result_id": str(session.initial_ai_result_id) if session.initial_ai_result_id else None,
        "callback_url": f"/api/internal/ai/tasks/{ai_task.id}/result",
        "wr_attach_url": f"/api/internal/weekly-review/{session.id}/attach-ai-result",
    }


def _trigger_weekly_review_n8n_if_enabled(
    db: Session,
    *,
    ai_task: AITask,
    path: str,
    idempotency_key_prefix: str,
) -> None:
    settings = get_settings()
    if settings.n8n_dry_run:
        return
    if not n8n_is_configured(settings):
        ai_task.error_code = "n8n_not_configured"
        ai_task.error_message = "N8N_BASE_URL and N8N_WEBHOOK_SECRET are required for outbound n8n trigger."
        db.commit()
        return
    try:
        trigger_n8n_webhook(
            path=path,
            payload=ai_task.prepared_payload or {},
            idempotency_key=f"{idempotency_key_prefix}_{ai_task.id}",
            settings=settings,
            dry_run=False,
        )
    except N8NConfigurationError as exc:
        ai_task.error_code = "n8n_not_configured"
        ai_task.error_message = str(exc)
        db.commit()
    except N8NRequestError as exc:
        ai_task.error_code = "n8n_trigger_failed"
        ai_task.error_message = str(exc)
        db.commit()


def add_user_message(
    db: Session,
    *,
    session_id: UUID,
    current_user: User,
    payload: WeeklyReviewAnswerRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
    create_integration_task: bool = False,
    trigger_type: str = "user_message",
) -> tuple[WeeklyReviewMessageRead, bool]:
    request_payload = payload.model_dump(mode="json")
    request_hash = _hash_payload({"action": "weekly_review.user_message", "session_id": str(session_id), **request_payload})
    existing_key = _get_existing_idempotency(db, user_id=current_user.id, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_idempotency(existing_key, request_hash, WeeklyReviewMessageRead, request_path=request_path), True

    created_ai_task: AITask | None = None
    session = _get_session_for_user(db, current_user=current_user, session_id=session_id)
    _ensure_session_open(session)
    message = _add_message(
        db,
        session=session,
        role="user",
        message_type="user_answer",
        content=payload.content,
        payload=payload.payload,
    )
    session.status = "integrating_answers"
    if create_integration_task:
        created_ai_task = _create_answer_integration_task(
            db,
            session=session,
            message=message,
            trigger_type=trigger_type,
        )
    db.flush()
    response = WeeklyReviewMessageRead.model_validate(message)
    _store_idempotency(
        db,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=201,
        response=response,
    )
    db.commit()
    if created_ai_task is not None:
        settings = get_settings()
        _trigger_weekly_review_n8n_if_enabled(
            db,
            ai_task=created_ai_task,
            path=settings.wr_n8n_answers_integrate_webhook_path,
            idempotency_key_prefix="wr_n8n_answers_integrate",
        )
    return response, False


def add_weekly_review_chat_message(
    db: Session,
    *,
    session_id: UUID,
    current_user: User,
    payload: WeeklyReviewAnswerRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[WeeklyReviewMessageRead, bool]:
    request_payload = payload.model_dump(mode="json")
    request_hash = _hash_payload({"action": "weekly_review.chat.message", "session_id": str(session_id), **request_payload})
    existing_key = _get_existing_idempotency(db, user_id=current_user.id, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_idempotency(existing_key, request_hash, WeeklyReviewMessageRead, request_path=request_path), True

    session = _get_session_for_user(db, current_user=current_user, session_id=session_id)
    _ensure_session_open(session)
    if session.status in {"draft_ready", "final_ready"}:
        raise WeeklyReviewStateConflictError("Request changes before adding more chat messages to a draft-ready weekly review.")
    content = payload.content.strip()
    if not content:
        raise WeeklyReviewStateConflictError("Weekly review chat message content is required.")
    message_payload = _chat_message_payload(payload.payload, source="imperium_weekly_review_chat")
    message = _add_message(
        db,
        session=session,
        role="user",
        message_type="chat_message",
        content=content,
        payload=message_payload,
    )
    _add_assistant_followup_message(db, session=session, user_content=content)
    session.status = "conversation_active"
    db.flush()
    response = WeeklyReviewMessageRead.model_validate(message)
    _store_idempotency(
        db,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=201,
        response=response,
    )
    db.commit()
    return response, False


def confirm_weekly_review_no_more_input(
    db: Session,
    *,
    session_id: UUID,
    current_user: User,
    payload: WeeklyReviewChatConfirmRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[WeeklyReviewSessionRead, bool]:
    request_payload = payload.model_dump(mode="json")
    request_hash = _hash_payload(
        {"action": "weekly_review.chat.confirm_no_more_input", "session_id": str(session_id), **request_payload}
    )
    existing_key = _get_existing_idempotency(db, user_id=current_user.id, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_idempotency(existing_key, request_hash, WeeklyReviewSessionRead, request_path=request_path), True

    session = _get_session_for_user(db, current_user=current_user, session_id=session_id)
    _ensure_session_open(session)
    if session.status in {"draft_ready", "final_ready"}:
        raise WeeklyReviewStateConflictError("Weekly review already has a draft candidate.")
    content = payload.content.strip() if payload.content else None
    if content:
        _add_message(
            db,
            session=session,
            role="user",
            message_type="chat_message",
            content=content,
            payload=_chat_message_payload(payload.payload, source="imperium_weekly_review_chat_confirm"),
        )
    elif not _session_has_user_input(db, session=session):
        raise WeeklyReviewStateConflictError("Cannot prepare a final draft without user-provided input.")

    ai_task, ai_result = _create_chat_final_draft_ai_result(
        db,
        session=session,
        content=content,
        payload=payload.payload,
    )
    _attach_final_report_candidate_from_ai_result(
        db,
        session=session,
        ai_result=ai_result,
        message_type_override="final_report_draft",
    )
    session.current_ai_task_id = ai_task.id if session.current_ai_task_id is None else session.current_ai_task_id
    session.status = "draft_ready"
    db.flush()
    response = WeeklyReviewSessionRead.model_validate(session)
    _store_idempotency(
        db,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=201,
        response=response,
    )
    db.commit()
    return response, False


def request_draft_changes(
    db: Session,
    *,
    session_id: UUID,
    current_user: User,
    payload: WeeklyReviewAnswerRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[WeeklyReviewMessageRead, bool]:
    request_payload = payload.model_dump(mode="json")
    request_hash = _hash_payload({"action": "weekly_review.draft.request_changes", "session_id": str(session_id), **request_payload})
    existing_key = _get_existing_idempotency(db, user_id=current_user.id, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_idempotency(existing_key, request_hash, WeeklyReviewMessageRead, request_path=request_path), True

    session = _get_session_for_user(db, current_user=current_user, session_id=session_id)
    _ensure_session_not_terminal(session)
    latest_report = _get_latest_mutable_report_for_changes(db, session=session, user_id=current_user.id)
    if latest_report is None:
        raise WeeklyReviewFinalReportNotFoundError("Weekly review draft or approved candidate not found.")

    latest_report.status = "superseded"
    latest_report.report_payload = {
        **(latest_report.report_payload or {}),
        "_revision_request": {
            "content": payload.content,
            "payload": payload.payload,
            "requested_at": datetime.now(UTC).isoformat(),
        },
    }
    message = _add_message(
        db,
        session=session,
        role="user",
        message_type="revision_request",
        content=payload.content,
        payload=_chat_message_payload(payload.payload, source="imperium_weekly_review_request_changes"),
    )
    _add_assistant_followup_message(db, session=session, user_content=payload.content)
    session.status = "conversation_active"
    db.flush()
    response = WeeklyReviewMessageRead.model_validate(message)
    _store_idempotency(
        db,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=201,
        response=response,
    )
    db.commit()
    return response, False


def _create_answer_integration_task(
    db: Session,
    *,
    session: ImperiumWeeklyReviewSession,
    message: ImperiumWeeklyReviewMessage,
    trigger_type: str,
) -> AITask:
    ai_task = AITask(
        user_id=session.user_id,
        task_type=ANSWER_INTEGRATION_TASK_TYPE,
        status="queued",
        source_module="imperium",
        input_payload={},
        privacy_level="medium",
    )
    db.add(ai_task)
    db.flush()
    payload = prepare_weekly_review_answers_integrate_payload(
        session=session,
        message=message,
        ai_task=ai_task,
        trigger_type=trigger_type,
    )
    ai_task.input_payload = payload
    ai_task.prepared_payload = payload
    if session.current_ai_task_id is None:
        session.current_ai_task_id = ai_task.id
    db.flush()
    return ai_task


def add_backend_or_qwen_message(
    db: Session,
    *,
    session_id: UUID,
    role: str,
    message_type: str,
    content: str | None = None,
    payload: dict | None = None,
    ai_task_id: UUID | None = None,
    ai_result_id: UUID | None = None,
) -> ImperiumWeeklyReviewMessage:
    session = db.get(ImperiumWeeklyReviewSession, session_id)
    if session is None:
        raise WeeklyReviewSessionNotFoundError("Weekly review session not found.")
    _ensure_ai_attach_session_open(session)
    message = _add_message(
        db,
        session=session,
        role=role,
        message_type=message_type,
        content=content,
        payload=payload,
        ai_task_id=ai_task_id,
        ai_result_id=ai_result_id,
    )
    db.commit()
    db.refresh(message)
    return message


def attach_initial_ai_result(
    db: Session,
    *,
    session_id: UUID,
    ai_result_id: UUID,
) -> ImperiumWeeklyReviewSession:
    session = db.get(ImperiumWeeklyReviewSession, session_id)
    if session is None:
        raise WeeklyReviewSessionNotFoundError("Weekly review session not found.")
    _ensure_ai_attach_session_open(session)
    ai_result = db.get(AIResult, ai_result_id)
    if ai_result is None or ai_result.user_id != session.user_id:
        raise WeeklyReviewAIResultConflictError("AI result does not belong to this weekly review user.")
    if ai_result.result_type not in COMPATIBLE_AI_RESULT_TYPES:
        raise WeeklyReviewAIResultConflictError("AI result type is not compatible with weekly review.")
    if ai_result.result_type == "weekly_report.summary" and session.initial_ai_result_id is not None:
        if session.initial_ai_result_id == ai_result.id:
            return session
        raise WeeklyReviewAIResultConflictError("Weekly review initial summary is already attached.")
    if ai_result.result_type in {"weekly_report.draft", "weekly_report.final"}:
        return _attach_final_report_candidate_from_ai_result(db, session=session, ai_result=ai_result)

    role = _role_for_ai_result(ai_result)
    message_type = _message_type_for_ai_result(ai_result)
    _add_message(
        db,
        session=session,
        role=role,
        message_type=message_type,
        content=None,
        payload=ai_result.result_payload,
        ai_result_id=ai_result.id,
    )
    if ai_result.result_type == "weekly_report.summary":
        session.initial_ai_result_id = ai_result.id
        session.status = "initial_summary_ready"
    elif ai_result.result_type == "weekly_report.questions":
        session.status = "waiting_for_user_answer"
    elif ai_result.result_type in {"weekly_report.draft", "weekly_report.revision"}:
        session.status = "draft_ready"
    elif ai_result.result_type == "weekly_report.final":
        session.final_ai_result_id = ai_result.id
        session.status = "final_ready"
    db.flush()
    return session


def _attach_final_report_candidate_from_ai_result(
    db: Session,
    *,
    session: ImperiumWeeklyReviewSession,
    ai_result: AIResult,
    message_type_override: str | None = None,
) -> ImperiumWeeklyReviewSession:
    reports = list(
        db.scalars(
            select(ImperiumWeeklyReviewFinalReport)
            .where(ImperiumWeeklyReviewFinalReport.session_id == session.id)
            .order_by(ImperiumWeeklyReviewFinalReport.created_at.desc())
        )
    )
    same_result_report = next((report for report in reports if report.source_ai_result_id == ai_result.id), None)
    if same_result_report is not None:
        if same_result_report.status in ACTIVE_FINAL_REPORT_STATUSES:
            if ai_result.result_type == "weekly_report.final":
                session.final_ai_result_id = ai_result.id
                session.status = "final_ready"
            else:
                session.status = "draft_ready"
        return session

    active_report = next((report for report in reports if report.status in ACTIVE_FINAL_REPORT_STATUSES), None)
    if active_report is not None:
        raise WeeklyReviewAIResultConflictError("Weekly review final candidate is already attached.")

    report_payload, report_markdown, memory_candidates = _report_candidate_fields_from_ai_result(ai_result)
    report = ImperiumWeeklyReviewFinalReport(
        session_id=session.id,
        user_id=session.user_id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="draft",
        report_payload=report_payload,
        report_markdown=report_markdown,
        memory_candidates=memory_candidates,
        source_ai_result_id=ai_result.id,
    )
    db.add(report)
    _add_message(
        db,
        session=session,
        role=_role_for_ai_result(ai_result),
        message_type=message_type_override or _message_type_for_ai_result(ai_result),
        content=report_markdown,
        payload=report_payload,
        ai_result_id=ai_result.id,
    )
    if ai_result.result_type == "weekly_report.final":
        session.final_ai_result_id = ai_result.id
        session.status = "final_ready"
    else:
        session.status = "draft_ready"
    db.flush()
    return session


def _report_candidate_fields_from_ai_result(ai_result: AIResult) -> tuple[dict, str, dict | list | None]:
    payload = ai_result.result_payload or {}
    report_payload = payload.get("report_payload") if isinstance(payload.get("report_payload"), dict) else payload
    report_markdown = _markdown_from_ai_result_payload(payload)
    memory_candidates = payload.get("memory_candidates")
    if not isinstance(memory_candidates, (dict, list)):
        memory_candidates = None
    return report_payload, report_markdown, memory_candidates


def _markdown_from_ai_result_payload(payload: dict) -> str:
    for key in ("report_markdown", "markdown", "final_markdown", "draft_markdown"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    summary = payload.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary
    return json.dumps(payload, sort_keys=True, indent=2, default=str)


def attach_ai_result_to_session(
    db: Session,
    *,
    session_id: UUID,
    payload: WeeklyReviewAttachAIResultRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[WeeklyReviewSessionRead, bool]:
    session = db.get(ImperiumWeeklyReviewSession, session_id)
    if session is None:
        raise WeeklyReviewSessionNotFoundError("Weekly review session not found.")
    request_hash = _hash_payload(
        {
            "action": "weekly_review.attach_ai_result",
            "session_id": str(session_id),
            "ai_result_id": str(payload.ai_result_id),
        }
    )
    existing_key = _get_existing_idempotency(db, user_id=session.user_id, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_idempotency(existing_key, request_hash, WeeklyReviewSessionRead, request_path=request_path), True

    session = attach_initial_ai_result(db, session_id=session_id, ai_result_id=payload.ai_result_id)
    response = WeeklyReviewSessionRead.model_validate(session)
    _store_idempotency(
        db,
        user_id=session.user_id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=200,
        response=response,
    )
    db.commit()
    return response, False


def mock_weekly_review_summary(
    db: Session,
    *,
    session_id: UUID,
    payload: AIResultCallback,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[WeeklyReviewSessionRead, bool]:
    if payload.result_type != "weekly_report.summary":
        raise WeeklyReviewAIResultConflictError("Mock weekly review summary must use result_type weekly_report.summary.")
    session = db.get(ImperiumWeeklyReviewSession, session_id)
    if session is None:
        raise WeeklyReviewSessionNotFoundError("Weekly review session not found.")
    _ensure_ai_attach_session_open(session)
    if session.current_ai_task_id is None:
        ai_task = AITask(
            user_id=session.user_id,
            task_type="weekly_report.interactive.start",
            status="queued",
            source_module="imperium",
            input_payload={
                "week_start": session.week_start.isoformat(),
                "week_end": session.week_end.isoformat(),
            },
            privacy_level="medium",
        )
        db.add(ai_task)
        db.flush()
        session.current_ai_task_id = ai_task.id
        ai_task.prepared_payload = prepare_weekly_review_n8n_trigger_payload(session=session, ai_task=ai_task)
        db.commit()

    ai_result, _result_duplicate = receive_ai_result(
        db,
        task_id=session.current_ai_task_id,
        payload=payload,
        idempotency_key=f"{idempotency_key}:ai-result",
    )
    return attach_ai_result_to_session(
        db,
        session_id=session_id,
        payload=WeeklyReviewAttachAIResultRequest(ai_result_id=ai_result.id),
        idempotency_key=f"{idempotency_key}:wr-attach",
        request_method=request_method,
        request_path=request_path,
    )


def request_revision(
    db: Session,
    *,
    session_id: UUID,
    current_user: User,
    payload: WeeklyReviewRevisionRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[WeeklyReviewMessageRead, bool]:
    request_payload = payload.model_dump(mode="json")
    request_hash = _hash_payload({"action": "weekly_review.revision_request", "session_id": str(session_id), **request_payload})
    existing_key = _get_existing_idempotency(db, user_id=current_user.id, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_idempotency(existing_key, request_hash, WeeklyReviewMessageRead, request_path=request_path), True

    session = _get_session_for_user(db, current_user=current_user, session_id=session_id)
    _ensure_session_open(session)
    message = _add_message(
        db,
        session=session,
        role="user",
        message_type="revision_request",
        content=payload.feedback,
        payload=payload.payload,
    )
    session.status = "revision_requested"
    db.flush()
    response = WeeklyReviewMessageRead.model_validate(message)
    _store_idempotency(
        db,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=201,
        response=response,
    )
    db.commit()
    return response, False


def create_or_update_final_draft(
    db: Session,
    *,
    session_id: UUID,
    current_user: User,
    payload: WeeklyReviewDraftCreate,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[WeeklyReviewDraftRead, bool]:
    request_payload = payload.model_dump(mode="json")
    request_hash = _hash_payload({"action": "weekly_review.final_draft", "session_id": str(session_id), **request_payload})
    existing_key = _get_existing_idempotency(db, user_id=current_user.id, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_idempotency(existing_key, request_hash, WeeklyReviewDraftRead, request_path=request_path), True

    session = _get_session_for_user(db, current_user=current_user, session_id=session_id)
    _ensure_session_open(session)
    if payload.ai_result_id is not None:
        ai_result = db.get(AIResult, payload.ai_result_id)
        if ai_result is None or ai_result.user_id != current_user.id:
            raise WeeklyReviewAIResultConflictError("AI result does not belong to this user.")
        if ai_result.result_type not in {"weekly_report.draft", "weekly_report.final", "weekly_report.revision"}:
            raise WeeklyReviewAIResultConflictError("AI result type is not compatible with a weekly review final draft.")
        if ai_result.result_type == "weekly_report.final":
            session.final_ai_result_id = ai_result.id
        target_status = "draft_ready" if ai_result.result_type in {"weekly_report.draft", "weekly_report.revision"} else "final_ready"
    else:
        target_status = "final_ready"

    reports = list(
        db.scalars(
            select(ImperiumWeeklyReviewFinalReport)
            .where(ImperiumWeeklyReviewFinalReport.session_id == session.id)
            .order_by(ImperiumWeeklyReviewFinalReport.created_at.desc())
        )
    )
    same_result_report = (
        next((candidate for candidate in reports if candidate.source_ai_result_id == payload.ai_result_id), None)
        if payload.ai_result_id is not None
        else None
    )
    active_report = next((candidate for candidate in reports if candidate.status in ACTIVE_FINAL_REPORT_STATUSES), None)
    report = same_result_report or active_report
    if report is None:
        report = ImperiumWeeklyReviewFinalReport(
            session_id=session.id,
            user_id=current_user.id,
            week_start=session.week_start,
            week_end=session.week_end,
            status="draft",
            report_payload=payload.report_payload,
            report_markdown=payload.report_markdown,
            memory_candidates=payload.memory_candidates,
            source_ai_result_id=payload.ai_result_id,
        )
        db.add(report)
    elif report.status in {"approved", "stored"}:
        raise WeeklyReviewStateConflictError("Approved or stored final report cannot be overwritten.")
    elif report.status == "superseded":
        raise WeeklyReviewStateConflictError("Superseded final report cannot be overwritten.")
    else:
        report.status = "draft"
        report.report_payload = payload.report_payload
        report.report_markdown = payload.report_markdown
        report.memory_candidates = payload.memory_candidates
        report.source_ai_result_id = payload.ai_result_id

    _add_message(
        db,
        session=session,
        role="backend",
        message_type="final_report",
        content=payload.report_markdown,
        payload=payload.report_payload,
        ai_result_id=payload.ai_result_id,
    )
    session.status = target_status
    db.flush()
    response = WeeklyReviewDraftRead.model_validate(report)
    _store_idempotency(
        db,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=201,
        response=response,
    )
    db.commit()
    return response, False


def approve_final_report(
    db: Session,
    *,
    session_id: UUID,
    current_user: User,
    payload: WeeklyReviewFinalApproveRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[WeeklyReviewFinalReportRead, bool]:
    request_payload = payload.model_dump(mode="json")
    request_hash = _hash_payload({"action": "weekly_review.approve", "session_id": str(session_id), **request_payload})
    existing_key = _get_existing_idempotency(db, user_id=current_user.id, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_idempotency(existing_key, request_hash, WeeklyReviewFinalReportRead, request_path=request_path), True

    session = _get_session_for_user(db, current_user=current_user, session_id=session_id)
    report = db.get(ImperiumWeeklyReviewFinalReport, payload.final_report_id)
    if report is None or report.session_id != session.id or report.user_id != current_user.id:
        raise WeeklyReviewFinalReportNotFoundError("Weekly review final report not found.")
    _ensure_session_not_terminal(session)
    if report.status == "draft":
        now = datetime.now(UTC)
        report.status = "approved"
        report.approved_at = now
        session.status = "approved"
        session.completed_at = now
    elif report.status == "stored":
        raise WeeklyReviewStateConflictError("Stored final report cannot be approved again.")
    elif report.status != "approved":
        raise WeeklyReviewStateConflictError("Final report cannot be approved from its current state.")

    db.flush()
    response = WeeklyReviewFinalReportRead.model_validate(report)
    _store_idempotency(
        db,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=200,
        response=response,
    )
    db.commit()
    return response, False


def approve_latest_draft_report(
    db: Session,
    *,
    session_id: UUID,
    current_user: User,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[WeeklyReviewFinalReportRead, bool]:
    request_hash = _hash_payload({"action": "weekly_review.draft.approve", "session_id": str(session_id)})
    existing_key = _get_existing_idempotency(db, user_id=current_user.id, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_idempotency(existing_key, request_hash, WeeklyReviewFinalReportRead, request_path=request_path), True

    session = _get_session_for_user(db, current_user=current_user, session_id=session_id)
    _ensure_session_not_terminal(session)
    report = _get_latest_active_draft_report(db, session=session, user_id=current_user.id)
    if report is None:
        raise WeeklyReviewFinalReportNotFoundError("Weekly review draft candidate not found.")

    now = datetime.now(UTC)
    report.status = "approved"
    report.approved_at = now
    session.status = "approved"
    session.completed_at = now
    db.flush()
    response = WeeklyReviewFinalReportRead.model_validate(report)
    _store_idempotency(
        db,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=200,
        response=response,
    )
    db.commit()
    return response, False


def store_approved_final_report(
    db: Session,
    *,
    session_id: UUID,
    current_user: User,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[WeeklyReviewFinalReportRead, bool]:
    request_hash = _hash_payload({"action": "weekly_review.draft.store", "session_id": str(session_id)})
    existing_key = _get_existing_idempotency(db, user_id=current_user.id, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_idempotency(existing_key, request_hash, WeeklyReviewFinalReportRead, request_path=request_path), True

    session = _get_session_for_user(db, current_user=current_user, session_id=session_id)
    _ensure_session_not_terminal(session)
    report = _get_latest_active_final_report(db, session=session, user_id=current_user.id)
    if report is None:
        raise WeeklyReviewFinalReportNotFoundError("Weekly review final report candidate not found.")
    if report.status == "stored" or report.stored_at is not None:
        raise WeeklyReviewStateConflictError("Weekly review final report is already stored.")
    if report.status != "approved":
        raise WeeklyReviewStateConflictError("Weekly review final report must be approved before storage.")

    now = datetime.now(UTC)
    report.status = "stored"
    report.stored_at = now
    session.status = "stored"
    if session.completed_at is None:
        session.completed_at = now
    db.flush()
    response = WeeklyReviewFinalReportRead.model_validate(report)
    _store_idempotency(
        db,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=200,
        response=response,
    )
    db.commit()
    return response, False


def reject_latest_draft_report(
    db: Session,
    *,
    session_id: UUID,
    current_user: User,
    payload: WeeklyReviewDraftRejectRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[WeeklyReviewFinalReportRead, bool]:
    request_payload = payload.model_dump(mode="json")
    request_hash = _hash_payload({"action": "weekly_review.draft.reject", "session_id": str(session_id), **request_payload})
    existing_key = _get_existing_idempotency(db, user_id=current_user.id, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_idempotency(existing_key, request_hash, WeeklyReviewFinalReportRead, request_path=request_path), True

    session = _get_session_for_user(db, current_user=current_user, session_id=session_id)
    _ensure_session_open(session)
    report = _get_latest_active_draft_report(db, session=session, user_id=current_user.id)
    if report is None:
        raise WeeklyReviewFinalReportNotFoundError("Weekly review draft candidate not found.")

    now = datetime.now(UTC)
    report.status = "superseded"
    report.report_payload = {
        **(report.report_payload or {}),
        "_rejection": {
            "reason": payload.reason,
            "payload": payload.payload,
            "rejected_at": now.isoformat(),
        },
    }
    _add_message(
        db,
        session=session,
        role="user",
        message_type="revision_request",
        content=payload.reason or "Draft rejected.",
        payload={"action": "draft_rejected", "reason": payload.reason, "payload": payload.payload},
    )
    session.status = "initial_summary_ready" if session.initial_ai_result_id else "waiting_for_user_answer"
    db.flush()
    response = WeeklyReviewFinalReportRead.model_validate(report)
    _store_idempotency(
        db,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=200,
        response=response,
    )
    db.commit()
    return response, False


def cancel_weekly_review(
    db: Session,
    *,
    session_id: UUID,
    current_user: User,
    payload: WeeklyReviewCancelRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[WeeklyReviewSessionRead, bool]:
    request_hash = _hash_payload(
        {
            "action": "weekly_review.cancel",
            "session_id": str(session_id),
            "reason": payload.reason,
        }
    )
    existing_key = _get_existing_idempotency(db, user_id=current_user.id, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_idempotency(existing_key, request_hash, WeeklyReviewSessionRead, request_path=request_path), True

    session = _get_session_for_user(db, current_user=current_user, session_id=session_id)
    if session.status in {"approved", "stored"}:
        raise WeeklyReviewStateConflictError("Approved or stored weekly review cannot be cancelled.")
    session.status = "cancelled"
    session.completed_at = datetime.now(UTC)
    _add_message(
        db,
        session=session,
        role="user",
        message_type="system_note",
        content=payload.reason,
        payload={"reason": payload.reason},
    )
    db.flush()
    response = WeeklyReviewSessionRead.model_validate(session)
    _store_idempotency(
        db,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=200,
        response=response,
    )
    db.commit()
    return response, False


def fail_weekly_review(
    db: Session,
    *,
    session_id: UUID,
    error_code: str,
    error_message: str,
) -> ImperiumWeeklyReviewSession:
    session = db.get(ImperiumWeeklyReviewSession, session_id)
    if session is None:
        raise WeeklyReviewSessionNotFoundError("Weekly review session not found.")
    session.status = "failed"
    session.failed_at = datetime.now(UTC)
    session.error_code = error_code
    session.error_message = error_message
    db.commit()
    db.refresh(session)
    return session


def get_weekly_review_messages(
    db: Session,
    *,
    current_user: User,
    session_id: UUID,
) -> list[ImperiumWeeklyReviewMessage]:
    session = _get_session_for_user(db, current_user=current_user, session_id=session_id)
    return list(
        db.scalars(
            select(ImperiumWeeklyReviewMessage)
            .where(ImperiumWeeklyReviewMessage.session_id == session.id)
            .order_by(ImperiumWeeklyReviewMessage.created_at.asc())
        )
    )


def get_weekly_review_conversation(
    db: Session,
    *,
    current_user: User,
    session_id: UUID,
    messages_limit: int = 200,
    messages_before: datetime | None = None,
    final_reports_limit: int = 5,
) -> WeeklyReviewConversationRead:
    messages_limit = max(1, min(messages_limit, 500))
    final_reports_limit = max(1, min(final_reports_limit, 20))
    session = _get_session_for_user(db, current_user=current_user, session_id=session_id)
    message_query = select(ImperiumWeeklyReviewMessage).where(ImperiumWeeklyReviewMessage.session_id == session.id)
    if messages_before is not None:
        message_query = message_query.where(ImperiumWeeklyReviewMessage.created_at < messages_before)
    message_query = message_query.order_by(ImperiumWeeklyReviewMessage.created_at.desc()).limit(messages_limit)
    messages = list(
        db.scalars(message_query)
    )
    if messages_before is not None:
        messages = [message for message in messages if message.created_at < messages_before]
    messages = sorted(messages, key=lambda message: message.created_at, reverse=True)[:messages_limit]
    messages.reverse()
    reports = list(
        db.scalars(
            select(ImperiumWeeklyReviewFinalReport)
            .where(
                ImperiumWeeklyReviewFinalReport.session_id == session.id,
                ImperiumWeeklyReviewFinalReport.user_id == current_user.id,
            )
            .order_by(ImperiumWeeklyReviewFinalReport.created_at.desc())
            .limit(final_reports_limit)
        )
    )
    reports = sorted(reports, key=lambda report: report.created_at, reverse=True)[:final_reports_limit]
    current_ai_task = db.get(AITask, session.current_ai_task_id) if session.current_ai_task_id else None
    initial_ai_result = db.get(AIResult, session.initial_ai_result_id) if session.initial_ai_result_id else None
    final_ai_result = db.get(AIResult, session.final_ai_result_id) if session.final_ai_result_id else None
    latest_final_report = reports[0] if reports else None
    active_final_report = _select_active_report_for_read(
        db,
        session=session,
        user_id=current_user.id,
        reports=reports,
    )
    flags = _build_conversation_flags(session=session, active_final_report=active_final_report)
    ui_state = _conversation_ui_state(session=session, active_final_report=active_final_report)
    allowed_actions = _conversation_allowed_actions(ui_state=ui_state, flags=flags)
    draft_review_state = _draft_review_state(
        session=session,
        active_final_report=active_final_report,
        latest_final_report=latest_final_report,
    )
    chat_timeline = _build_chat_timeline(messages=messages, reports=reports)
    latest_assistant_prompt = _latest_assistant_prompt(messages)
    visible_ai_state = _visible_ai_state(
        session=session,
        ui_state=ui_state,
        initial_ai_result=initial_ai_result,
        active_final_report=active_final_report,
        latest_final_report=latest_final_report,
        latest_assistant_prompt=latest_assistant_prompt,
    )
    primary_action, secondary_actions = _conversation_action_descriptors(
        session_id=session.id,
        ui_state=ui_state,
        flags=flags,
        allowed_actions=allowed_actions,
    )

    return WeeklyReviewConversationRead(
        session=WeeklyReviewSessionRead.model_validate(session),
        messages=[WeeklyReviewMessageRead.model_validate(message) for message in messages],
        current_ai_task=WeeklyReviewAITaskSummary.model_validate(current_ai_task) if current_ai_task else None,
        initial_ai_result=WeeklyReviewAIResultSummary.model_validate(initial_ai_result) if initial_ai_result else None,
        final_ai_result=WeeklyReviewAIResultSummary.model_validate(final_ai_result) if final_ai_result else None,
        final_reports=[WeeklyReviewFinalReportRead.model_validate(report) for report in reports],
        final_report_candidates=[WeeklyReviewFinalReportRead.model_validate(report) for report in reports],
        latest_final_report=WeeklyReviewFinalReportRead.model_validate(latest_final_report) if latest_final_report else None,
        flags=flags,
        allowed_actions=allowed_actions,
        ui_state=ui_state,
        chat_timeline=chat_timeline,
        visible_ai_state=visible_ai_state,
        latest_assistant_prompt=latest_assistant_prompt,
        draft_review_state=draft_review_state,
        primary_action=primary_action,
        secondary_actions=secondary_actions,
    )


def get_current_weekly_review(
    db: Session,
    *,
    current_user: User,
    week_start: date | None = None,
    messages_limit: int = 200,
    final_reports_limit: int = 5,
) -> WeeklyReviewCurrentResponse:
    if week_start is not None:
        _validate_week_start(week_start)
        session = _get_session_by_week(db, current_user=current_user, week_start=week_start)
    else:
        session = db.scalar(
            select(ImperiumWeeklyReviewSession)
            .where(ImperiumWeeklyReviewSession.user_id == current_user.id)
            .order_by(ImperiumWeeklyReviewSession.created_at.desc())
        )
    if session is not None and session.user_id != current_user.id:
        session = None
    if session is None:
        return WeeklyReviewCurrentResponse()
    return WeeklyReviewCurrentResponse(
        session=WeeklyReviewSessionRead.model_validate(session),
        conversation=get_weekly_review_conversation(
            db,
            current_user=current_user,
            session_id=session.id,
            messages_limit=messages_limit,
            final_reports_limit=final_reports_limit,
        ),
    )


def get_weekly_review_history(
    db: Session,
    *,
    current_user: User,
    limit: int = 20,
    offset: int = 0,
    status: str | None = None,
    stored_only: bool = False,
) -> WeeklyReviewHistoryResponse:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    query = select(ImperiumWeeklyReviewSession).where(ImperiumWeeklyReviewSession.user_id == current_user.id)
    if status:
        query = query.where(ImperiumWeeklyReviewSession.status == status)
    if stored_only:
        query = query.where(
            select(ImperiumWeeklyReviewFinalReport.id)
            .where(
                ImperiumWeeklyReviewFinalReport.session_id == ImperiumWeeklyReviewSession.id,
                ImperiumWeeklyReviewFinalReport.user_id == current_user.id,
                ImperiumWeeklyReviewFinalReport.status == "stored",
            )
            .exists()
        )
    query = query.order_by(ImperiumWeeklyReviewSession.created_at.desc()).offset(offset).limit(limit + 1)
    sessions = [session for session in db.scalars(query) if session.user_id == current_user.id]
    if status:
        sessions = [session for session in sessions if session.status == status]

    items: list[WeeklyReviewHistoryItem] = []
    has_more = len(sessions) > limit
    for session in sessions:
        reports = _get_reports_for_session(db, session=session, user_id=current_user.id)
        if stored_only and not any(report.status == "stored" for report in reports):
            continue
        items.append(_history_item_for_session(session=session, reports=reports))
        if len(items) >= limit:
            break

    return WeeklyReviewHistoryResponse(
        items=items,
        limit=limit,
        offset=offset,
        count=len(items),
        has_more=has_more,
    )


def get_weekly_review_final_report(
    db: Session,
    *,
    current_user: User,
    session_id: UUID,
) -> WeeklyReviewFinalReportRead:
    session = _get_session_for_user(db, current_user=current_user, session_id=session_id)
    report = _get_latest_relevant_final_report(db, session=session, user_id=current_user.id)
    if report is None:
        raise WeeklyReviewFinalReportNotFoundError("Weekly review final report not found.")
    return _final_report_read(report)


def get_weekly_review_final_report_by_id(
    db: Session,
    *,
    current_user: User,
    report_id: UUID,
) -> WeeklyReviewFinalReportRead:
    report = db.get(ImperiumWeeklyReviewFinalReport, report_id)
    if report is None or report.user_id != current_user.id:
        raise WeeklyReviewFinalReportNotFoundError("Weekly review final report not found.")
    return _final_report_read(report)


def get_stored_weekly_review_final_reports(
    db: Session,
    *,
    current_user: User,
    limit: int = 20,
    offset: int = 0,
) -> WeeklyReviewStoredFinalReportsResponse:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    reports = list(
        db.scalars(
            select(ImperiumWeeklyReviewFinalReport)
            .where(
                ImperiumWeeklyReviewFinalReport.user_id == current_user.id,
                ImperiumWeeklyReviewFinalReport.status == "stored",
            )
            .order_by(
                ImperiumWeeklyReviewFinalReport.stored_at.desc().nullslast(),
                ImperiumWeeklyReviewFinalReport.created_at.desc(),
            )
            .offset(offset)
            .limit(limit + 1)
        )
    )
    reports = [
        report
        for report in reports
        if report.user_id == current_user.id and report.status == "stored"
    ]
    reports = sorted(
        reports,
        key=lambda report: (
            report.stored_at or datetime.min.replace(tzinfo=UTC),
            report.created_at or datetime.min.replace(tzinfo=UTC),
        ),
        reverse=True,
    )
    has_more = len(reports) > limit
    items = reports[:limit]
    return WeeklyReviewStoredFinalReportsResponse(
        items=[_stored_final_report_summary(report) for report in items],
        limit=limit,
        offset=offset,
        count=len(items),
        has_more=has_more,
    )


def get_weekly_review_memory_candidates(
    db: Session,
    *,
    current_user: User,
    session_id: UUID,
) -> WeeklyReviewMemoryCandidatesResponse:
    session = _get_session_for_user(db, current_user=current_user, session_id=session_id)
    report = _get_latest_relevant_final_report(db, session=session, user_id=current_user.id)
    if report is None:
        raise WeeklyReviewFinalReportNotFoundError("Weekly review final report not found.")
    return _memory_candidates_response(
        report=report,
        session=session,
        decisions=_get_memory_candidate_decisions_for_report(db, report_id=report.id, user_id=current_user.id),
    )


def get_weekly_review_memory_candidates_by_report_id(
    db: Session,
    *,
    current_user: User,
    report_id: UUID,
) -> WeeklyReviewMemoryCandidatesResponse:
    report = db.get(ImperiumWeeklyReviewFinalReport, report_id)
    if report is None or report.user_id != current_user.id:
        raise WeeklyReviewFinalReportNotFoundError("Weekly review final report not found.")
    session = db.get(ImperiumWeeklyReviewSession, report.session_id)
    if session is not None and session.user_id != current_user.id:
        raise WeeklyReviewFinalReportNotFoundError("Weekly review final report not found.")
    return _memory_candidates_response(
        report=report,
        session=session,
        decisions=_get_memory_candidate_decisions_for_report(db, report_id=report.id, user_id=current_user.id),
    )


def get_weekly_review_memory_candidates_preview(
    db: Session,
    *,
    current_user: User,
    limit: int = 20,
    offset: int = 0,
    include_rejected: bool = False,
) -> WeeklyReviewMemoryCandidatesPreviewResponse:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    reports = list(
        db.scalars(
            select(ImperiumWeeklyReviewFinalReport)
            .where(
                ImperiumWeeklyReviewFinalReport.user_id == current_user.id,
                ImperiumWeeklyReviewFinalReport.status == "stored",
            )
            .order_by(
                ImperiumWeeklyReviewFinalReport.stored_at.desc().nullslast(),
                ImperiumWeeklyReviewFinalReport.created_at.desc(),
            )
            .offset(offset)
            .limit(limit + 1)
        )
    )
    reports = [
        report
        for report in reports
        if report.user_id == current_user.id and report.status == "stored"
    ]
    reports = sorted(
        reports,
        key=lambda report: (
            report.stored_at or datetime.min.replace(tzinfo=UTC),
            report.created_at or datetime.min.replace(tzinfo=UTC),
        ),
        reverse=True,
    )
    has_more = len(reports) > limit
    items = [
        _memory_candidates_response(
            report=report,
            session=db.get(ImperiumWeeklyReviewSession, report.session_id),
            decisions=_get_memory_candidate_decisions_for_report(db, report_id=report.id, user_id=current_user.id),
            include_rejected=include_rejected,
        )
        for report in reports[:limit]
    ]
    return WeeklyReviewMemoryCandidatesPreviewResponse(
        items=items,
        limit=limit,
        offset=offset,
        count=len(items),
        has_more=has_more,
    )


def approve_weekly_review_memory_candidate(
    db: Session,
    *,
    current_user: User,
    report_id: UUID,
    candidate_id: str,
    payload: WeeklyReviewMemoryCandidateApproveRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[WeeklyReviewMemoryCandidateDecisionRead, bool]:
    return _decide_weekly_review_memory_candidate(
        db,
        current_user=current_user,
        report_id=report_id,
        candidate_id=candidate_id,
        decision="approved",
        reason=payload.reason,
        payload=payload.payload,
        edited_candidate=None,
        request_payload=payload.model_dump(mode="json"),
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
    )


def reject_weekly_review_memory_candidate(
    db: Session,
    *,
    current_user: User,
    report_id: UUID,
    candidate_id: str,
    payload: WeeklyReviewMemoryCandidateRejectRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[WeeklyReviewMemoryCandidateDecisionRead, bool]:
    return _decide_weekly_review_memory_candidate(
        db,
        current_user=current_user,
        report_id=report_id,
        candidate_id=candidate_id,
        decision="rejected",
        reason=payload.reason,
        payload=payload.payload,
        edited_candidate=None,
        request_payload=payload.model_dump(mode="json"),
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
    )


def edit_weekly_review_memory_candidate(
    db: Session,
    *,
    current_user: User,
    report_id: UUID,
    candidate_id: str,
    payload: WeeklyReviewMemoryCandidateEditRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[WeeklyReviewMemoryCandidateDecisionRead, bool]:
    request_payload = payload.model_dump(mode="json")
    edited_candidate_patch = {
        "title": payload.edited_title,
        "content": payload.edited_content,
        "kind": payload.edited_kind,
        "confidence": payload.edited_confidence,
    }
    return _decide_weekly_review_memory_candidate(
        db,
        current_user=current_user,
        report_id=report_id,
        candidate_id=candidate_id,
        decision="edited",
        reason=payload.reason,
        payload=payload.payload,
        edited_candidate=edited_candidate_patch,
        request_payload=request_payload,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
    )


def get_weekly_review_memory_candidate_decisions(
    db: Session,
    *,
    current_user: User,
    limit: int = 20,
    offset: int = 0,
    decision: str | None = None,
) -> WeeklyReviewMemoryCandidateDecisionsResponse:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    query = select(ImperiumMemoryCandidateDecision).where(
        ImperiumMemoryCandidateDecision.user_id == current_user.id,
    )
    if decision:
        query = query.where(ImperiumMemoryCandidateDecision.decision == decision)
    query = query.order_by(ImperiumMemoryCandidateDecision.created_at.desc()).offset(offset).limit(limit + 1)
    decisions = [
        item
        for item in db.scalars(query)
        if item.user_id == current_user.id and (decision is None or item.decision == decision)
    ]
    decisions = sorted(
        decisions,
        key=lambda item: item.created_at or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )
    has_more = len(decisions) > limit
    items = decisions[:limit]
    return WeeklyReviewMemoryCandidateDecisionsResponse(
        items=[_decision_read(item) for item in items],
        limit=limit,
        offset=offset,
        count=len(items),
        has_more=has_more,
    )


def get_weekly_review_memory_commit_ready_candidates(
    db: Session,
    *,
    current_user: User,
    limit: int = 20,
    offset: int = 0,
) -> WeeklyReviewMemoryCommitPreviewRead:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    decisions = list(
        db.scalars(
            select(ImperiumMemoryCandidateDecision)
            .where(
                ImperiumMemoryCandidateDecision.user_id == current_user.id,
                ImperiumMemoryCandidateDecision.decision.in_(("approved", "edited")),
            )
            .order_by(ImperiumMemoryCandidateDecision.created_at.desc())
            .offset(offset)
            .limit(limit + 1)
        )
    )
    decisions = _sorted_commit_eligible_decisions(decisions, user_id=current_user.id)
    has_more = len(decisions) > limit
    items = [_commit_candidate_read(decision) for decision in decisions[:limit]]
    return WeeklyReviewMemoryCommitPreviewRead(
        items=items,
        limit=limit,
        offset=offset,
        count=len(items),
        has_more=has_more,
        storage_enabled=False,
        note=MEMORY_COMMIT_READY_NOTE,
    )


def get_weekly_review_memory_commit_ready_candidates_by_report_id(
    db: Session,
    *,
    current_user: User,
    report_id: UUID,
    limit: int = 100,
    offset: int = 0,
) -> WeeklyReviewMemoryCommitPreviewRead:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    report = db.get(ImperiumWeeklyReviewFinalReport, report_id)
    if report is None or report.user_id != current_user.id:
        raise WeeklyReviewFinalReportNotFoundError("Weekly review final report not found.")
    decisions = list(
        db.scalars(
            select(ImperiumMemoryCandidateDecision)
            .where(
                ImperiumMemoryCandidateDecision.user_id == current_user.id,
                ImperiumMemoryCandidateDecision.report_id == report_id,
                ImperiumMemoryCandidateDecision.decision.in_(("approved", "edited")),
            )
            .order_by(ImperiumMemoryCandidateDecision.created_at.desc())
            .offset(offset)
            .limit(limit + 1)
        )
    )
    decisions = [
        decision
        for decision in _sorted_commit_eligible_decisions(decisions, user_id=current_user.id)
        if decision.report_id == report_id
    ]
    has_more = len(decisions) > limit
    items = [_commit_candidate_read(decision) for decision in decisions[:limit]]
    return WeeklyReviewMemoryCommitPreviewRead(
        items=items,
        limit=limit,
        offset=offset,
        count=len(items),
        has_more=has_more,
        storage_enabled=False,
        note=MEMORY_COMMIT_READY_NOTE,
    )


def dry_run_weekly_review_memory_commit(
    db: Session,
    *,
    current_user: User,
    payload: WeeklyReviewMemoryCommitDryRunRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[WeeklyReviewMemoryCommitDryRunRead, bool]:
    request_payload = payload.model_dump(mode="json")
    request_hash = _hash_payload({"action": "weekly_review.memory_commit.dry_run", **request_payload})
    existing_key = _get_existing_idempotency(db, user_id=current_user.id, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_idempotency(existing_key, request_hash, WeeklyReviewMemoryCommitDryRunRead, request_path=request_path), True

    requested_ids = list(dict.fromkeys(payload.decision_ids))
    decisions = list(
        db.scalars(
            select(ImperiumMemoryCandidateDecision).where(
                ImperiumMemoryCandidateDecision.id.in_(requested_ids),
                ImperiumMemoryCandidateDecision.user_id == current_user.id,
            )
        )
    )
    decisions_by_id = {decision.id: decision for decision in decisions}
    candidates: list[WeeklyReviewMemoryCommitCandidateRead] = []
    blocked: list[dict] = []
    eligible_count = 0

    for decision_id in requested_ids:
        decision = decisions_by_id.get(decision_id)
        if decision is None:
            blocked.append(_blocked_commit_decision(decision_id=decision_id, reasons=["decision not found"]))
            continue
        if decision.user_id != current_user.id:
            blocked.append(_blocked_commit_decision(decision_id=decision_id, reasons=["decision not found"]))
            continue
        if decision.decision == "rejected":
            blocked.append(_blocked_commit_decision(decision_id=decision_id, reasons=["decision is rejected"]))
            continue
        if decision.decision not in {"approved", "edited"}:
            blocked.append(_blocked_commit_decision(decision_id=decision_id, reasons=["decision is not approved or edited"]))
            continue

        eligible_count += 1
        candidate = _commit_candidate_read(decision)
        if candidate.readiness_status == "ready":
            candidates.append(candidate)
        else:
            blocked.append(
                {
                    "decision_id": str(decision_id),
                    "candidate_id": candidate.candidate_id,
                    "readiness_status": candidate.readiness_status,
                    "readiness_reasons": candidate.readiness_reasons,
                }
            )

    response = WeeklyReviewMemoryCommitDryRunRead(
        requested_count=len(payload.decision_ids),
        eligible_count=eligible_count,
        blocked_count=len(blocked),
        would_commit_count=len(candidates),
        candidates=candidates,
        blocked=blocked,
        storage_enabled=False,
        note=MEMORY_COMMIT_DRY_RUN_NOTE,
    )
    _store_idempotency(
        db,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=200,
        response=response,
    )
    db.commit()
    return response, False


def commit_weekly_review_memory_candidates(
    db: Session,
    *,
    current_user: User,
    payload: WeeklyReviewMemoryCommitRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[WeeklyReviewMemoryCommitRead, bool]:
    request_payload = payload.model_dump(mode="json")
    request_hash = _hash_payload({"action": "weekly_review.memory_commit.commit", **request_payload})
    existing_key = _get_existing_idempotency(db, user_id=current_user.id, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_idempotency(existing_key, request_hash, WeeklyReviewMemoryCommitRead, request_path=request_path), True

    requested_ids = list(dict.fromkeys(payload.decision_ids))
    decisions = list(
        db.scalars(
            select(ImperiumMemoryCandidateDecision).where(
                ImperiumMemoryCandidateDecision.id.in_(requested_ids),
                ImperiumMemoryCandidateDecision.user_id == current_user.id,
            )
        )
    )
    decisions_by_id = {decision.id: decision for decision in decisions}
    memories: list[WeeklyReviewMemoryCommitItem] = []
    already_committed: list[WeeklyReviewMemoryAlreadyCommittedItem] = []
    blocked: list[dict] = []

    for decision_id in requested_ids:
        decision = decisions_by_id.get(decision_id)
        if decision is None:
            blocked.append(_blocked_memory_commit(decision_id=decision_id, reason="not_found"))
            continue
        if decision.user_id != current_user.id:
            blocked.append(_blocked_memory_commit(decision_id=decision_id, reason="not_found"))
            continue
        if decision.decision == "rejected":
            blocked.append(_blocked_memory_commit(decision_id=decision_id, reason="rejected"))
            continue
        if decision.decision not in {"approved", "edited"}:
            blocked.append(_blocked_memory_commit(decision_id=decision_id, reason="not_approved_or_edited"))
            continue

        try:
            draft = build_memory_draft_from_weekly_review_decision(decision, current_user_id=current_user.id)
        except AIMemoryOwnershipError:
            blocked.append(_blocked_memory_commit(decision_id=decision_id, reason="not_found"))
            continue
        except AIMemoryValidationError:
            blocked.append(_blocked_memory_commit(decision_id=decision_id, reason="invalid_candidate"))
            continue

        existing_memory = get_existing_memory_for_source(
            db,
            user_id=current_user.id,
            source_module=draft.source_module,
            source_type=draft.source_type,
            source_decision_id=draft.source_decision_id,
            source_id=draft.source_id,
        )
        if existing_memory is not None:
            already_committed.append(
                WeeklyReviewMemoryAlreadyCommittedItem(
                    memory_id=existing_memory.id,
                    decision_id=decision.id,
                )
            )
            continue

        memory = create_ai_memory_from_draft(db, draft=draft, idempotency_key=idempotency_key)
        memories.append(_memory_commit_item(memory=memory, decision=decision))

    response = WeeklyReviewMemoryCommitRead(
        requested_count=len(payload.decision_ids),
        committed_count=len(memories),
        already_committed_count=len(already_committed),
        blocked_count=len(blocked),
        memories=memories,
        already_committed=already_committed,
        blocked=blocked,
        storage_enabled=True,
        note="Committed approved memory candidates to ai_memories. No embeddings were generated.",
    )
    _store_idempotency(
        db,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=200,
        response=response,
    )
    db.commit()
    return response, False


def get_weekly_review_final_report_markdown(
    db: Session,
    *,
    current_user: User,
    session_id: UUID,
) -> str:
    session = _get_session_for_user(db, current_user=current_user, session_id=session_id)
    report = _get_latest_relevant_final_report(db, session=session, user_id=current_user.id)
    if report is None:
        raise WeeklyReviewFinalReportNotFoundError("Weekly review final report not found.")
    if report.report_markdown and report.report_markdown.strip():
        return report.report_markdown
    return _markdown_from_final_report(report)


def get_weekly_review_debug_status(
    db: Session,
    *,
    current_user: User,
    session_id: UUID,
    limit: int = 20,
) -> WeeklyReviewDebugStatusRead:
    limit = max(1, min(limit, 50))
    session = _get_session_for_user(db, current_user=current_user, session_id=session_id)
    current_ai_task = db.get(AITask, session.current_ai_task_id) if session.current_ai_task_id else None
    task_candidates = list(
        db.scalars(
            select(AITask)
            .where(
                AITask.user_id == current_user.id,
                AITask.source_module == "imperium",
            )
            .order_by(AITask.created_at.desc())
            .limit(limit)
        )
    )
    if current_ai_task is not None and all(task.id != current_ai_task.id for task in task_candidates):
        task_candidates.insert(0, current_ai_task)
    recent_ai_tasks = [task for task in task_candidates if _ai_task_matches_session(task, session_id=session.id)][:limit]
    task_ids = {task.id for task in recent_ai_tasks}
    if session.current_ai_task_id:
        task_ids.add(session.current_ai_task_id)

    result_candidates = list(
        db.scalars(
            select(AIResult)
            .where(AIResult.user_id == current_user.id)
            .order_by(AIResult.created_at.desc())
            .limit(limit)
        )
    )
    pinned_result_ids = {result_id for result_id in (session.initial_ai_result_id, session.final_ai_result_id) if result_id}
    recent_ai_results = [
        result
        for result in result_candidates
        if result.task_id in task_ids or result.id in pinned_result_ids
    ][:limit]
    for result_id in pinned_result_ids:
        if all(result.id != result_id for result in recent_ai_results):
            result = db.get(AIResult, result_id)
            if result is not None and result.user_id == current_user.id:
                recent_ai_results.insert(0, result)

    final_reports = list(
        db.scalars(
            select(ImperiumWeeklyReviewFinalReport)
            .where(
                ImperiumWeeklyReviewFinalReport.session_id == session.id,
                ImperiumWeeklyReviewFinalReport.user_id == current_user.id,
            )
            .order_by(ImperiumWeeklyReviewFinalReport.created_at.desc())
            .limit(limit)
        )
    )
    messages = list(
        db.scalars(
            select(ImperiumWeeklyReviewMessage)
            .where(ImperiumWeeklyReviewMessage.session_id == session.id)
            .order_by(ImperiumWeeklyReviewMessage.created_at.desc())
            .limit(limit)
        )
    )
    active_final_reports = [report for report in final_reports if report.status in MUTABLE_ACTIVE_FINAL_REPORT_STATUSES]
    stored_final_reports = [report for report in final_reports if report.status == "stored"]
    superseded_final_reports = [report for report in final_reports if report.status == "superseded"]
    active_final_report = active_final_reports[0] if active_final_reports else None
    latest_final_report = _select_latest_relevant_report(final_reports)
    latest_stored_report = (
        sorted(
            stored_final_reports,
            key=lambda report: (
                report.stored_at or datetime.min.replace(tzinfo=UTC),
                report.created_at or datetime.min.replace(tzinfo=UTC),
            ),
            reverse=True,
        )[0]
        if stored_final_reports
        else None
    )
    latest_active_report = active_final_report
    latest_user_message = next((message for message in messages if message.message_type == "user_answer"), None)
    latest_revision_request = next((message for message in messages if message.message_type == "revision_request"), None)
    latest_answer_integration_task = next(
        (task for task in recent_ai_tasks if task.task_type == ANSWER_INTEGRATION_TASK_TYPE),
        None,
    )

    return WeeklyReviewDebugStatusRead(
        session=WeeklyReviewSessionRead.model_validate(session),
        active_final_report_id=active_final_report.id if active_final_report else None,
        active_final_report_status=active_final_report.status if active_final_report else None,
        historical_final_report_count=len(superseded_final_reports),
        active_final_report_count=len(active_final_reports),
        active_reports_count=len(active_final_reports),
        stored_reports_count=len(stored_final_reports),
        superseded_reports_count=len(superseded_final_reports),
        latest_final_report_id=latest_final_report.id if latest_final_report else None,
        latest_stored_report_id=latest_stored_report.id if latest_stored_report else None,
        latest_active_report_id=latest_active_report.id if latest_active_report else None,
        latest_user_message_id=latest_user_message.id if latest_user_message else None,
        latest_revision_request_id=latest_revision_request.id if latest_revision_request else None,
        latest_answer_integration_task_id=latest_answer_integration_task.id if latest_answer_integration_task else None,
        current_ai_task=WeeklyReviewAITaskSummary.model_validate(current_ai_task) if current_ai_task else None,
        recent_ai_tasks=[WeeklyReviewAITaskSummary.model_validate(task) for task in recent_ai_tasks],
        recent_ai_results=[_ai_result_debug_summary(result) for result in recent_ai_results],
        final_report_candidates=[WeeklyReviewFinalReportRead.model_validate(report) for report in final_reports[:limit]],
        recent_messages=[WeeklyReviewMessageRead.model_validate(message) for message in messages[:limit]],
    )


def _chat_message_payload(payload: dict | None, *, source: str) -> dict:
    safe_payload = _strip_raw_payload(payload or {})
    return _json_safe({"source": source, "payload": safe_payload})


def _add_assistant_followup_message(
    db: Session,
    *,
    session: ImperiumWeeklyReviewSession,
    user_content: str,
) -> ImperiumWeeklyReviewMessage:
    bounded_content = _bounded_text(user_content, 600) or "ce point"
    visible_analysis = (
        "Dry-run Qwen: j'ai intégré ton message dans le bilan visible de la semaine "
        "sans générer de rapport final pour l'instant."
    )
    questions = [
        "Quel impact concret ce point a-t-il eu sur ta semaine ?",
        "Y a-t-il un blocage, une décision ou un signal important à préciser ?",
    ]
    content = (
        f"{visible_analysis}\n\n"
        f"Point ajouté: {bounded_content}\n\n"
        f"{WR_FINAL_CONFIRMATION_PROMPT}"
    )
    return _add_message(
        db,
        session=session,
        role="qwen",
        message_type="assistant_followup",
        content=content,
        payload={
            "source": "qwen_dry_run_chat_followup",
            "visible_analysis": visible_analysis,
            "questions": questions,
            "final_confirmation_prompt": WR_FINAL_CONFIRMATION_PROMPT,
        },
    )


def _create_chat_final_draft_ai_result(
    db: Session,
    *,
    session: ImperiumWeeklyReviewSession,
    content: str | None,
    payload: dict | None,
) -> tuple[AITask, AIResult]:
    input_payload = {
        "session_id": str(session.id),
        "week_start": session.week_start.isoformat(),
        "week_end": session.week_end.isoformat(),
        "final_user_clarification": content,
        "source": "backend_wr_chat_confirm_no_more_input",
    }
    ai_task = AITask(
        user_id=session.user_id,
        task_type="weekly_report.chat.final_draft.dry_run",
        status="result_received",
        source_module="imperium",
        input_payload=input_payload,
        prepared_payload=input_payload,
        model_hint="qwen2.5:7b-instruct",
        privacy_level="medium",
        completed_at=datetime.now(UTC),
    )
    db.add(ai_task)
    db.flush()
    report_payload = _chat_final_draft_payload(session=session, content=content, payload=payload)
    ai_result = AIResult(
        task_id=ai_task.id,
        user_id=session.user_id,
        result_type="weekly_report.draft",
        status="pending_validation",
        result_payload=report_payload,
        raw_payload={
            "source": "qwen_dry_run_chat_confirm_no_more_input",
            "dry_run": True,
        },
        model_used="qwen2.5:7b-instruct",
        provider="qwen-dry-run",
    )
    db.add(ai_result)
    db.flush()
    return ai_task, ai_result


def _chat_final_draft_payload(
    *,
    session: ImperiumWeeklyReviewSession,
    content: str | None,
    payload: dict | None,
) -> dict:
    clarification = content or "Aucun ajout final avant préparation du brouillon."
    title = f"Weekly Review {session.week_start.isoformat()} - {session.week_end.isoformat()}"
    summary = "Brouillon dry-run généré après confirmation explicite de fin de conversation."
    report_markdown = (
        f"# {title}\n\n"
        f"{summary}\n\n"
        "## Synthèse conversationnelle\n\n"
        f"{clarification}\n\n"
        "## Décision\n\n"
        "Ce brouillon reste une proposition et attend l'approbation utilisateur."
    )
    return {
        "title": title,
        "summary": summary,
        "sections": [
            {
                "title": "Synthèse conversationnelle",
                "content": clarification,
            }
        ],
        "questions_answered": [
            {
                "question": WR_FINAL_CONFIRMATION_PROMPT,
                "answer": clarification,
            }
        ],
        "source": "qwen_dry_run_chat_confirm_no_more_input",
        "payload": _strip_raw_payload(payload or {}),
        "report_markdown": report_markdown,
    }


def _build_chat_timeline(
    *,
    messages: list[ImperiumWeeklyReviewMessage],
    reports: list[ImperiumWeeklyReviewFinalReport],
) -> list[WeeklyReviewChatTimelineItem]:
    items: list[WeeklyReviewChatTimelineItem] = []
    report_ids_from_messages: set[UUID] = set()
    for message in messages:
        item_type = _timeline_type_for_message(message)
        source_report_id = _source_report_id_from_message(message, reports=reports)
        if source_report_id is not None:
            report_ids_from_messages.add(source_report_id)
        items.append(
            WeeklyReviewChatTimelineItem(
                id=f"msg_{message.id}",
                role=_timeline_role_for_message(message),
                type=item_type,
                content=message.content,
                created_at=message.created_at,
                source_message_id=message.id,
                source_report_id=source_report_id,
                display_payload=_strip_raw_payload(message.payload),
                is_final_draft=item_type == "final_draft",
            )
        )
    for report in reports:
        if report.id in report_ids_from_messages:
            continue
        if report.status not in {"draft", "approved", "stored"}:
            continue
        items.append(
            WeeklyReviewChatTimelineItem(
                id=f"report_{report.id}",
                role="assistant",
                type="final_draft",
                content=report.report_markdown,
                created_at=report.created_at,
                source_report_id=report.id,
                display_payload=_strip_raw_payload(_final_report_summary_payload(report)),
                is_final_draft=True,
            )
        )
    return sorted(items, key=lambda item: item.created_at)


def _timeline_type_for_message(message: ImperiumWeeklyReviewMessage) -> str:
    if message.message_type == "initial_summary":
        return "initial_summary"
    if message.message_type in {"chat_message", "user_answer"}:
        return "user_message"
    if message.message_type == "assistant_followup":
        return "assistant_followup"
    if message.message_type in {"final_report_draft", "draft", "final_report"}:
        return "final_draft"
    if message.message_type == "revision_request":
        return "user_message"
    return "status"


def _timeline_role_for_message(message: ImperiumWeeklyReviewMessage) -> str:
    if message.role == "user":
        return "user"
    if message.role in {"qwen", "opus", "backend"}:
        return "assistant"
    return "system"


def _source_report_id_from_message(
    message: ImperiumWeeklyReviewMessage,
    *,
    reports: list[ImperiumWeeklyReviewFinalReport],
) -> UUID | None:
    if message.ai_result_id is None:
        return None
    report = next((item for item in reports if item.source_ai_result_id == message.ai_result_id), None)
    return report.id if report else None


def _latest_assistant_prompt(messages: list[ImperiumWeeklyReviewMessage]) -> str | None:
    for message in sorted(messages, key=lambda item: item.created_at, reverse=True):
        if message.role not in {"qwen", "opus", "backend"}:
            continue
        payload = message.payload if isinstance(message.payload, dict) else {}
        prompt = payload.get("final_confirmation_prompt") or payload.get("prompt")
        if isinstance(prompt, str) and prompt.strip():
            return prompt.strip()
        if message.content and WR_FINAL_CONFIRMATION_PROMPT in message.content:
            return WR_FINAL_CONFIRMATION_PROMPT
    return None


def _visible_ai_state(
    *,
    session: ImperiumWeeklyReviewSession,
    ui_state: str,
    initial_ai_result: AIResult | None,
    active_final_report: ImperiumWeeklyReviewFinalReport | None,
    latest_final_report: ImperiumWeeklyReviewFinalReport | None,
    latest_assistant_prompt: str | None,
) -> WeeklyReviewVisibleAIState:
    initial_payload = initial_ai_result.result_payload if initial_ai_result is not None else {}
    if not isinstance(initial_payload, dict):
        initial_payload = {}
    report_payload = {}
    if active_final_report is not None:
        report_payload = active_final_report.report_payload or {}
    elif latest_final_report is not None:
        report_payload = latest_final_report.report_payload or {}
    summary = _first_text(
        report_payload.get("summary"),
        initial_payload.get("summary"),
        initial_payload.get("visible_analysis"),
    )
    current_step = _visible_current_step(ui_state=ui_state, session=session)
    return WeeklyReviewVisibleAIState(
        summary=summary,
        observed_signals=_text_list(initial_payload.get("observed_signals") or initial_payload.get("signals")),
        risks=_text_list(initial_payload.get("risks")),
        open_questions=_text_list(initial_payload.get("questions") or latest_assistant_prompt),
        draft_plan=_draft_plan_from_report_payload(report_payload),
        current_step=current_step,
        next_expected_user_action=_next_expected_user_action(ui_state),
        visible_reasoning_summary=_visible_reasoning_summary(
            ui_state=ui_state,
            has_initial_summary=session.initial_ai_result_id is not None,
            has_draft=active_final_report is not None,
        ),
    )


def _visible_current_step(*, ui_state: str, session: ImperiumWeeklyReviewSession) -> str:
    if session.status in {"preparing_initial_summary", "integrating_answers"} or ui_state == "preparing_initial_summary":
        return "waiting_for_ai"
    if ui_state == "conversation_active":
        return "collecting_user_context"
    if ui_state == "draft_ready":
        return "reviewing_final_draft"
    if ui_state == "approved":
        return "ready_to_store"
    if ui_state in {"stored", "closed"}:
        return "closed"
    if ui_state == "failed":
        return "failed"
    return "waiting_for_ai"


def _next_expected_user_action(ui_state: str) -> str | None:
    mapping = {
        "conversation_active": "send_message_or_confirm_no_more_input",
        "draft_ready": "approve_or_request_changes",
        "approved": "store_final_report",
    }
    return mapping.get(ui_state)


def _visible_reasoning_summary(*, ui_state: str, has_initial_summary: bool, has_draft: bool) -> str:
    if ui_state == "preparing_initial_summary":
        return "Je prépare une synthèse visible de la semaine avant de poursuivre la discussion."
    if ui_state == "conversation_active":
        if has_initial_summary:
            return "J’ai identifié les signaux principaux de la semaine, j’attends tes précisions avant de préparer le rapport final."
        return "J’attends les premiers éléments de contexte avant de préparer le rapport final."
    if ui_state == "draft_ready" and has_draft:
        return "Le brouillon du rapport final est prêt pour relecture, approbation ou demande de changements."
    if ui_state == "approved":
        return "Le rapport final est approuvé et attend uniquement l’action de stockage."
    if ui_state == "stored":
        return "Le rapport final est stocké. La session est clôturée."
    if ui_state == "failed":
        return "La revue hebdomadaire est en erreur et ne peut pas être modifiée."
    return "La revue hebdomadaire est dans un état fermé ou non modifiable."


def _draft_review_state(
    *,
    session: ImperiumWeeklyReviewSession,
    active_final_report: ImperiumWeeklyReviewFinalReport | None,
    latest_final_report: ImperiumWeeklyReviewFinalReport | None,
) -> WeeklyReviewDraftReviewState:
    report = active_final_report or latest_final_report
    if report is None:
        return WeeklyReviewDraftReviewState()
    active_status = _normalized_status(active_final_report)
    display_status = _normalized_status(report)
    is_closed = session.status in CLOSED_SESSION_STATUSES
    can_approve = active_status == "draft" and session.status in {"draft_ready", "final_ready"} and not is_closed
    can_request_changes = (
        active_status in {"draft", "approved"}
        and session.status in {"draft_ready", "final_ready", "approved"}
        and not is_closed
    )
    can_store = (
        active_status == "approved"
        and active_final_report is not None
        and active_final_report.stored_at is None
        and session.status == "approved"
        and not is_closed
    )
    return WeeklyReviewDraftReviewState(
        has_draft=display_status in {"draft", "approved", "stored"},
        active_draft_id=active_final_report.id if active_final_report else None,
        active_draft_status=active_status if active_final_report else None,
        can_approve=can_approve,
        can_request_changes=can_request_changes,
        can_store=can_store,
        latest_draft_title=_title_from_report(report),
        latest_draft_summary=_summary_from_report(report),
        latest_draft_markdown_preview=_bounded_text(report.report_markdown, 1000),
    )


def _conversation_action_descriptors(
    *,
    session_id: UUID,
    ui_state: str,
    flags: WeeklyReviewConversationFlags,
    allowed_actions: list[str],
) -> tuple[WeeklyReviewActionDescriptor | None, list[WeeklyReviewActionDescriptor]]:
    descriptors: list[WeeklyReviewActionDescriptor] = []
    if ui_state == "conversation_active":
        descriptors.append(_action_descriptor(session_id, "send_message", enabled="send_message" in allowed_actions))
        descriptors.append(_action_descriptor(session_id, "confirm_no_more_input", enabled="confirm_no_more_input" in allowed_actions))
    elif ui_state == "draft_ready":
        descriptors.append(_action_descriptor(session_id, "approve_draft", enabled="approve_draft" in allowed_actions))
        descriptors.append(_action_descriptor(session_id, "request_changes", enabled="request_changes" in allowed_actions))
        descriptors.append(_action_descriptor(session_id, "reject_draft", enabled=flags.can_reject))
    elif ui_state == "approved":
        descriptors.append(_action_descriptor(session_id, "store_final_report", enabled="store_final_report" in allowed_actions))
        descriptors.append(_action_descriptor(session_id, "request_changes", enabled="request_changes" in allowed_actions))
    enabled_descriptors = descriptors
    primary = next((item for item in enabled_descriptors if item.enabled and item.style == "primary"), None)
    if primary is None:
        primary = next((item for item in enabled_descriptors if item.enabled), None)
    secondary = [item for item in enabled_descriptors if primary is None or item.action != primary.action]
    return primary, secondary


def _action_descriptor(session_id: UUID, action: str, *, enabled: bool) -> WeeklyReviewActionDescriptor:
    endpoint_map = {
        "send_message": f"/api/imperium/weekly-review/{session_id}/chat/messages",
        "confirm_no_more_input": f"/api/imperium/weekly-review/{session_id}/chat/confirm-no-more-input",
        "approve_draft": f"/api/imperium/weekly-review/{session_id}/draft/approve",
        "request_changes": f"/api/imperium/weekly-review/{session_id}/draft/request-changes",
        "reject_draft": f"/api/imperium/weekly-review/{session_id}/draft/reject",
        "store_final_report": f"/api/imperium/weekly-review/{session_id}/draft/store",
    }
    labels = {
        "send_message": "Envoyer un message",
        "confirm_no_more_input": "Préparer le rapport final",
        "approve_draft": "Approuver le brouillon",
        "request_changes": "Demander des changements",
        "reject_draft": "Rejeter le brouillon",
        "store_final_report": "Stocker le rapport final",
    }
    requires_text = action in {"send_message", "request_changes", "reject_draft"}
    style = "primary" if action in {"send_message", "approve_draft", "store_final_report"} else "secondary"
    if action == "reject_draft":
        style = "danger"
    return WeeklyReviewActionDescriptor(
        action=action,
        label=labels[action],
        endpoint_hint=endpoint_map[action],
        requires_text=requires_text,
        style=style,
        enabled=enabled,
        disabled_reason=None if enabled else "Action unavailable in the current weekly review state.",
        confirmation_required=action in {"confirm_no_more_input", "approve_draft", "reject_draft", "store_final_report"},
    )


def _session_has_user_input(db: Session, *, session: ImperiumWeeklyReviewSession) -> bool:
    messages = list(
        db.scalars(
            select(ImperiumWeeklyReviewMessage).where(
                ImperiumWeeklyReviewMessage.session_id == session.id,
                ImperiumWeeklyReviewMessage.user_id == session.user_id,
                ImperiumWeeklyReviewMessage.role == "user",
                ImperiumWeeklyReviewMessage.message_type.in_({"chat_message", "user_answer", "revision_request"}),
            )
        )
    )
    return any(
        message.session_id == session.id
        and message.user_id == session.user_id
        and message.role == "user"
        and message.message_type in {"chat_message", "user_answer", "revision_request"}
        and bool((message.content or "").strip())
        for message in messages
    )


def _add_message(
    db: Session,
    *,
    session: ImperiumWeeklyReviewSession,
    role: str,
    message_type: str,
    content: str | None = None,
    payload: dict | None = None,
    ai_task_id: UUID | None = None,
    ai_result_id: UUID | None = None,
) -> ImperiumWeeklyReviewMessage:
    message = ImperiumWeeklyReviewMessage(
        session_id=session.id,
        user_id=session.user_id,
        role=role,
        message_type=message_type,
        content=content,
        payload=payload,
        ai_task_id=ai_task_id,
        ai_result_id=ai_result_id,
    )
    db.add(message)
    db.flush()
    return message


def _get_session_by_week(
    db: Session,
    *,
    current_user: User,
    week_start: date,
) -> ImperiumWeeklyReviewSession | None:
    return db.scalar(
        select(ImperiumWeeklyReviewSession).where(
            ImperiumWeeklyReviewSession.user_id == current_user.id,
            ImperiumWeeklyReviewSession.week_start == week_start,
        )
    )


def _get_session_for_user(
    db: Session,
    *,
    current_user: User,
    session_id: UUID,
) -> ImperiumWeeklyReviewSession:
    session = db.get(ImperiumWeeklyReviewSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise WeeklyReviewSessionNotFoundError("Weekly review session not found.")
    return session


def _ensure_session_not_terminal(session: ImperiumWeeklyReviewSession) -> None:
    if session.status in CLOSED_SESSION_STATUSES:
        raise WeeklyReviewStateConflictError("Cannot modify a closed weekly review session.")


def _ensure_session_open(session: ImperiumWeeklyReviewSession) -> None:
    _ensure_session_not_terminal(session)
    if session.status == "approved":
        raise WeeklyReviewStateConflictError("Weekly review session is closed.")


def _ensure_ai_attach_session_open(session: ImperiumWeeklyReviewSession) -> None:
    if session.status in {"approved", "stored", "cancelled", "failed"}:
        raise WeeklyReviewStateConflictError("Cannot attach AI result to a closed weekly review session.")


def _build_conversation_flags(
    *,
    session: ImperiumWeeklyReviewSession,
    active_final_report: ImperiumWeeklyReviewFinalReport | None,
) -> WeeklyReviewConversationFlags:
    closed_statuses = {"stored", "cancelled", "failed"}
    waiting_statuses = {"preparing_initial_summary", "integrating_answers"}
    active_status = _normalized_status(active_final_report)
    has_final_draft = active_status in MUTABLE_ACTIVE_FINAL_REPORT_STATUSES
    is_closed = session.status in closed_statuses
    can_approve = active_status == "draft" and session.status in {"draft_ready", "final_ready"} and not is_closed
    can_request_changes = active_status in {"draft", "approved"} and session.status in {"draft_ready", "final_ready", "approved"} and not is_closed
    can_store = (
        active_status == "approved"
        and active_final_report is not None
        and active_final_report.stored_at is None
        and session.status == "approved"
        and not is_closed
    )
    can_chat = (
        not is_closed
        and active_final_report is None
        and session.status in {
            "initial_summary_ready",
            "waiting_for_user_answer",
            "conversation_active",
            "revision_requested",
        }
    )

    return WeeklyReviewConversationFlags(
        can_answer=can_chat,
        can_send_message=can_chat,
        can_confirm_no_more_input=can_chat,
        can_request_revision=can_approve,
        can_approve=can_approve,
        can_store=can_store and session.status == "approved",
        can_request_changes=can_request_changes,
        can_reject=can_approve,
        is_waiting_for_ai=session.status in waiting_statuses and not is_closed,
        is_closed=is_closed,
        has_initial_summary=session.initial_ai_result_id is not None,
        has_final_draft=has_final_draft,
    )


def _conversation_ui_state(
    *,
    session: ImperiumWeeklyReviewSession,
    active_final_report: ImperiumWeeklyReviewFinalReport | None,
) -> str:
    if session.status == "stored":
        return "stored"
    if session.status == "approved":
        return "approved"
    if session.status == "failed":
        return "failed"
    if session.status == "cancelled":
        return "closed"
    active_status = _normalized_status(active_final_report)
    if active_status == "draft":
        return "draft_ready"
    if session.status in {"draft_ready", "final_ready"}:
        return "preparing_initial_summary"
    if session.status == "integrating_answers":
        return "preparing_initial_summary"
    if session.status in {"initial_summary_ready", "waiting_for_user_answer", "conversation_active", "revision_requested"}:
        return "conversation_active"
    return "preparing_initial_summary"


def _conversation_allowed_actions(
    *,
    ui_state: str,
    flags: WeeklyReviewConversationFlags,
) -> list[str]:
    if ui_state == "conversation_active" and flags.can_send_message:
        return ["send_message", "confirm_no_more_input"]
    if ui_state == "draft_ready" and flags.can_approve:
        return ["approve_draft", "request_changes"]
    if ui_state == "approved":
        actions: list[str] = []
        if flags.can_store:
            actions.append("store_final_report")
        if flags.can_request_changes:
            actions.append("request_changes")
        return actions
    return []


def _normalized_status(report: ImperiumWeeklyReviewFinalReport | None) -> str | None:
    if report is None:
        return None
    status = report.status
    if not isinstance(status, str):
        return None
    return status.strip().lower()


def _select_active_report_for_read(
    db: Session,
    *,
    session: ImperiumWeeklyReviewSession,
    user_id: UUID,
    reports: list[ImperiumWeeklyReviewFinalReport],
) -> ImperiumWeeklyReviewFinalReport | None:
    sorted_reports = sorted(
        reports,
        key=lambda report: report.created_at or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )
    active_report = next(
        (
            report
            for report in sorted_reports
            if report.session_id == session.id
            and report.user_id == user_id
            and _normalized_status(report) in MUTABLE_ACTIVE_FINAL_REPORT_STATUSES
        ),
        None,
    )
    if active_report is not None:
        return active_report
    if session.status in {"draft_ready", "final_ready", "approved"}:
        return _get_latest_mutable_report_for_changes(db, session=session, user_id=user_id)
    return None


def _get_reports_for_session(
    db: Session,
    *,
    session: ImperiumWeeklyReviewSession,
    user_id: UUID,
) -> list[ImperiumWeeklyReviewFinalReport]:
    reports = list(
        db.scalars(
            select(ImperiumWeeklyReviewFinalReport)
            .where(
                ImperiumWeeklyReviewFinalReport.session_id == session.id,
                ImperiumWeeklyReviewFinalReport.user_id == user_id,
            )
            .order_by(ImperiumWeeklyReviewFinalReport.created_at.desc())
        )
    )
    return [report for report in reports if report.session_id == session.id and report.user_id == user_id]


def _get_latest_relevant_final_report(
    db: Session,
    *,
    session: ImperiumWeeklyReviewSession,
    user_id: UUID,
) -> ImperiumWeeklyReviewFinalReport | None:
    return _select_latest_relevant_report(_get_reports_for_session(db, session=session, user_id=user_id))


def _select_latest_relevant_report(
    reports: list[ImperiumWeeklyReviewFinalReport],
) -> ImperiumWeeklyReviewFinalReport | None:
    if not reports:
        return None
    reports_by_date = sorted(
        reports,
        key=lambda report: report.created_at or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )
    return sorted(reports_by_date, key=lambda report: FINAL_REPORT_PRIORITY.get(report.status, 99))[0]


def _history_item_for_session(
    *,
    session: ImperiumWeeklyReviewSession,
    reports: list[ImperiumWeeklyReviewFinalReport],
) -> WeeklyReviewHistoryItem:
    latest_report = _select_latest_relevant_report(reports)
    active_reports_count = len([report for report in reports if report.status in MUTABLE_ACTIVE_FINAL_REPORT_STATUSES])
    stored_reports_count = len([report for report in reports if report.status == "stored"])
    superseded_reports_count = len([report for report in reports if report.status == "superseded"])
    return WeeklyReviewHistoryItem(
        session_id=session.id,
        week_start=session.week_start,
        week_end=session.week_end,
        session_status=session.status,
        launched_at=session.launched_at,
        completed_at=session.completed_at,
        failed_at=session.failed_at,
        latest_final_report=_final_report_summary(latest_report) if latest_report else None,
        has_initial_summary=session.initial_ai_result_id is not None,
        has_active_or_stored_report=active_reports_count > 0 or stored_reports_count > 0,
        has_stored_report=stored_reports_count > 0,
        has_superseded_reports=superseded_reports_count > 0,
        final_reports_count=len(reports),
        active_reports_count=active_reports_count,
        stored_reports_count=stored_reports_count,
        superseded_reports_count=superseded_reports_count,
    )


def _final_report_summary(report: ImperiumWeeklyReviewFinalReport) -> WeeklyReviewFinalReportSummary:
    payload = _strip_raw_payload(report.report_payload or {})
    summary = payload.get("summary") if isinstance(payload, dict) else None
    title = payload.get("title") if isinstance(payload, dict) else None
    return WeeklyReviewFinalReportSummary(
        id=report.id,
        status=report.status,
        week_start=report.week_start,
        week_end=report.week_end,
        summary=summary if isinstance(summary, str) else None,
        title=title if isinstance(title, str) else None,
        approved_at=report.approved_at,
        stored_at=report.stored_at,
        source_ai_result_id=report.source_ai_result_id,
        created_at=report.created_at,
    )


def _stored_final_report_summary(report: ImperiumWeeklyReviewFinalReport) -> WeeklyReviewStoredFinalReportSummary:
    payload = _strip_raw_payload(report.report_payload or {})
    summary = payload.get("summary") if isinstance(payload, dict) else None
    title = payload.get("title") if isinstance(payload, dict) else None
    return WeeklyReviewStoredFinalReportSummary(
        id=report.id,
        session_id=report.session_id,
        week_start=report.week_start,
        week_end=report.week_end,
        status=report.status,
        title=title if isinstance(title, str) else None,
        summary=summary if isinstance(summary, str) else None,
        stored_at=report.stored_at,
        approved_at=report.approved_at,
        created_at=report.created_at,
        source_ai_result_id=report.source_ai_result_id,
    )


def _decide_weekly_review_memory_candidate(
    db: Session,
    *,
    current_user: User,
    report_id: UUID,
    candidate_id: str,
    decision: str,
    reason: str | None,
    payload: dict | None,
    edited_candidate: dict | None,
    request_payload: dict,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[WeeklyReviewMemoryCandidateDecisionRead, bool]:
    request_hash = _hash_payload(
        {
            "action": f"weekly_review.memory_candidate.{decision}",
            "report_id": str(report_id),
            "candidate_id": candidate_id,
            **request_payload,
        }
    )
    existing_key = _get_existing_idempotency(db, user_id=current_user.id, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_idempotency(existing_key, request_hash, WeeklyReviewMemoryCandidateDecisionRead, request_path=request_path), True

    report = db.get(ImperiumWeeklyReviewFinalReport, report_id)
    if report is None or report.user_id != current_user.id:
        raise WeeklyReviewFinalReportNotFoundError("Weekly review final report not found.")
    if report.status not in {"stored", "approved"}:
        raise WeeklyReviewStateConflictError("Memory candidate decisions require an approved or stored weekly review report.")

    session = db.get(ImperiumWeeklyReviewSession, report.session_id)
    if session is not None and session.user_id != current_user.id:
        raise WeeklyReviewFinalReportNotFoundError("Weekly review final report not found.")

    candidates = _build_weekly_review_memory_candidates(report, session)
    original_candidate = next((candidate for candidate in candidates if candidate["id"] == candidate_id), None)
    if original_candidate is None:
        raise WeeklyReviewFinalReportNotFoundError("Weekly review memory candidate not found.")

    existing_decision = _get_memory_candidate_decision(
        db,
        user_id=current_user.id,
        report_id=report.id,
        candidate_id=candidate_id,
    )
    if existing_decision is not None:
        raise WeeklyReviewStateConflictError("Weekly review memory candidate has already been decided.")

    clean_original = _json_safe(_strip_raw_payload(original_candidate))
    clean_edited = _edited_candidate_from_patch(clean_original, edited_candidate) if decision == "edited" else None
    decision_row = ImperiumMemoryCandidateDecision(
        user_id=current_user.id,
        report_id=report.id,
        session_id=report.session_id,
        candidate_id=candidate_id,
        decision=decision,
        source="weekly_review",
        original_candidate=clean_original,
        edited_candidate=clean_edited,
        reason=reason,
        payload=_json_safe(_strip_raw_payload(payload)),
        idempotency_key=idempotency_key,
    )
    db.add(decision_row)
    db.flush()
    response = _decision_read(decision_row)
    _store_idempotency(
        db,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=201,
        response=response,
    )
    db.commit()
    return response, False


def _get_memory_candidate_decision(
    db: Session,
    *,
    user_id: UUID,
    report_id: UUID,
    candidate_id: str,
) -> ImperiumMemoryCandidateDecision | None:
    return db.scalar(
        select(ImperiumMemoryCandidateDecision).where(
            ImperiumMemoryCandidateDecision.user_id == user_id,
            ImperiumMemoryCandidateDecision.report_id == report_id,
            ImperiumMemoryCandidateDecision.candidate_id == candidate_id,
        )
    )


def _get_memory_candidate_decisions_for_report(
    db: Session,
    *,
    report_id: UUID,
    user_id: UUID,
) -> list[ImperiumMemoryCandidateDecision]:
    decisions = list(
        db.scalars(
            select(ImperiumMemoryCandidateDecision).where(
                ImperiumMemoryCandidateDecision.user_id == user_id,
                ImperiumMemoryCandidateDecision.report_id == report_id,
            )
        )
    )
    return [decision for decision in decisions if decision.user_id == user_id and decision.report_id == report_id]


def _decision_read(decision: ImperiumMemoryCandidateDecision) -> WeeklyReviewMemoryCandidateDecisionRead:
    response = WeeklyReviewMemoryCandidateDecisionRead.model_validate(decision)
    return response.model_copy(
        update={
            "original_candidate": _strip_raw_payload(response.original_candidate),
            "edited_candidate": _strip_raw_payload(response.edited_candidate),
            "payload": _strip_raw_payload(response.payload),
        }
    )


def _memory_candidates_response(
    *,
    report: ImperiumWeeklyReviewFinalReport,
    session: ImperiumWeeklyReviewSession | None,
    decisions: list[ImperiumMemoryCandidateDecision] | None = None,
    include_rejected: bool = True,
) -> WeeklyReviewMemoryCandidatesResponse:
    decisions_by_candidate = {
        decision.candidate_id: decision
        for decision in decisions or []
        if decision.report_id == report.id
    }
    all_candidates = [
        _merge_candidate_decision(candidate, decisions_by_candidate.get(candidate["id"]))
        for candidate in _build_weekly_review_memory_candidates(report, session)
    ]
    rejected_hidden_count = len(
        [candidate for candidate in all_candidates if candidate["decision_status"] == "rejected"]
    )
    visible_candidates = [
        candidate
        for candidate in all_candidates
        if include_rejected or candidate["decision_status"] != "rejected"
    ]
    candidates = [WeeklyReviewMemoryCandidateRead.model_validate(candidate) for candidate in visible_candidates]
    return WeeklyReviewMemoryCandidatesResponse(
        report_id=report.id,
        session_id=report.session_id,
        week_start=report.week_start,
        week_end=report.week_end,
        report_status=report.status,
        candidates=candidates,
        count=len(candidates),
        storage_enabled=False,
        note=MEMORY_CANDIDATE_NOTE,
        total_candidates=len(all_candidates),
        rejected_hidden_count=0 if include_rejected else rejected_hidden_count,
    )


def _sorted_commit_eligible_decisions(
    decisions: list[ImperiumMemoryCandidateDecision],
    *,
    user_id: UUID,
) -> list[ImperiumMemoryCandidateDecision]:
    filtered = [
        decision
        for decision in decisions
        if decision.user_id == user_id and decision.decision in {"approved", "edited"}
    ]
    return sorted(
        filtered,
        key=lambda decision: decision.created_at or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )


def _commit_candidate_read(decision: ImperiumMemoryCandidateDecision) -> WeeklyReviewMemoryCommitCandidateRead:
    original_candidate = _json_safe(_strip_raw_payload(decision.original_candidate or {}))
    edited_candidate = _json_safe(_strip_raw_payload(decision.edited_candidate)) if decision.edited_candidate else None
    effective_candidate = edited_candidate if decision.decision == "edited" and edited_candidate else original_candidate
    readiness_status, readiness_reasons = _commit_readiness(effective_candidate)
    title = _commit_text(effective_candidate.get("title")) or ""
    content = _commit_text(effective_candidate.get("content")) or ""
    kind = _commit_text(effective_candidate.get("kind")) or ""
    confidence = _commit_confidence(effective_candidate.get("confidence"))
    proposed_memory_scope = _commit_text(effective_candidate.get("proposed_memory_scope")) or ""
    source = _commit_text(effective_candidate.get("source")) or "weekly_review_final_report"
    source_report_id = _commit_uuid(effective_candidate.get("source_report_id"), fallback=decision.report_id)
    source_session_id = _commit_uuid(effective_candidate.get("source_session_id"), fallback=decision.session_id)
    week_start = _commit_date(effective_candidate.get("week_start"))
    week_end = _commit_date(effective_candidate.get("week_end"))
    return WeeklyReviewMemoryCommitCandidateRead(
        decision_id=decision.id,
        report_id=decision.report_id,
        session_id=decision.session_id,
        candidate_id=decision.candidate_id,
        decision=decision.decision,
        title=title,
        content=content,
        kind=kind,
        confidence=confidence,
        proposed_memory_scope=proposed_memory_scope,
        week_start=week_start,
        week_end=week_end,
        source=source,
        source_report_id=source_report_id,
        source_session_id=source_session_id,
        effective_candidate=effective_candidate,
        original_candidate=original_candidate,
        edited_candidate=edited_candidate,
        readiness_status=readiness_status,
        readiness_reasons=readiness_reasons,
        created_at=decision.created_at,
        updated_at=decision.updated_at,
    )


def _commit_readiness(candidate: dict) -> tuple[str, list[str]]:
    reasons: list[str] = []
    title = _commit_text(candidate.get("title"))
    content = _commit_text(candidate.get("content"))
    kind = _commit_text(candidate.get("kind"))
    confidence = _commit_confidence(candidate.get("confidence"))
    scope = _commit_text(candidate.get("proposed_memory_scope"))

    if not title:
        reasons.append("candidate missing non-empty title")
    if not content:
        reasons.append("candidate missing non-empty content")
    if kind not in MEMORY_CANDIDATE_KINDS:
        reasons.append("candidate has invalid kind")
    if confidence is None or confidence < 0 or confidence > 1:
        reasons.append("candidate has invalid confidence")
    if scope not in MEMORY_CANDIDATE_SCOPES:
        reasons.append("candidate has invalid proposed_memory_scope")
    return ("blocked", reasons) if reasons else ("ready", [])


def _blocked_commit_decision(*, decision_id: UUID, reasons: list[str]) -> dict:
    return {
        "decision_id": str(decision_id),
        "readiness_status": "blocked",
        "readiness_reasons": reasons,
    }


def _blocked_memory_commit(*, decision_id: UUID, reason: str) -> dict:
    return {
        "decision_id": str(decision_id),
        "reason": reason,
    }


def _memory_commit_item(
    *,
    memory: AIMemory,
    decision: ImperiumMemoryCandidateDecision,
) -> WeeklyReviewMemoryCommitItem:
    return WeeklyReviewMemoryCommitItem(
        memory_id=memory.id,
        decision_id=decision.id,
        candidate_id=decision.candidate_id,
        status=memory.status,
        title=memory.title,
        kind=memory.kind,
        scope=memory.scope,
        confidence=float(memory.confidence),
        created_at=memory.created_at,
    )


def _commit_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _commit_confidence(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _commit_uuid(value, *, fallback: UUID) -> UUID:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError:
            return fallback
    return fallback


def _commit_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            pass
    return date(1970, 1, 1)


def _build_weekly_review_memory_candidates(
    report: ImperiumWeeklyReviewFinalReport,
    session: ImperiumWeeklyReviewSession | None,
) -> list[dict]:
    payload = _strip_raw_payload(report.report_payload or {})
    raw_candidates: list = []
    if isinstance(payload, dict):
        raw_candidates.extend(_candidate_items(payload.get("memory_candidates")))
    raw_candidates.extend(_candidate_items(_strip_raw_payload(report.memory_candidates)))

    candidates = [
        candidate
        for index, raw in enumerate(raw_candidates)
        if (candidate := _normalize_memory_candidate(raw, report, session, index))
    ]
    if candidates:
        return candidates
    return _derive_fallback_memory_candidates(report, session)


def _normalize_memory_candidate(
    raw,
    report: ImperiumWeeklyReviewFinalReport,
    session: ImperiumWeeklyReviewSession | None,
    index: int,
) -> dict | None:
    if not isinstance(raw, dict):
        return None
    raw = _strip_raw_payload(raw)
    text_blob = " ".join(str(value) for value in raw.values() if value is not None)
    kind = _safe_kind(raw.get("kind") or raw.get("type") or _kind_for_memory_text(text_blob))
    title = _bounded_text(raw.get("title") or raw.get("label") or raw.get("question"), 160)
    content = _bounded_text(
        raw.get("content")
        or raw.get("summary")
        or raw.get("text")
        or raw.get("description")
        or raw.get("answer"),
        1200,
    )
    if content is None and title is not None:
        content = title
    if title is None and content is not None:
        title = _bounded_text(content, 160)
    if title is None or content is None:
        return None

    confidence = _clamp_confidence(raw.get("confidence", raw.get("score", 0.5)))
    scope = _safe_memory_scope(raw.get("proposed_memory_scope") or raw.get("scope"))
    source = _bounded_text(raw.get("source") or "weekly_review_final_report", 160) or "weekly_review_final_report"
    digest = hashlib.sha256(
        f"{report.id}:{index}:{kind}:{title}:{content}".encode("utf-8")
    ).hexdigest()[:16]
    return {
        "id": f"wrmem_{digest}",
        "kind": kind,
        "title": title,
        "content": content,
        "confidence": confidence,
        "source": source,
        "source_report_id": report.id,
        "source_session_id": session.id if session is not None else report.session_id,
        "week_start": report.week_start,
        "week_end": report.week_end,
        "proposed_memory_scope": scope,
        "status": "candidate",
        "created_from": "weekly_review_final_report",
    }


def _merge_candidate_decision(
    candidate: dict,
    decision: ImperiumMemoryCandidateDecision | None,
) -> dict:
    merged = dict(candidate)
    if decision is None:
        merged.update(
            {
                "decision_status": "undecided",
                "decision_id": None,
                "decided_at": None,
                "edited_candidate": None,
                "effective_candidate": _candidate_effective_dict(candidate),
            }
        )
        return merged
    edited_candidate = _strip_raw_payload(decision.edited_candidate)
    merged.update(
        {
            "decision_status": decision.decision,
            "decision_id": decision.id,
            "decided_at": decision.created_at,
            "edited_candidate": edited_candidate,
            "effective_candidate": edited_candidate if decision.decision == "edited" and edited_candidate else _candidate_effective_dict(candidate),
        }
    )
    return merged


def _edited_candidate_from_patch(original_candidate: dict, edited_patch: dict | None) -> dict:
    patch = edited_patch or {}
    edited = _candidate_effective_dict(original_candidate)
    title = _bounded_text(patch.get("title"), 160)
    content = _bounded_text(patch.get("content"), 1200)
    kind = _safe_kind(patch.get("kind") or edited.get("kind"))
    confidence = _clamp_confidence(patch.get("confidence", edited.get("confidence", 0.5)))
    if title:
        edited["title"] = title
    if content:
        edited["content"] = content
    edited["kind"] = kind
    edited["confidence"] = confidence
    edited["status"] = "candidate"
    return _strip_raw_payload(edited)


def _candidate_effective_dict(candidate: dict) -> dict:
    keys = (
        "id",
        "kind",
        "title",
        "content",
        "confidence",
        "source",
        "source_report_id",
        "source_session_id",
        "week_start",
        "week_end",
        "proposed_memory_scope",
        "status",
        "created_from",
    )
    return {key: candidate.get(key) for key in keys}


def _derive_fallback_memory_candidates(
    report: ImperiumWeeklyReviewFinalReport,
    session: ImperiumWeeklyReviewSession | None,
) -> list[dict]:
    payload = _strip_raw_payload(report.report_payload or {})
    if not isinstance(payload, dict):
        return []

    raw_candidates: list[dict] = []
    summary = _string_payload_value(payload, "summary")
    if summary:
        raw_candidates.append(
            {
                "kind": "operational_signal",
                "title": "Weekly review summary",
                "content": summary,
                "confidence": 0.55,
                "proposed_memory_scope": "weekly_review",
                "source": "weekly_review_fallback",
            }
        )

    sections = payload.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if isinstance(section, dict):
                title = _bounded_text(section.get("title") or "Weekly review section", 160)
                content = _bounded_text(section.get("content") or section.get("summary"), 1200)
            else:
                title = "Weekly review section"
                content = _bounded_text(section, 1200)
            if content:
                raw_candidates.append(
                    {
                        "kind": _kind_for_memory_text(f"{title or ''} {content}"),
                        "title": title or "Weekly review section",
                        "content": content,
                        "confidence": 0.5,
                        "proposed_memory_scope": "operating_pattern",
                        "source": "weekly_review_fallback",
                    }
                )

    questions_answered = payload.get("questions_answered")
    if isinstance(questions_answered, list):
        for item in questions_answered:
            if isinstance(item, dict):
                question = _bounded_text(item.get("question") or item.get("label") or "Weekly review answer", 160)
                answer = _bounded_text(item.get("answer") or item.get("content") or item.get("summary"), 1200)
                content = f"{question}: {answer}" if answer else question
            else:
                question = "Weekly review answer"
                content = _bounded_text(item, 1200)
            if content:
                raw_candidates.append(
                    {
                        "kind": _kind_for_memory_text(content),
                        "title": question or "Weekly review answer",
                        "content": content,
                        "confidence": 0.5,
                        "proposed_memory_scope": "weekly_review",
                        "source": "weekly_review_fallback",
                    }
                )

    return [
        candidate
        for index, raw in enumerate(raw_candidates)
        if (candidate := _normalize_memory_candidate(raw, report, session, index))
    ]


def _final_report_read(report: ImperiumWeeklyReviewFinalReport) -> WeeklyReviewFinalReportRead:
    response = WeeklyReviewFinalReportRead.model_validate(report)
    return response.model_copy(
        update={
            "report_payload": _strip_raw_payload(response.report_payload),
            "memory_candidates": _strip_raw_payload(response.memory_candidates),
        }
    )


def _markdown_from_final_report(report: ImperiumWeeklyReviewFinalReport) -> str:
    payload = _strip_raw_payload(report.report_payload or {})
    title = _string_payload_value(payload, "title") or "Weekly Review Final Report"
    lines = [f"# {title}", ""]
    summary = _string_payload_value(payload, "summary")
    if summary:
        lines.extend(["## Summary", "", summary, ""])

    sections = payload.get("sections") if isinstance(payload, dict) else None
    if isinstance(sections, list) and sections:
        lines.extend(["## Sections", ""])
        for section in sections:
            if isinstance(section, dict):
                section_title = section.get("title") or "Section"
                content = section.get("content") or section.get("summary") or ""
                lines.extend([f"### {section_title}", "", str(content), ""])
            else:
                lines.extend([f"- {section}", ""])

    questions_answered = payload.get("questions_answered") if isinstance(payload, dict) else None
    if questions_answered:
        lines.extend(["## Questions Answered", ""])
        if isinstance(questions_answered, list):
            for item in questions_answered:
                if isinstance(item, dict):
                    question = item.get("question") or item.get("label") or "Question"
                    answer = item.get("answer") or item.get("content") or ""
                    lines.extend([f"- **{question}**: {answer}"])
                else:
                    lines.extend([f"- {item}"])
        else:
            lines.extend([str(questions_answered)])
        lines.append("")

    lines.extend(
        [
            "## Metadata",
            "",
            f"- Week start: {report.week_start}",
            f"- Week end: {report.week_end}",
            f"- Status: {report.status}",
            f"- Approved at: {report.approved_at.isoformat() if report.approved_at else 'none'}",
            f"- Stored at: {report.stored_at.isoformat() if report.stored_at else 'none'}",
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _string_payload_value(payload: dict | list | None, key: str) -> str | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _candidate_items(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("candidates", "items", "memory_candidates"):
            nested = value.get(key)
            if isinstance(nested, list):
                return nested
        return [value]
    return []


def _safe_kind(value) -> str:
    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate in MEMORY_CANDIDATE_KINDS:
            return candidate
    return "operational_signal"


def _safe_memory_scope(value) -> str:
    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate in MEMORY_CANDIDATE_SCOPES:
            return candidate
    return "weekly_review"


def _bounded_text(value, max_length: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:max_length]


def _clamp_confidence(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.5
    if number > 1 and number <= 100:
        number = number / 100
    return max(0.0, min(number, 1.0))


def _kind_for_memory_text(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ("risk", "danger", "unsafe", "medical")):
        return "risk"
    if any(token in lowered for token in ("block", "blocked", "blocker", "frein", "problem", "fatigue", "stress", "missed")):
        return "blocker"
    if any(token in lowered for token in ("win", "achievement", "achieved", "completed", "success", "reussi")):
        return "achievement"
    if any(token in lowered for token in ("next", "commit", "commitment", "decision", "will", "semaine prochaine")):
        return "weekly_commitment"
    if "prefer" in lowered or "preference" in lowered:
        return "preference"
    if "pattern" in lowered or "habit" in lowered:
        return "behavior_pattern"
    return "operational_signal"


def _strip_raw_payload(value):
    if isinstance(value, list):
        return [_strip_raw_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: _strip_raw_payload(item) for key, item in value.items() if key != "raw_payload"}
    return value


def _first_text(*values) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _text_list(value) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _draft_plan_from_report_payload(payload: dict) -> list[str]:
    sections = payload.get("sections") if isinstance(payload, dict) else None
    if not isinstance(sections, list):
        return []
    plan: list[str] = []
    for section in sections[:5]:
        if isinstance(section, dict):
            title = section.get("title")
            if isinstance(title, str) and title.strip():
                plan.append(title.strip())
        elif isinstance(section, str) and section.strip():
            plan.append(section.strip())
    return plan


def _final_report_summary_payload(report: ImperiumWeeklyReviewFinalReport) -> dict:
    return {
        "id": str(report.id),
        "status": report.status,
        "title": _title_from_report(report),
        "summary": _summary_from_report(report),
    }


def _title_from_report(report: ImperiumWeeklyReviewFinalReport) -> str | None:
    payload = report.report_payload or {}
    if isinstance(payload, dict):
        title = payload.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    first_line = (report.report_markdown or "").strip().splitlines()[0:1]
    if first_line and first_line[0].startswith("#"):
        return first_line[0].lstrip("#").strip() or None
    return None


def _summary_from_report(report: ImperiumWeeklyReviewFinalReport) -> str | None:
    payload = report.report_payload or {}
    if isinstance(payload, dict):
        summary = payload.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
    return _bounded_text(report.report_markdown, 500)


def _json_safe(value):
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def _get_latest_final_report(
    db: Session,
    *,
    session: ImperiumWeeklyReviewSession,
    user_id: UUID,
) -> ImperiumWeeklyReviewFinalReport | None:
    return db.scalar(
        select(ImperiumWeeklyReviewFinalReport)
        .where(
            ImperiumWeeklyReviewFinalReport.session_id == session.id,
            ImperiumWeeklyReviewFinalReport.user_id == user_id,
        )
        .order_by(ImperiumWeeklyReviewFinalReport.created_at.desc())
    )


def _get_latest_active_draft_report(
    db: Session,
    *,
    session: ImperiumWeeklyReviewSession,
    user_id: UUID,
) -> ImperiumWeeklyReviewFinalReport | None:
    return db.scalar(
        select(ImperiumWeeklyReviewFinalReport)
        .where(
            ImperiumWeeklyReviewFinalReport.session_id == session.id,
            ImperiumWeeklyReviewFinalReport.user_id == user_id,
            ImperiumWeeklyReviewFinalReport.status == "draft",
        )
        .order_by(ImperiumWeeklyReviewFinalReport.created_at.desc())
    )


def _get_latest_active_final_report(
    db: Session,
    *,
    session: ImperiumWeeklyReviewSession,
    user_id: UUID,
) -> ImperiumWeeklyReviewFinalReport | None:
    return db.scalar(
        select(ImperiumWeeklyReviewFinalReport)
        .where(
            ImperiumWeeklyReviewFinalReport.session_id == session.id,
            ImperiumWeeklyReviewFinalReport.user_id == user_id,
            ImperiumWeeklyReviewFinalReport.status.in_(ACTIVE_FINAL_REPORT_STATUSES),
        )
        .order_by(ImperiumWeeklyReviewFinalReport.created_at.desc())
    )


def _get_latest_mutable_report_for_changes(
    db: Session,
    *,
    session: ImperiumWeeklyReviewSession,
    user_id: UUID,
) -> ImperiumWeeklyReviewFinalReport | None:
    return db.scalar(
        select(ImperiumWeeklyReviewFinalReport)
        .where(
            ImperiumWeeklyReviewFinalReport.session_id == session.id,
            ImperiumWeeklyReviewFinalReport.user_id == user_id,
            ImperiumWeeklyReviewFinalReport.status.in_({"draft", "approved"}),
        )
        .order_by(ImperiumWeeklyReviewFinalReport.created_at.desc())
    )


def _ai_task_matches_session(task: AITask, *, session_id: UUID) -> bool:
    session_id_text = str(session_id)
    payloads = [task.input_payload, task.prepared_payload]
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        if payload.get("session_id") == session_id_text or payload.get("source_ref_id") == session_id_text:
            return True
    return False


def _ai_result_debug_summary(result: AIResult) -> WeeklyReviewAIResultDebugSummary:
    raw_payload_keys = sorted(result.raw_payload.keys()) if isinstance(result.raw_payload, dict) else []
    return WeeklyReviewAIResultDebugSummary(
        id=result.id,
        task_id=result.task_id,
        result_type=result.result_type,
        result_payload=result.result_payload,
        provider=result.provider,
        model_used=result.model_used,
        confidence=result.confidence,
        status=result.status,
        created_at=result.created_at,
        raw_payload_keys=raw_payload_keys,
    )


def _validate_week_start(week_start: date) -> None:
    if week_start.weekday() != 0:
        raise InvalidWeekStartError("week_start must be a Monday.")


def _role_for_ai_result(ai_result: AIResult) -> str:
    provider = (ai_result.provider or "").lower()
    model = (ai_result.model_used or "").lower()
    if "opus" in provider or "opus" in model or "claude" in provider:
        return "opus"
    if "qwen" in provider or "qwen" in model:
        return "qwen"
    return "backend"


def _message_type_for_ai_result(ai_result: AIResult) -> str:
    if ai_result.result_type == "weekly_report.summary":
        return "initial_summary"
    if ai_result.result_type == "weekly_report.questions":
        return "clarification_question"
    if ai_result.result_type in {"weekly_report.draft", "weekly_report.revision"}:
        return "draft"
    if ai_result.result_type == "weekly_report.final":
        return "final_report"
    return "system_note"


def _get_existing_idempotency(
    db: Session,
    *,
    user_id: UUID,
    idempotency_key: str,
) -> IdempotencyKey | None:
    return db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.idempotency_key == idempotency_key,
        )
    )


def _handle_idempotency(
    existing_key: IdempotencyKey,
    request_hash: str,
    schema: type[T],
    *,
    request_path: str,
) -> T:
    if existing_key.request_path != request_path:
        raise WeeklyReviewIdempotencyConflictError("Idempotency-Key already used on a different endpoint.")
    if existing_key.request_hash != request_hash:
        raise WeeklyReviewIdempotencyConflictError("Idempotency key already used with different payload.")
    if existing_key.response_body is None:
        raise WeeklyReviewIdempotencyConflictError("Idempotency key is already processing.")
    return schema.model_validate(existing_key.response_body)


def _store_idempotency(
    db: Session,
    *,
    user_id: UUID,
    idempotency_key: str,
    request_method: str,
    request_path: str,
    request_hash: str,
    response_status_code: int,
    response: BaseModel,
) -> None:
    db.add(
        IdempotencyKey(
            user_id=user_id,
            idempotency_key=idempotency_key,
            request_method=request_method,
            request_path=request_path,
            request_hash=request_hash,
            status=IdempotencyStatus.completed,
            response_status_code=response_status_code,
            response_body=response.model_dump(mode="json"),
        )
    )


def _hash_payload(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def current_week_start(today: date) -> date:
    return today - timedelta(days=today.weekday())
