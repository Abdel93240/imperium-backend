from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUserDep, SessionDep
from app.core.config import get_settings
from app.models.imperium import ImperiumWeeklyReviewState
from app.schemas.imperium import (
    ActiveMissionResponse,
    BacklogDecisionPreviewResponse,
    BacklogMissionCreateRequest,
    BacklogMissionCreateResponse,
    BacklogMissionListResponse,
    CalendarEventCreate,
    CalendarEventDeleteResponse,
    CalendarEventRead,
    CalendarEventType,
    CompleteMissionRequest,
    CreateDailyPlanRequest,
    CreatePathItemRequest,
    DayReviewResponse,
    DailyPlanResponse,
    DailyPlanWriteResponse,
    DecisionFrameworkPrioritiesResponse,
    DecisionFrameworkPrioritiesUpdateRequest,
    DecisionFrameworkSchemaResponse,
    DecisionFrameworkScorePreviewRequest,
    DecisionFrameworkScorePreviewResponse,
    FailMissionRequest,
    FinishDayRequest,
    FinishDayResponse,
    MissionDecisionScoreRead,
    MissionCompletionResponse,
    MissionDetailResponse,
    MissionHistoryResponse,
    MissionHistoryStatus,
    MissionResponse,
    MissionWriteResponse,
    PathItemResponse,
    PathItemWriteResponse,
    PromoteBacklogMissionResponse,
    PriorityRuleResponse,
    PriorityRulesResponse,
    ReplacePriorityRulesRequest,
    SkipPathItemRequest,
    StartMissionRequest,
    WeeklyReportResponse,
    WeeklyReviewStateResponse,
)
from app.schemas.ai import (
    AIMemoryArchiveRequest,
    AIMemoryListResponse,
    AIMemoryRead,
    AIMemorySchemaHealth,
    AIMemorySupersedeRequest,
)
from app.schemas.weekly_review import (
    WeeklyReviewAnswerRequest,
    WeeklyReviewCancelRequest,
    WeeklyReviewChatConfirmRequest,
    WeeklyReviewConversationRead,
    WeeklyReviewCurrentResponse,
    WeeklyReviewDebugStatusRead,
    WeeklyReviewDraftCreate,
    WeeklyReviewDraftRejectRequest,
    WeeklyReviewDraftRead,
    WeeklyReviewFinalApproveRequest,
    WeeklyReviewFinalReportRead,
    WeeklyReviewHistoryResponse,
    WeeklyReviewMemoryCandidatesPreviewResponse,
    WeeklyReviewMemoryCandidatesResponse,
    WeeklyReviewMemoryCandidateApproveRequest,
    WeeklyReviewMemoryCandidateDecisionRead,
    WeeklyReviewMemoryCandidateDecisionsResponse,
    WeeklyReviewMemoryCandidateEditRequest,
    WeeklyReviewMemoryCandidateRejectRequest,
    WeeklyReviewMemoryCommitDryRunRead,
    WeeklyReviewMemoryCommitDryRunRequest,
    WeeklyReviewMemoryCommitRead,
    WeeklyReviewMemoryCommitRequest,
    WeeklyReviewMemoryCommitPreviewRead,
    WeeklyReviewMessageCreate,
    WeeklyReviewMessageRead,
    WeeklyReviewRevisionRequest,
    WeeklyReviewSessionRead,
    WeeklyReviewStoredFinalReportsResponse,
)
from app.services.imperium.calendar import (
    CalendarEventIdempotencyConflictError,
    CalendarEventNotFoundError,
    CalendarEventValidationError,
    create_calendar_event,
    delete_calendar_event,
    list_calendar_events,
)
from app.services.ai.memories import (
    AIMemoryIdempotencyConflictError,
    AIMemoryNotFoundError,
    AIMemoryValidationError,
    archive_ai_memory,
    get_ai_memories,
    get_ai_memory,
    get_ai_memory_schema_health,
    supersede_ai_memory,
)
from app.services.imperium.day_finish import (
    DayAlreadyFinishedError,
    IdempotencyConflictError as DayIdempotencyConflictError,
    finish_day,
    get_latest_day_review,
)
from app.services.imperium.daily_plans import (
    DailyPlanAlreadyExistsError,
    DailyPlanNotFoundError,
    DailyPlanStateConflictError,
    IdempotencyConflictError as DailyPlanIdempotencyConflictError,
    activate_daily_plan,
    cancel_daily_plan,
    complete_daily_plan,
    create_daily_plan,
    get_daily_plan_for_date,
    get_today_daily_plan,
)
from app.services.imperium.decision_framework import (
    DecisionFrameworkIdempotencyConflictError,
    DecisionFrameworkValidationError,
    get_decision_framework_schema,
    get_canonical_priority_order,
    get_or_initialize_user_priorities,
    get_user_priority_context,
    preview_decision_framework_score,
    replace_user_priorities,
)
from app.services.imperium.missions import (
    ActiveMissionExistsError,
    IdempotencyConflictError as MissionIdempotencyConflictError,
    MissionNotFoundError,
    MissionStateConflictError,
    MultipleActiveMissionsError,
    complete_mission,
    create_backlog_mission,
    fail_mission,
    get_backlog_decision_preview,
    get_current_active_mission,
    get_current_mission,
    get_mission_detail,
    get_mission_history,
    get_mission_decision_score,
    get_recent_missions,
    list_backlog_missions,
    promote_backlog_mission,
    start_mission,
)
from app.services.imperium.path_items import (
    IdempotencyConflictError as PathItemIdempotencyConflictError,
    PathItemNotFoundError,
    cancel_path_item,
    complete_path_item,
    create_path_item,
    get_path_items_for_day,
    get_recent_path_items,
    get_today_path_items,
    skip_path_item,
    start_path_item,
)
from app.services.imperium.weekly_report import (
    InvalidWeekStartError,
    get_weekly_report,
)
from app.services.imperium.weekly_review_conversation import (
    InvalidWeekStartError as WeeklyReviewConversationInvalidWeekStartError,
    WeeklyReviewAIResultConflictError,
    WeeklyReviewFinalReportNotFoundError,
    WeeklyReviewIdempotencyConflictError,
    WeeklyReviewSessionNotFoundError,
    WeeklyReviewStateConflictError,
    add_weekly_review_chat_message,
    add_user_message,
    approve_latest_draft_report,
    approve_final_report,
    approve_weekly_review_memory_candidate,
    cancel_weekly_review,
    confirm_weekly_review_no_more_input,
    commit_weekly_review_memory_candidates,
    create_or_update_final_draft,
    dry_run_weekly_review_memory_commit,
    edit_weekly_review_memory_candidate,
    get_current_weekly_review,
    get_stored_weekly_review_final_reports,
    get_weekly_review_final_report,
    get_weekly_review_final_report_by_id,
    get_weekly_review_final_report_markdown,
    get_weekly_review_history,
    get_weekly_review_memory_candidates,
    get_weekly_review_memory_candidates_by_report_id,
    get_weekly_review_memory_candidate_decisions,
    get_weekly_review_memory_commit_ready_candidates,
    get_weekly_review_memory_commit_ready_candidates_by_report_id,
    get_weekly_review_memory_candidates_preview,
    get_weekly_review_debug_status,
    get_weekly_review_conversation,
    get_weekly_review_messages,
    get_weekly_review_session,
    launch_weekly_review_session,
    reject_latest_draft_report,
    reject_weekly_review_memory_candidate,
    request_draft_changes,
    request_revision,
    store_approved_final_report,
)

router = APIRouter()

_DECISION_FRAMEWORK_PRIORITY_LABELS = {
    "religious": "Religious",
    "business": "Business",
    "finance": "Finance",
    "health": "Health",
}


def _decision_framework_priority_label(domain: str) -> str:
    return _DECISION_FRAMEWORK_PRIORITY_LABELS.get(domain, domain.replace("_", " ").title())


@router.get("/decision-framework/schema", response_model=DecisionFrameworkSchemaResponse)
def decision_framework_schema_route(current_user: CurrentUserDep) -> DecisionFrameworkSchemaResponse:
    _ = current_user
    return get_decision_framework_schema()


@router.get("/decision-framework/priorities", response_model=DecisionFrameworkPrioritiesResponse)
def get_decision_framework_priorities_route(
    current_user: CurrentUserDep,
    db: SessionDep,
) -> DecisionFrameworkPrioritiesResponse:
    return get_or_initialize_user_priorities(db, current_user=current_user)


@router.post("/decision-framework/priorities", response_model=DecisionFrameworkPrioritiesResponse)
def replace_decision_framework_priorities_route(
    payload: DecisionFrameworkPrioritiesUpdateRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DecisionFrameworkPrioritiesResponse:
    _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = replace_user_priorities(
            db,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except DecisionFrameworkValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except DecisionFrameworkIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Decision framework priority conflict.") from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post("/decision-framework/score-preview", response_model=DecisionFrameworkScorePreviewResponse)
def decision_framework_score_preview_route(
    payload: DecisionFrameworkScorePreviewRequest,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> DecisionFrameworkScorePreviewResponse:
    try:
        priorities = get_user_priority_context(db, current_user=current_user)
        return preview_decision_framework_score(payload, priorities=priorities)
    except DecisionFrameworkValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/memories/schema", response_model=AIMemorySchemaHealth)
def memories_schema_route(current_user: CurrentUserDep) -> AIMemorySchemaHealth:
    _ = current_user
    return get_ai_memory_schema_health()


@router.get("/memories", response_model=AIMemoryListResponse)
def memories_index_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: Annotated[str | None, Query(pattern="^(active|archived|superseded|deleted|all)$")] = "active",
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
    return get_ai_memories(
        db,
        current_user=current_user,
        limit=limit,
        offset=offset,
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


@router.post("/memories/{memory_id}/archive", response_model=AIMemoryRead)
def archive_memory_route(
    memory_id: UUID,
    payload: AIMemoryArchiveRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AIMemoryRead:
    _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = archive_ai_memory(
            db,
            current_user=current_user,
            memory_id=memory_id,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except AIMemoryNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (AIMemoryValidationError, AIMemoryIdempotencyConflictError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post("/memories/{memory_id}/supersede", response_model=AIMemoryRead)
def supersede_memory_route(
    memory_id: UUID,
    payload: AIMemorySupersedeRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AIMemoryRead:
    _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = supersede_ai_memory(
            db,
            current_user=current_user,
            memory_id=memory_id,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except AIMemoryNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (AIMemoryValidationError, AIMemoryIdempotencyConflictError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/memories/{memory_id}", response_model=AIMemoryRead)
def memory_detail_route(memory_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> AIMemoryRead:
    try:
        return get_ai_memory(db, current_user=current_user, memory_id=memory_id)
    except AIMemoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/calendar/events",
    response_model=CalendarEventRead,
    status_code=status.HTTP_201_CREATED,
)
def create_calendar_event_route(
    payload: CalendarEventCreate,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> CalendarEventRead:
    _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = create_calendar_event(
            db,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except CalendarEventIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Calendar event or event log conflicts with an existing record.",
        ) from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/calendar/events", response_model=list[CalendarEventRead])
def list_calendar_events_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query(alias="to")] = None,
    event_type: CalendarEventType | None = None,
) -> list[CalendarEventRead]:
    try:
        events = list_calendar_events(
            db,
            current_user=current_user,
            starts_from=from_,
            starts_to=to,
            event_type=event_type,
        )
    except CalendarEventValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return [CalendarEventRead.model_validate(event) for event in events]


@router.delete("/calendar/events/{event_id}", response_model=CalendarEventDeleteResponse)
def delete_calendar_event_route(
    event_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> CalendarEventDeleteResponse:
    try:
        deleted_id = delete_calendar_event(db, current_user=current_user, event_id=event_id)
    except CalendarEventNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CalendarEventDeleteResponse(id=deleted_id, status="deleted")


@router.get("/report/week", response_model=WeeklyReportResponse)
def weekly_report_route(
    week_start: date,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> WeeklyReportResponse:
    try:
        return get_weekly_report(db, current_user=current_user, week_start=week_start)
    except InvalidWeekStartError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/day/finish", response_model=FinishDayResponse, status_code=status.HTTP_201_CREATED)
def finish_day_route(
    payload: FinishDayRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> FinishDayResponse:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Idempotency-Key header.",
        )

    try:
        result, duplicate = finish_day(
            db,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except DayAlreadyFinishedError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DayIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Day review or event conflicts with an existing record.",
        ) from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/day/latest", response_model=DayReviewResponse)
def latest_day_review_route(current_user: CurrentUserDep, db: SessionDep) -> DayReviewResponse:
    review = get_latest_day_review(db, current_user=current_user)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No day review found.")
    return DayReviewResponse.model_validate(review)


@router.post("/day/plan", response_model=DailyPlanWriteResponse, status_code=status.HTTP_201_CREATED)
def create_daily_plan_route(
    payload: CreateDailyPlanRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DailyPlanWriteResponse:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")

    try:
        result, duplicate = create_daily_plan(
            db,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except DailyPlanAlreadyExistsError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DailyPlanIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Daily plan or event conflicts with an existing record.",
        ) from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/day/plan/today", response_model=DailyPlanResponse)
def today_daily_plan_route(current_user: CurrentUserDep, db: SessionDep) -> DailyPlanResponse:
    plan = get_today_daily_plan(db, current_user=current_user)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No daily plan found.")
    return DailyPlanResponse.model_validate(plan)


@router.get("/day/plan", response_model=DailyPlanResponse)
def get_daily_plan_route(
    local_date: date,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> DailyPlanResponse:
    plan = get_daily_plan_for_date(db, current_user=current_user, local_date=local_date)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No daily plan found.")
    return DailyPlanResponse.model_validate(plan)


@router.post("/day/plan/{plan_id}/activate", response_model=DailyPlanWriteResponse)
def activate_daily_plan_route(
    plan_id: UUID,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DailyPlanWriteResponse:
    return _transition_daily_plan_route(
        plan_id=plan_id,
        request=request,
        response=response,
        current_user=current_user,
        db=db,
        idempotency_key=idempotency_key,
        transition=activate_daily_plan,
    )


@router.post("/day/plan/{plan_id}/complete", response_model=DailyPlanWriteResponse)
def complete_daily_plan_route(
    plan_id: UUID,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DailyPlanWriteResponse:
    return _transition_daily_plan_route(
        plan_id=plan_id,
        request=request,
        response=response,
        current_user=current_user,
        db=db,
        idempotency_key=idempotency_key,
        transition=complete_daily_plan,
    )


@router.post("/day/plan/{plan_id}/cancel", response_model=DailyPlanWriteResponse)
def cancel_daily_plan_route(
    plan_id: UUID,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DailyPlanWriteResponse:
    return _transition_daily_plan_route(
        plan_id=plan_id,
        request=request,
        response=response,
        current_user=current_user,
        db=db,
        idempotency_key=idempotency_key,
        transition=cancel_daily_plan,
    )


def _transition_daily_plan_route(
    *,
    plan_id: UUID,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: str | None,
    transition,
) -> DailyPlanWriteResponse:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")

    try:
        result, duplicate = transition(
            db,
            current_user=current_user,
            plan_id=plan_id,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except DailyPlanNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DailyPlanStateConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DailyPlanIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/path/today", response_model=list[PathItemResponse])
def path_today_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    timezone: str = "Europe/Paris",
) -> list[PathItemResponse]:
    items = get_today_path_items(db, current_user=current_user, timezone=timezone)
    return [PathItemResponse.model_validate(item) for item in items]


@router.get("/path/day", response_model=list[PathItemResponse])
def path_day_route(
    local_date: date,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> list[PathItemResponse]:
    items = get_path_items_for_day(db, current_user=current_user, local_date=local_date)
    return [PathItemResponse.model_validate(item) for item in items]


@router.get("/path/recent", response_model=list[PathItemResponse])
def path_recent_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[PathItemResponse]:
    items = get_recent_path_items(db, current_user=current_user, limit=limit)
    return [PathItemResponse.model_validate(item) for item in items]


@router.post(
    "/path/items",
    response_model=PathItemWriteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_path_item_route(
    payload: CreatePathItemRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PathItemWriteResponse:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")

    try:
        result, duplicate = create_path_item(
            db,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except PathItemIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Path item or event conflicts with an existing record.",
        ) from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post("/path/items/{item_id}/start", response_model=PathItemWriteResponse)
def start_path_item_route(
    item_id: UUID,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PathItemWriteResponse:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")

    try:
        result, duplicate = start_path_item(
            db,
            current_user=current_user,
            item_id=item_id,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except PathItemNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PathItemIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post("/path/items/{item_id}/complete", response_model=PathItemWriteResponse)
def complete_path_item_route(
    item_id: UUID,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PathItemWriteResponse:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")

    try:
        result, duplicate = complete_path_item(
            db,
            current_user=current_user,
            item_id=item_id,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except PathItemNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PathItemIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post("/path/items/{item_id}/skip", response_model=PathItemWriteResponse)
def skip_path_item_route(
    item_id: UUID,
    payload: SkipPathItemRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PathItemWriteResponse:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")

    try:
        result, duplicate = skip_path_item(
            db,
            current_user=current_user,
            item_id=item_id,
            skip_reason=payload.skip_reason,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except PathItemNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PathItemIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post("/path/items/{item_id}/cancel", response_model=PathItemWriteResponse)
def cancel_path_item_route(
    item_id: UUID,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PathItemWriteResponse:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")

    try:
        result, duplicate = cancel_path_item(
            db,
            current_user=current_user,
            item_id=item_id,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except PathItemNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PathItemIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post(
    "/missions/start",
    response_model=MissionWriteResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_mission_route(
    payload: StartMissionRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> MissionWriteResponse:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Idempotency-Key header.",
        )

    try:
        result, duplicate = start_mission(
            db,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except ActiveMissionExistsError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except MissionIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DecisionFrameworkValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mission or event conflicts with an existing record.",
        ) from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post(
    "/missions/backlog",
    response_model=BacklogMissionCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_backlog_mission_route(
    payload: BacklogMissionCreateRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> BacklogMissionCreateResponse:
    _require_idempotency_key(idempotency_key)

    try:
        result, duplicate = create_backlog_mission(
            db,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except MissionIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DecisionFrameworkValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mission or event conflicts with an existing record.",
        ) from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/missions/backlog", response_model=BacklogMissionListResponse)
def backlog_missions_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    domain: Annotated[
        str | None,
        Query(pattern="^(religious|business|finance|health)$"),
    ] = None,
    priority_level: Annotated[int | None, Query(ge=1, le=10)] = None,
) -> BacklogMissionListResponse:
    return list_backlog_missions(
        db,
        current_user=current_user,
        limit=limit,
        offset=offset,
        domain=domain,
        priority_level=priority_level,
    )


@router.get(
    "/missions/backlog/decision-preview",
    response_model=BacklogDecisionPreviewResponse,
    response_model_exclude_none=True,
)
def backlog_decision_preview_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    domain: Annotated[
        str | None,
        Query(pattern="^(religious|business|finance|health)$"),
    ] = None,
    priority_level: Annotated[int | None, Query(ge=1, le=10)] = None,
    include_reasons: bool = True,
) -> BacklogDecisionPreviewResponse:
    return get_backlog_decision_preview(
        db,
        current_user=current_user,
        limit=limit,
        domain=domain,
        priority_level=priority_level,
        include_reasons=include_reasons,
    )


@router.post("/missions/backlog/{mission_id}/promote", response_model=PromoteBacklogMissionResponse)
def promote_backlog_mission_route(
    mission_id: UUID,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PromoteBacklogMissionResponse:
    _require_idempotency_key(idempotency_key)

    try:
        result, duplicate = promote_backlog_mission(
            db,
            current_user=current_user,
            mission_id=mission_id,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except MissionNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ActiveMissionExistsError, MissionStateConflictError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except MissionIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mission or event conflicts with an existing record.",
        ) from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post("/missions/{mission_id}/complete", response_model=MissionCompletionResponse)
def complete_mission_route(
    mission_id: UUID,
    payload: CompleteMissionRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> MissionCompletionResponse:
    _require_idempotency_key(idempotency_key)

    try:
        result, duplicate = complete_mission(
            db,
            current_user=current_user,
            mission_id=mission_id,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except MissionNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MissionStateConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except MissionIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mission or event conflicts with an existing record.",
        ) from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post("/missions/{mission_id}/fail", response_model=MissionWriteResponse)
def fail_mission_route(
    mission_id: UUID,
    payload: FailMissionRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> MissionWriteResponse:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Idempotency-Key header.",
        )

    try:
        result, duplicate = fail_mission(
            db,
            current_user=current_user,
            mission_id=mission_id,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except MissionNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MissionStateConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except MissionIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mission or event conflicts with an existing record.",
        ) from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/missions/current", response_model=MissionResponse)
def current_mission_route(current_user: CurrentUserDep, db: SessionDep) -> MissionResponse:
    mission = get_current_mission(db, current_user=current_user)
    if mission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active mission found.")
    return MissionResponse.model_validate(mission)


@router.get("/missions/active", response_model=ActiveMissionResponse)
def active_mission_route(current_user: CurrentUserDep, db: SessionDep) -> ActiveMissionResponse:
    try:
        return get_current_active_mission(db, current_user=current_user)
    except MultipleActiveMissionsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Multiple active missions found for current user.",
        ) from exc


@router.get("/missions/history", response_model=MissionHistoryResponse)
def mission_history_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_filter: Annotated[MissionHistoryStatus | None, Query(alias="status")] = None,
    domain: Annotated[str | None, Query()] = None,
    priority_level: Annotated[int | None, Query(ge=1, le=10)] = None,
    started_after: Annotated[datetime | None, Query()] = None,
    ended_before: Annotated[datetime | None, Query()] = None,
) -> MissionHistoryResponse:
    return get_mission_history(
        db,
        current_user=current_user,
        limit=limit,
        offset=offset,
        status=status_filter,
        domain=domain,
        priority_level=priority_level,
        started_after=started_after,
        ended_before=ended_before,
    )


@router.get("/missions/recent", response_model=list[MissionResponse])
def recent_missions_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[MissionResponse]:
    missions = get_recent_missions(db, current_user=current_user, limit=limit)
    return [MissionResponse.model_validate(mission) for mission in missions]


@router.get(
    "/missions/{mission_id}",
    response_model=MissionDetailResponse,
    response_model_exclude_none=True,
)
def mission_detail_route(
    mission_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> MissionDetailResponse:
    try:
        return get_mission_detail(db, current_user=current_user, mission_id=mission_id)
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/missions/{mission_id}/decision-score",
    response_model=MissionDecisionScoreRead,
    response_model_exclude_none=True,
)
def mission_decision_score_route(
    mission_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
    include_reasons: bool = True,
) -> MissionDecisionScoreRead:
    try:
        return get_mission_decision_score(
            db,
            current_user=current_user,
            mission_id=mission_id,
            include_reasons=include_reasons,
        )
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/priorities", response_model=PriorityRulesResponse)
def get_priorities_route(current_user: CurrentUserDep, db: SessionDep) -> PriorityRulesResponse:
    """Deprecated legacy priority read.

    Decision Framework priorities in `imperium_user_priorities` are canonical.
    This route remains only as a compatibility projection for old clients.
    """

    priorities = get_canonical_priority_order(db, current_user=current_user, persist_defaults=True)
    return PriorityRulesResponse(
        priorities=[
            PriorityRuleResponse(
                id=priority.id,
                priority_key=priority.domain,
                label=_decision_framework_priority_label(priority.domain),
                rank_order=priority.position,
                importance_score=None,
                is_active=priority.is_active,
                updated_by_event_id=None,
                created_at=priority.created_at,
                updated_at=priority.updated_at,
            )
            for priority in priorities
        ],
        status="legacy_superseded",
        deprecated=True,
        legacy=True,
        superseded_by="/api/imperium/decision-framework/priorities",
        canonical_source="imperium_user_priorities",
        message="Legacy priority rules are superseded; Decision Framework priorities are canonical.",
    )


@router.post("/priorities", response_model=PriorityRulesResponse)
def replace_priorities_route(
    payload: ReplacePriorityRulesRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PriorityRulesResponse:
    """Deprecated legacy priority write.

    Decision Framework priorities in `imperium_user_priorities` are canonical.
    Legacy `imperium_priority_rules` writes are blocked to prevent two active
    hierarchy writers from coexisting.
    """

    _ = (payload, request, response, current_user, db, idempotency_key)
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "status": "legacy_superseded",
            "deprecated": True,
            "legacy": True,
            "superseded_by": "/api/imperium/decision-framework/priorities",
            "canonical_source": "imperium_user_priorities",
            "message": "Use Decision Framework priorities; legacy priority rule writes are disabled.",
        },
    )


@router.get("/weekly-review/state", response_model=WeeklyReviewStateResponse | None)
def weekly_review_state_route(
    week_start: date,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> WeeklyReviewStateResponse | None:
    if week_start.weekday() != 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="week_start must be a Monday.",
        )
    state = db.scalar(
        select(ImperiumWeeklyReviewState).where(
            ImperiumWeeklyReviewState.user_id == current_user.id,
            ImperiumWeeklyReviewState.week_start == week_start,
        )
    )
    if state is None:
        return None
    return WeeklyReviewStateResponse.model_validate(state)


@router.post(
    "/weekly-review/launch",
    response_model=WeeklyReviewSessionRead,
    status_code=status.HTTP_201_CREATED,
)
def launch_weekly_review_route(
    week_start: date,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WeeklyReviewSessionRead:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")

    try:
        result, duplicate = launch_weekly_review_session(
            db,
            current_user=current_user,
            week_start=week_start,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except WeeklyReviewConversationInvalidWeekStartError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except WeeklyReviewStateConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WeeklyReviewIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/weekly-review/session", response_model=WeeklyReviewSessionRead)
def get_weekly_review_session_route(
    week_start: date,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> WeeklyReviewSessionRead:
    try:
        session = get_weekly_review_session(db, current_user=current_user, week_start=week_start)
    except WeeklyReviewConversationInvalidWeekStartError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Weekly review session not found.")
    return WeeklyReviewSessionRead.model_validate(session)


@router.get("/weekly-review/current", response_model=WeeklyReviewCurrentResponse)
def get_current_weekly_review_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    week_start: date | None = None,
    messages_limit: Annotated[int, Query(ge=1, le=500)] = 200,
    final_reports_limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> WeeklyReviewCurrentResponse:
    try:
        return get_current_weekly_review(
            db,
            current_user=current_user,
            week_start=week_start,
            messages_limit=messages_limit,
            final_reports_limit=final_reports_limit,
        )
    except WeeklyReviewConversationInvalidWeekStartError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/weekly-review/history", response_model=WeeklyReviewHistoryResponse)
def get_weekly_review_history_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    stored_only: bool = False,
) -> WeeklyReviewHistoryResponse:
    return get_weekly_review_history(
        db,
        current_user=current_user,
        limit=limit,
        offset=offset,
        status=status_filter,
        stored_only=stored_only,
    )


@router.get("/weekly-review/final-reports/stored", response_model=WeeklyReviewStoredFinalReportsResponse)
def get_stored_weekly_review_final_reports_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> WeeklyReviewStoredFinalReportsResponse:
    return get_stored_weekly_review_final_reports(
        db,
        current_user=current_user,
        limit=limit,
        offset=offset,
    )


@router.get("/weekly-review/memory-candidates/preview", response_model=WeeklyReviewMemoryCandidatesPreviewResponse)
def preview_weekly_review_memory_candidates_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    include_rejected: bool = False,
) -> WeeklyReviewMemoryCandidatesPreviewResponse:
    return get_weekly_review_memory_candidates_preview(
        db,
        current_user=current_user,
        limit=limit,
        offset=offset,
        include_rejected=include_rejected,
    )


@router.get("/weekly-review/memory-candidates/decisions", response_model=WeeklyReviewMemoryCandidateDecisionsResponse)
def get_weekly_review_memory_candidate_decisions_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    decision: Annotated[str | None, Query(pattern="^(approved|rejected|edited)$")] = None,
) -> WeeklyReviewMemoryCandidateDecisionsResponse:
    return get_weekly_review_memory_candidate_decisions(
        db,
        current_user=current_user,
        limit=limit,
        offset=offset,
        decision=decision,
    )


@router.get("/weekly-review/memory-candidates/commit-ready", response_model=WeeklyReviewMemoryCommitPreviewRead)
def get_weekly_review_memory_commit_ready_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> WeeklyReviewMemoryCommitPreviewRead:
    return get_weekly_review_memory_commit_ready_candidates(
        db,
        current_user=current_user,
        limit=limit,
        offset=offset,
    )


@router.post("/weekly-review/memory-candidates/commit-dry-run", response_model=WeeklyReviewMemoryCommitDryRunRead)
def dry_run_weekly_review_memory_commit_route(
    payload: WeeklyReviewMemoryCommitDryRunRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WeeklyReviewMemoryCommitDryRunRead:
    _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = dry_run_weekly_review_memory_commit(
            db,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except WeeklyReviewIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post("/weekly-review/memory-candidates/commit", response_model=WeeklyReviewMemoryCommitRead)
def commit_weekly_review_memory_candidates_route(
    payload: WeeklyReviewMemoryCommitRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WeeklyReviewMemoryCommitRead:
    _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = commit_weekly_review_memory_candidates(
            db,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except WeeklyReviewIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.get(
    "/weekly-review/final-reports/{report_id}/memory-candidates/commit-ready",
    response_model=WeeklyReviewMemoryCommitPreviewRead,
)
def get_weekly_review_memory_commit_ready_by_report_id_route(
    report_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> WeeklyReviewMemoryCommitPreviewRead:
    try:
        return get_weekly_review_memory_commit_ready_candidates_by_report_id(
            db,
            current_user=current_user,
            report_id=report_id,
            limit=limit,
            offset=offset,
        )
    except WeeklyReviewFinalReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/weekly-review/final-reports/{report_id}/memory-candidates", response_model=WeeklyReviewMemoryCandidatesResponse)
def get_weekly_review_memory_candidates_by_report_id_route(
    report_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> WeeklyReviewMemoryCandidatesResponse:
    try:
        return get_weekly_review_memory_candidates_by_report_id(db, current_user=current_user, report_id=report_id)
    except WeeklyReviewFinalReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/weekly-review/final-reports/{report_id}/memory-candidates/{candidate_id}/approve",
    response_model=WeeklyReviewMemoryCandidateDecisionRead,
    status_code=status.HTTP_201_CREATED,
)
def approve_weekly_review_memory_candidate_route(
    report_id: UUID,
    candidate_id: str,
    payload: WeeklyReviewMemoryCandidateApproveRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WeeklyReviewMemoryCandidateDecisionRead:
    _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = approve_weekly_review_memory_candidate(
            db,
            current_user=current_user,
            report_id=report_id,
            candidate_id=candidate_id,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except WeeklyReviewFinalReportNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (WeeklyReviewStateConflictError, WeeklyReviewIdempotencyConflictError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post(
    "/weekly-review/final-reports/{report_id}/memory-candidates/{candidate_id}/reject",
    response_model=WeeklyReviewMemoryCandidateDecisionRead,
    status_code=status.HTTP_201_CREATED,
)
def reject_weekly_review_memory_candidate_route(
    report_id: UUID,
    candidate_id: str,
    payload: WeeklyReviewMemoryCandidateRejectRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WeeklyReviewMemoryCandidateDecisionRead:
    _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = reject_weekly_review_memory_candidate(
            db,
            current_user=current_user,
            report_id=report_id,
            candidate_id=candidate_id,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except WeeklyReviewFinalReportNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (WeeklyReviewStateConflictError, WeeklyReviewIdempotencyConflictError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post(
    "/weekly-review/final-reports/{report_id}/memory-candidates/{candidate_id}/edit",
    response_model=WeeklyReviewMemoryCandidateDecisionRead,
    status_code=status.HTTP_201_CREATED,
)
def edit_weekly_review_memory_candidate_route(
    report_id: UUID,
    candidate_id: str,
    payload: WeeklyReviewMemoryCandidateEditRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WeeklyReviewMemoryCandidateDecisionRead:
    _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = edit_weekly_review_memory_candidate(
            db,
            current_user=current_user,
            report_id=report_id,
            candidate_id=candidate_id,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except WeeklyReviewFinalReportNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (WeeklyReviewStateConflictError, WeeklyReviewIdempotencyConflictError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/weekly-review/final-reports/{report_id}", response_model=WeeklyReviewFinalReportRead)
def get_weekly_review_final_report_by_id_route(
    report_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> WeeklyReviewFinalReportRead:
    try:
        return get_weekly_review_final_report_by_id(db, current_user=current_user, report_id=report_id)
    except WeeklyReviewFinalReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/weekly-review/{session_id}/final-report", response_model=WeeklyReviewFinalReportRead)
def get_weekly_review_final_report_route(
    session_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> WeeklyReviewFinalReportRead:
    try:
        return get_weekly_review_final_report(db, current_user=current_user, session_id=session_id)
    except (WeeklyReviewSessionNotFoundError, WeeklyReviewFinalReportNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/weekly-review/{session_id}/final-report/markdown", response_class=PlainTextResponse)
def get_weekly_review_final_report_markdown_route(
    session_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> PlainTextResponse:
    try:
        markdown = get_weekly_review_final_report_markdown(db, current_user=current_user, session_id=session_id)
    except (WeeklyReviewSessionNotFoundError, WeeklyReviewFinalReportNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return PlainTextResponse(markdown, media_type="text/markdown; charset=utf-8")


@router.get("/weekly-review/{session_id}/memory-candidates", response_model=WeeklyReviewMemoryCandidatesResponse)
def get_weekly_review_memory_candidates_route(
    session_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> WeeklyReviewMemoryCandidatesResponse:
    try:
        return get_weekly_review_memory_candidates(db, current_user=current_user, session_id=session_id)
    except (WeeklyReviewSessionNotFoundError, WeeklyReviewFinalReportNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/weekly-review/{session_id}/messages", response_model=list[WeeklyReviewMessageRead])
def get_weekly_review_messages_route(
    session_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> list[WeeklyReviewMessageRead]:
    try:
        messages = get_weekly_review_messages(db, current_user=current_user, session_id=session_id)
    except WeeklyReviewSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [WeeklyReviewMessageRead.model_validate(message) for message in messages]


@router.get("/weekly-review/{session_id}/conversation", response_model=WeeklyReviewConversationRead)
def get_weekly_review_conversation_route(
    session_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
    messages_limit: Annotated[int, Query(ge=1, le=500)] = 200,
    messages_before: datetime | None = None,
    final_reports_limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> WeeklyReviewConversationRead:
    try:
        return get_weekly_review_conversation(
            db,
            current_user=current_user,
            session_id=session_id,
            messages_limit=messages_limit,
            messages_before=messages_before,
            final_reports_limit=final_reports_limit,
        )
    except WeeklyReviewSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/weekly-review/{session_id}/debug-status", response_model=WeeklyReviewDebugStatusRead)
def get_weekly_review_debug_status_route(
    session_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> WeeklyReviewDebugStatusRead:
    try:
        result = get_weekly_review_debug_status(
            db,
            current_user=current_user,
            session_id=session_id,
            limit=limit,
        )
        if get_settings().environment not in {"local", "test"}:
            return _sanitize_weekly_review_debug_status(result)
        return result
    except WeeklyReviewSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _sanitize_weekly_review_debug_status(result: WeeklyReviewDebugStatusRead) -> WeeklyReviewDebugStatusRead:
    """Remove provider/debug internals from public debug-status outside local/test."""
    sanitized = result.model_copy(deep=True)
    for task in [sanitized.current_ai_task, *sanitized.recent_ai_tasks]:
        if task is None:
            continue
        task.model_hint = None
        task.privacy_level = None
        task.error_message = None
    for ai_result in sanitized.recent_ai_results:
        ai_result.provider = None
        ai_result.model_used = None
        ai_result.result_payload = {}
        ai_result.raw_payload_keys = []
    return sanitized


@router.post(
    "/weekly-review/{session_id}/chat/messages",
    response_model=WeeklyReviewMessageRead,
    status_code=status.HTTP_201_CREATED,
)
def post_weekly_review_chat_message_route(
    session_id: UUID,
    payload: WeeklyReviewAnswerRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WeeklyReviewMessageRead:
    _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = add_weekly_review_chat_message(
            db,
            session_id=session_id,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except WeeklyReviewSessionNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WeeklyReviewStateConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WeeklyReviewIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post(
    "/weekly-review/{session_id}/chat/confirm-no-more-input",
    response_model=WeeklyReviewSessionRead,
    status_code=status.HTTP_201_CREATED,
)
def confirm_weekly_review_no_more_input_route(
    session_id: UUID,
    payload: WeeklyReviewChatConfirmRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WeeklyReviewSessionRead:
    _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = confirm_weekly_review_no_more_input(
            db,
            session_id=session_id,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except (WeeklyReviewSessionNotFoundError, WeeklyReviewFinalReportNotFoundError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (WeeklyReviewStateConflictError, WeeklyReviewAIResultConflictError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WeeklyReviewIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post(
    "/weekly-review/{session_id}/messages",
    response_model=WeeklyReviewMessageRead,
    status_code=status.HTTP_201_CREATED,
)
def post_weekly_review_message_route(
    session_id: UUID,
    payload: WeeklyReviewMessageCreate,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WeeklyReviewMessageRead:
    _require_idempotency_key(idempotency_key)
    if payload.role != "user":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="User endpoint only accepts user messages.")
    if not payload.content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Message content is required.")
    try:
        result, duplicate = add_user_message(
            db,
            session_id=session_id,
            current_user=current_user,
            payload=WeeklyReviewAnswerRequest(content=payload.content, payload=payload.payload),
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except WeeklyReviewSessionNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WeeklyReviewStateConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WeeklyReviewIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post(
    "/weekly-review/{session_id}/answer",
    response_model=WeeklyReviewMessageRead,
    status_code=status.HTTP_201_CREATED,
)
def answer_weekly_review_route(
    session_id: UUID,
    payload: WeeklyReviewAnswerRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WeeklyReviewMessageRead:
    _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = add_user_message(
            db,
            session_id=session_id,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
            create_integration_task=True,
            trigger_type="user_message",
        )
    except WeeklyReviewSessionNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WeeklyReviewStateConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WeeklyReviewIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post(
    "/weekly-review/{session_id}/request-revision",
    response_model=WeeklyReviewMessageRead,
    status_code=status.HTTP_201_CREATED,
)
def request_weekly_review_revision_route(
    session_id: UUID,
    payload: WeeklyReviewRevisionRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WeeklyReviewMessageRead:
    _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = request_revision(
            db,
            session_id=session_id,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except WeeklyReviewSessionNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WeeklyReviewStateConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WeeklyReviewIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post(
    "/weekly-review/{session_id}/final-draft",
    response_model=WeeklyReviewDraftRead,
    status_code=status.HTTP_201_CREATED,
)
def create_weekly_review_final_draft_route(
    session_id: UUID,
    payload: WeeklyReviewDraftCreate,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WeeklyReviewDraftRead:
    _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = create_or_update_final_draft(
            db,
            session_id=session_id,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except WeeklyReviewSessionNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WeeklyReviewAIResultConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WeeklyReviewStateConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WeeklyReviewIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post("/weekly-review/{session_id}/draft/approve", response_model=WeeklyReviewFinalReportRead)
def approve_weekly_review_draft_route(
    session_id: UUID,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WeeklyReviewFinalReportRead:
    _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = approve_latest_draft_report(
            db,
            session_id=session_id,
            current_user=current_user,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except (WeeklyReviewSessionNotFoundError, WeeklyReviewFinalReportNotFoundError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WeeklyReviewStateConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WeeklyReviewIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post("/weekly-review/{session_id}/draft/reject", response_model=WeeklyReviewFinalReportRead)
def reject_weekly_review_draft_route(
    session_id: UUID,
    payload: WeeklyReviewDraftRejectRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WeeklyReviewFinalReportRead:
    _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = reject_latest_draft_report(
            db,
            session_id=session_id,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except (WeeklyReviewSessionNotFoundError, WeeklyReviewFinalReportNotFoundError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WeeklyReviewStateConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WeeklyReviewIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post(
    "/weekly-review/{session_id}/draft/request-changes",
    response_model=WeeklyReviewMessageRead,
    status_code=status.HTTP_201_CREATED,
)
def request_weekly_review_draft_changes_route(
    session_id: UUID,
    payload: WeeklyReviewAnswerRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WeeklyReviewMessageRead:
    _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = request_draft_changes(
            db,
            session_id=session_id,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except (WeeklyReviewSessionNotFoundError, WeeklyReviewFinalReportNotFoundError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WeeklyReviewStateConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WeeklyReviewIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post("/weekly-review/{session_id}/draft/store", response_model=WeeklyReviewFinalReportRead)
def store_weekly_review_draft_route(
    session_id: UUID,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WeeklyReviewFinalReportRead:
    _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = store_approved_final_report(
            db,
            session_id=session_id,
            current_user=current_user,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except (WeeklyReviewSessionNotFoundError, WeeklyReviewFinalReportNotFoundError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WeeklyReviewStateConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WeeklyReviewIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post("/weekly-review/{session_id}/approve", response_model=WeeklyReviewFinalReportRead)
def approve_weekly_review_route(
    session_id: UUID,
    payload: WeeklyReviewFinalApproveRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WeeklyReviewFinalReportRead:
    _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = approve_final_report(
            db,
            session_id=session_id,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except (WeeklyReviewSessionNotFoundError, WeeklyReviewFinalReportNotFoundError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WeeklyReviewStateConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WeeklyReviewIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post("/weekly-review/{session_id}/cancel", response_model=WeeklyReviewSessionRead)
def cancel_weekly_review_route(
    session_id: UUID,
    payload: WeeklyReviewCancelRequest,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WeeklyReviewSessionRead:
    _require_idempotency_key(idempotency_key)
    try:
        result, duplicate = cancel_weekly_review(
            db,
            session_id=session_id,
            current_user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
            request_method=request.method,
            request_path=request.url.path,
        )
    except WeeklyReviewSessionNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WeeklyReviewStateConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WeeklyReviewIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


def _require_idempotency_key(idempotency_key: str | None) -> None:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
