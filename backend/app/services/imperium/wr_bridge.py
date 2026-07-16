"""WR n8n bridges ported to direct backend service calls (passe 0, N8N_INVENTORY §A).

The two production n8n workflows were nothing but chains of signed internal
POSTs; in the backend they become plain function calls with the SAME payload
shapes, the SAME field validations and the SAME idempotency keys — the network
hop and the internal HMAC signatures disappear (no hop, nothing to sign).
Equivalence is proven by tests fed with the payloads of the JSON exports
(tests/fixtures/n8n_wr_payloads.py).

The single intentional divergence: model_used/model_hint are resolved through
the `local_executor` role (ai_role_models) instead of the hard-coded legacy
7B model id the workflows carried (DV-6).

Workflow #3 (mock) is not ported: it became a pytest fixture of this flow.
"""

import logging

from sqlalchemy.orm import Session

from app.models.ai import AIResult, AITask
from app.schemas.ai import AIResultCallback
from app.schemas.weekly_review import WeeklyReviewAttachAIResultRequest
from app.services.ai.providers.qwen import QwenClient
from app.services.ai.roles import LOCAL_EXECUTOR_ROLE, resolve_model_id
from app.services.ai.tasks import receive_ai_result
from app.services.imperium.weekly_review_conversation import attach_ai_result_to_session

logger = logging.getLogger(__name__)

INTERACTIVE_START_TASK_TYPE = "weekly_report.interactive.start"
ANSWERS_INTEGRATE_TASK_TYPE = "weekly_report.answers.integrate"

_START_REQUIRED_FIELDS = (
    "task_id",
    "session_id",
    "task_type",
    "week_start",
    "week_end",
    "callback_url",
    "wr_attach_url",
)
_ANSWERS_REQUIRED_FIELDS = _START_REQUIRED_FIELDS + ("user_message_id", "user_answer")


class WRBridgePayloadError(ValueError):
    pass


def _validate_payload(payload: dict, *, required: tuple[str, ...], task_type: str) -> None:
    for field in required:
        if not payload.get(field):
            raise WRBridgePayloadError(f"Missing required WR payload field: {field}")
    if payload["task_type"] != task_type:
        raise WRBridgePayloadError(f"Unsupported task_type for WR bridge: {payload['task_type']}")
    expected_callback = f"/api/internal/ai/tasks/{payload['task_id']}/result"
    expected_attach = f"/api/internal/weekly-review/{payload['session_id']}/attach-ai-result"
    if payload["callback_url"] != expected_callback:
        raise WRBridgePayloadError(f"Unexpected callback_url. Expected {expected_callback}")
    if payload["wr_attach_url"] != expected_attach:
        raise WRBridgePayloadError(f"Unexpected wr_attach_url. Expected {expected_attach}")


def run_wr_interactive_start(db: Session, *, ai_task: AITask) -> AIResult:
    """Ported IMPERIUM_WR_INTERACTIVE_START_QWEN_DRY_RUN: smoke → callback → attach."""
    payload = dict(ai_task.prepared_payload or {})
    _validate_payload(
        payload, required=_START_REQUIRED_FIELDS, task_type=INTERACTIVE_START_TASK_TYPE
    )

    summary = QwenClient().generate_weekly_summary(
        input_payload={
            "week_start": payload["week_start"],
            "week_end": payload["week_end"],
            "session_id": payload["session_id"],
            "task_id": payload["task_id"],
            "source": "n8n_qwen_dry_run_workflow",
        }
    )
    if summary.result_type != "weekly_report.summary":
        raise WRBridgePayloadError(f"Unexpected Qwen result_type: {summary.result_type}")

    callback = AIResultCallback(
        result_type="weekly_report.summary",
        result_payload={
            "summary": summary.summary,
            "sections": summary.sections,
            "questions": summary.questions,
            "warnings": summary.warnings,
            "source": "qwen_dry_run",
        },
        model_used=resolve_model_id(LOCAL_EXECUTOR_ROLE, db=db),
        provider="qwen-dry-run",
        confidence=summary.confidence,
        raw_payload={
            "workflow": "IMPERIUM_WR_INTERACTIVE_START_QWEN_DRY_RUN",
            "qwen_response": summary.model_dump(mode="json"),
        },
    )
    result, _ = receive_ai_result(
        db,
        task_id=ai_task.id,
        payload=callback,
        idempotency_key=f"wr_qwen_dry_run_result_{payload['task_id']}",
    )
    attach_ai_result_to_session(
        db,
        session_id=payload["session_id"],
        payload=WeeklyReviewAttachAIResultRequest(ai_result_id=result.id),
        idempotency_key=f"wr_qwen_dry_run_attach_{payload['session_id']}_{result.id}",
        request_method="POST",
        request_path=payload["wr_attach_url"],
    )
    return result


def run_wr_answers_integrate(db: Session, *, ai_task: AITask) -> AIResult:
    """Ported IMPERIUM_WR_ANSWERS_INTEGRATE_QWEN_DRY_RUN: callback → attach."""
    payload = dict(ai_task.prepared_payload or {})
    _validate_payload(
        payload, required=_ANSWERS_REQUIRED_FIELDS, task_type=ANSWERS_INTEGRATE_TASK_TYPE
    )

    callback = AIResultCallback(
        result_type="weekly_report.draft",
        result_payload={
            "title": "Draft WR from dry-run answer integration",
            "summary": "Dry-run draft generated after integrating the latest WR answer.",
            "sections": [
                {
                    "title": "Answer integration dry-run",
                    "content": (
                        f"User answer captured for message {payload['user_message_id']}: "
                        f"{payload['user_answer']}"
                    ),
                }
            ],
            "questions_answered": [
                {
                    "message_id": payload["user_message_id"],
                    "answer": payload["user_answer"],
                }
            ],
            "source": "qwen_dry_run_answers_integrate",
        },
        model_used=resolve_model_id(LOCAL_EXECUTOR_ROLE, db=db),
        provider="qwen-dry-run",
        confidence=0.7,
        raw_payload={
            "workflow": "IMPERIUM_WR_ANSWERS_INTEGRATE_QWEN_DRY_RUN",
            "dry_run": True,
        },
    )
    result, _ = receive_ai_result(
        db,
        task_id=ai_task.id,
        payload=callback,
        idempotency_key=f"wr_qwen_dry_run_result_{payload['task_id']}",
    )
    attach_ai_result_to_session(
        db,
        session_id=payload["session_id"],
        payload=WeeklyReviewAttachAIResultRequest(ai_result_id=result.id),
        idempotency_key=(
            f"wr_answers_integrate_attach_{payload['session_id']}_{result.id}"
        ),
        request_method="POST",
        request_path=payload["wr_attach_url"],
    )
    return result
