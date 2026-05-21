from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Response, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.ai import (
    AITaskRunningResponse,
    AIResultValidationCreate,
    AIResultValidationRead,
    AITaskCreate,
    AITaskRead,
    QwenRoutingDecision,
    QwenSmokeRequest,
    QwenWeeklySummary,
)
from app.services.ai.providers.qwen import QwenClient, QwenProviderError
from app.services.ai.tasks import (
    AIIdempotencyConflictError,
    AIResultNotFoundError,
    AIStateConflictError,
    AITaskNotFoundError,
    AIValidationError,
    create_ai_task,
    get_ai_task,
    mark_ai_task_running,
    reject_ai_result,
    validate_ai_result,
)

router = APIRouter()


@router.post("/qwen/smoke", response_model=QwenRoutingDecision | QwenWeeklySummary)
def qwen_smoke_route(
    payload: QwenSmokeRequest,
    current_user: CurrentUserDep,
) -> QwenRoutingDecision | QwenWeeklySummary:
    _ = current_user
    client = QwenClient()
    try:
        if payload.mode == "weekly_summary":
            return client.generate_weekly_summary(input_payload=payload.input_payload)
        return client.classify_task(task_type=payload.task_type, input_payload=payload.input_payload)
    except QwenProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/tasks", response_model=AITaskRead, status_code=status.HTTP_201_CREATED)
def create_ai_task_route(
    payload: AITaskCreate,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AITaskRead:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    try:
        task, duplicate = create_ai_task(
            db,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
        )
    except AIIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return AITaskRead.model_validate(task)


@router.get("/tasks/{task_id}", response_model=AITaskRead)
def get_ai_task_route(task_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> AITaskRead:
    try:
        return AITaskRead.model_validate(get_ai_task(db, current_user=current_user, task_id=task_id))
    except AITaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/mark-running", response_model=AITaskRunningResponse)
def mark_ai_task_running_route(
    task_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AITaskRunningResponse:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    try:
        task, transitioned = mark_ai_task_running(db, current_user=current_user, task_id=task_id)
    except AITaskNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AIStateConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return AITaskRunningResponse(task=AITaskRead.model_validate(task), transitioned=transitioned)


@router.post("/results/{result_id}/validate", response_model=AIResultValidationRead)
def validate_ai_result_route(
    result_id: UUID,
    payload: AIResultValidationCreate,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AIResultValidationRead:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    try:
        validation = validate_ai_result(db, current_user=current_user, result_id=result_id, payload=payload)
    except AIResultNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AIValidationError as exc:
        db.rollback()
        if "terminal validation state" in str(exc):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return AIResultValidationRead.model_validate(validation)


@router.post("/results/{result_id}/reject", response_model=AIResultValidationRead)
def reject_ai_result_route(
    result_id: UUID,
    payload: AIResultValidationCreate,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AIResultValidationRead:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    try:
        validation = reject_ai_result(db, current_user=current_user, result_id=result_id, payload=payload)
    except AIResultNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AIValidationError as exc:
        db.rollback()
        if "terminal validation state" in str(exc):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return AIResultValidationRead.model_validate(validation)
