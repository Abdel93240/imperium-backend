from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

def _validate_monday(value: date) -> date:
    if value.weekday() != 0:
        raise ValueError("week_start must be a Monday.")
    return value


class WeeklyReviewSessionLaunchRequest(BaseModel):
    week_start: date

    @field_validator("week_start")
    @classmethod
    def week_start_must_be_monday(cls, value: date) -> date:
        return _validate_monday(value)


class WeeklyReviewSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    week_start: date
    week_end: date
    status: str
    launched_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    error_code: str | None
    error_message: str | None
    current_ai_task_id: UUID | None
    initial_ai_result_id: UUID | None
    final_ai_result_id: UUID | None
    created_at: datetime
    updated_at: datetime


class WeeklyReviewMessageCreate(BaseModel):
    """User-facing schema. Role is locked to 'user'; backend code paths must use
    WeeklyReviewMessageCreateInternal for non-user messages."""

    role: Literal["user"] = "user"
    message_type: Literal["user_answer", "chat_message", "revision_request"] = "user_answer"
    content: str | None = Field(default=None, max_length=12000)
    payload: dict | None = None
    ai_task_id: UUID | None = None
    ai_result_id: UUID | None = None


class WeeklyReviewMessageCreateInternal(BaseModel):
    """Backend-only schema. Permissive role regex preserved from the original
    WeeklyReviewMessageCreate — must never be wired to a user-facing route."""

    role: str = Field(default="user", pattern=r"^(user|qwen|system|opus|backend)$")
    message_type: str = Field(
        default="user_answer",
        pattern=(
            r"^(user_answer|clarification_question|initial_summary|draft|revision_request|final_report|system_note|"
            r"chat_message|assistant_followup|final_report_draft)$"
        ),
    )
    content: str | None = Field(default=None, max_length=12000)
    payload: dict | None = None
    ai_task_id: UUID | None = None
    ai_result_id: UUID | None = None


class WeeklyReviewMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    user_id: UUID
    role: str
    message_type: str
    content: str | None
    payload: dict | None
    ai_task_id: UUID | None
    ai_result_id: UUID | None
    created_at: datetime


class WeeklyReviewAnswerRequest(BaseModel):
    content: str = Field(min_length=1, max_length=12000)
    payload: dict | None = None


class WeeklyReviewChatConfirmRequest(BaseModel):
    content: str | None = Field(default=None, max_length=12000)
    payload: dict | None = None

    @field_validator("content")
    @classmethod
    def content_if_present_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("content must not be blank when provided.")
        return value


class WeeklyReviewDraftCreate(BaseModel):
    ai_result_id: UUID | None = None
    report_payload: dict
    report_markdown: str = Field(min_length=1, max_length=100000)
    memory_candidates: dict | list | None = None


class WeeklyReviewDraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    user_id: UUID
    week_start: date
    week_end: date
    status: str
    report_payload: dict
    report_markdown: str
    memory_candidates: dict | list | None
    approved_at: datetime | None
    stored_at: datetime | None
    source_ai_result_id: UUID | None
    created_at: datetime
    updated_at: datetime


class WeeklyReviewRevisionRequest(BaseModel):
    feedback: str = Field(min_length=1, max_length=12000)
    payload: dict | None = None


class WeeklyReviewFinalApproveRequest(BaseModel):
    final_report_id: UUID
    user_note: str | None = Field(default=None, max_length=5000)


class WeeklyReviewCancelRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=5000)


class WeeklyReviewAttachAIResultRequest(BaseModel):
    ai_result_id: UUID


class WeeklyReviewDraftRejectRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=5000)
    payload: dict | None = None


class WeeklyReviewFinalReportRead(WeeklyReviewDraftRead):
    pass


class WeeklyReviewFinalReportSummary(BaseModel):
    id: UUID
    status: str
    week_start: date
    week_end: date
    summary: str | None = None
    title: str | None = None
    approved_at: datetime | None = None
    stored_at: datetime | None = None
    source_ai_result_id: UUID | None = None
    created_at: datetime


class WeeklyReviewStoredFinalReportSummary(BaseModel):
    id: UUID
    session_id: UUID
    week_start: date
    week_end: date
    status: str
    title: str | None = None
    summary: str | None = None
    stored_at: datetime | None = None
    approved_at: datetime | None = None
    created_at: datetime
    source_ai_result_id: UUID | None = None


class WeeklyReviewStoredFinalReportsResponse(BaseModel):
    items: list[WeeklyReviewStoredFinalReportSummary]
    limit: int
    offset: int
    count: int
    has_more: bool


class WeeklyReviewMemoryCandidateRead(BaseModel):
    id: str
    kind: str
    title: str
    content: str
    confidence: float = Field(ge=0, le=1)
    source: str
    source_report_id: UUID
    source_session_id: UUID
    week_start: date
    week_end: date
    proposed_memory_scope: str
    status: str = "candidate"
    created_from: str = "weekly_review_final_report"
    decision_status: str = "undecided"
    decision_id: UUID | None = None
    decided_at: datetime | None = None
    edited_candidate: dict | None = None
    effective_candidate: dict | None = None


class WeeklyReviewMemoryCandidatesResponse(BaseModel):
    report_id: UUID
    session_id: UUID
    week_start: date
    week_end: date
    report_status: str
    candidates: list[WeeklyReviewMemoryCandidateRead]
    count: int
    storage_enabled: bool = False
    note: str = "Memory candidates are proposals only. Nothing has been written to memory."
    total_candidates: int | None = None
    rejected_hidden_count: int = 0


class WeeklyReviewMemoryCandidatesPreviewResponse(BaseModel):
    items: list[WeeklyReviewMemoryCandidatesResponse]
    limit: int
    offset: int
    count: int
    has_more: bool


class WeeklyReviewMemoryCandidateApproveRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=5000)
    payload: dict | None = None


class WeeklyReviewMemoryCandidateRejectRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=5000)
    payload: dict | None = None


class WeeklyReviewMemoryCandidateEditRequest(BaseModel):
    edited_title: str | None = Field(default=None, max_length=160)
    edited_content: str = Field(min_length=1, max_length=1200)
    edited_kind: str | None = Field(default=None, max_length=64)
    edited_confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str | None = Field(default=None, max_length=5000)
    payload: dict | None = None


class WeeklyReviewMemoryCandidateDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    report_id: UUID
    session_id: UUID
    candidate_id: str
    decision: str
    source: str
    original_candidate: dict
    edited_candidate: dict | None
    reason: str | None
    payload: dict | None
    idempotency_key: str | None
    created_at: datetime
    updated_at: datetime


class WeeklyReviewMemoryCandidateDecisionsResponse(BaseModel):
    items: list[WeeklyReviewMemoryCandidateDecisionRead]
    limit: int
    offset: int
    count: int
    has_more: bool


class WeeklyReviewMemoryCommitCandidateRead(BaseModel):
    decision_id: UUID
    report_id: UUID
    session_id: UUID
    candidate_id: str
    decision: str
    title: str
    content: str
    kind: str
    confidence: float | None
    proposed_memory_scope: str
    week_start: date
    week_end: date
    source: str
    source_report_id: UUID
    source_session_id: UUID
    effective_candidate: dict
    original_candidate: dict
    edited_candidate: dict | None = None
    readiness_status: str
    readiness_reasons: list[str]
    created_at: datetime
    updated_at: datetime


class WeeklyReviewMemoryCommitPreviewRead(BaseModel):
    items: list[WeeklyReviewMemoryCommitCandidateRead]
    limit: int
    offset: int
    count: int
    has_more: bool
    storage_enabled: bool = False
    note: str = "Commit readiness only. Nothing has been written to memory."


class WeeklyReviewMemoryCommitDryRunRequest(BaseModel):
    decision_ids: list[UUID] = Field(min_length=1, max_length=100)
    payload: dict | None = None


class WeeklyReviewMemoryCommitRequest(BaseModel):
    decision_ids: list[UUID] = Field(min_length=1, max_length=100)
    payload: dict | None = None


class WeeklyReviewMemoryCommitItem(BaseModel):
    memory_id: UUID
    decision_id: UUID
    candidate_id: str
    is_active: bool
    content: str
    memory_type: str
    learning_element_type: str | None = None
    source_domain: str
    confidence: float | None = None
    privacy_level: str
    created_at: datetime


class WeeklyReviewMemoryAlreadyCommittedItem(BaseModel):
    memory_id: UUID
    decision_id: UUID
    reason: str = "already_committed"


class WeeklyReviewMemoryCommitRead(BaseModel):
    requested_count: int
    committed_count: int
    already_committed_count: int
    blocked_count: int
    memories: list[WeeklyReviewMemoryCommitItem]
    already_committed: list[WeeklyReviewMemoryAlreadyCommittedItem]
    blocked: list[dict]
    storage_enabled: bool = False
    note: str = "Weekly Review memory commit is disabled until the embedding service is available."


class WeeklyReviewMemoryCommitDryRunRead(BaseModel):
    requested_count: int
    eligible_count: int
    blocked_count: int
    would_commit_count: int
    candidates: list[WeeklyReviewMemoryCommitCandidateRead]
    blocked: list[dict]
    storage_enabled: bool = False
    note: str = "Dry run only. Nothing has been written to memory."


class WeeklyReviewHistoryItem(BaseModel):
    session_id: UUID
    week_start: date
    week_end: date
    session_status: str
    launched_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    latest_final_report: WeeklyReviewFinalReportSummary | None = None
    has_initial_summary: bool
    has_active_or_stored_report: bool
    has_stored_report: bool
    has_superseded_reports: bool
    final_reports_count: int
    active_reports_count: int = 0
    stored_reports_count: int = 0
    superseded_reports_count: int


class WeeklyReviewHistoryResponse(BaseModel):
    items: list[WeeklyReviewHistoryItem]
    limit: int
    offset: int
    count: int
    has_more: bool


class WeeklyReviewConversationFlags(BaseModel):
    can_answer: bool
    can_send_message: bool = False
    can_confirm_no_more_input: bool = False
    can_request_revision: bool
    can_approve: bool
    can_store: bool = False
    can_request_changes: bool = False
    can_reject: bool = False
    is_waiting_for_ai: bool
    is_closed: bool = False
    has_initial_summary: bool
    has_final_draft: bool


class WeeklyReviewAIResultSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    result_type: str
    result_payload: dict
    provider: str | None
    model_used: str | None
    confidence: Decimal | None
    status: str
    created_at: datetime


class WeeklyReviewAITaskSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_type: str
    status: str
    source_module: str
    model_hint: str | None
    privacy_level: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    error_code: str | None
    error_message: str | None


class WeeklyReviewChatTimelineItem(BaseModel):
    id: str
    role: str
    type: str
    content: str | None = None
    created_at: datetime
    source_message_id: UUID | None = None
    source_report_id: UUID | None = None
    display_payload: dict | None = None
    is_final_draft: bool = False


class WeeklyReviewVisibleAIState(BaseModel):
    summary: str | None = None
    observed_signals: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    draft_plan: list[str] = Field(default_factory=list)
    current_step: str
    next_expected_user_action: str | None = None
    visible_reasoning_summary: str | None = None


class WeeklyReviewDraftReviewState(BaseModel):
    has_draft: bool = False
    active_draft_id: UUID | None = None
    active_draft_status: str | None = None
    can_approve: bool = False
    can_request_changes: bool = False
    can_store: bool = False
    latest_draft_title: str | None = None
    latest_draft_summary: str | None = None
    latest_draft_markdown_preview: str | None = None


class WeeklyReviewActionDescriptor(BaseModel):
    action: str
    label: str
    endpoint_hint: str
    method: str = "POST"
    requires_text: bool = False
    style: str
    enabled: bool
    disabled_reason: str | None = None
    confirmation_required: bool = False


class WeeklyReviewConversationRead(BaseModel):
    session: WeeklyReviewSessionRead
    messages: list[WeeklyReviewMessageRead]
    current_ai_task: WeeklyReviewAITaskSummary | None = None
    initial_ai_result: WeeklyReviewAIResultSummary | None = None
    final_ai_result: WeeklyReviewAIResultSummary | None = None
    final_reports: list[WeeklyReviewFinalReportRead] = Field(default_factory=list)
    final_report_candidates: list[WeeklyReviewFinalReportRead] = Field(default_factory=list)
    latest_final_report: WeeklyReviewFinalReportRead | None = None
    flags: WeeklyReviewConversationFlags
    allowed_actions: list[str] = Field(default_factory=list)
    ui_state: str
    chat_timeline: list[WeeklyReviewChatTimelineItem] = Field(default_factory=list)
    visible_ai_state: WeeklyReviewVisibleAIState | None = None
    latest_assistant_prompt: str | None = None
    draft_review_state: WeeklyReviewDraftReviewState | None = None
    primary_action: WeeklyReviewActionDescriptor | None = None
    secondary_actions: list[WeeklyReviewActionDescriptor] = Field(default_factory=list)


class WeeklyReviewCurrentResponse(BaseModel):
    session: WeeklyReviewSessionRead | None = None
    conversation: WeeklyReviewConversationRead | None = None


class WeeklyReviewAIResultDebugSummary(WeeklyReviewAIResultSummary):
    raw_payload_keys: list[str] = Field(default_factory=list)


class WeeklyReviewDebugStatusRead(BaseModel):
    session: WeeklyReviewSessionRead
    active_final_report_id: UUID | None = None
    active_final_report_status: str | None = None
    historical_final_report_count: int = 0
    active_final_report_count: int = 0
    active_reports_count: int = 0
    stored_reports_count: int = 0
    superseded_reports_count: int = 0
    latest_final_report_id: UUID | None = None
    latest_stored_report_id: UUID | None = None
    latest_active_report_id: UUID | None = None
    latest_user_message_id: UUID | None = None
    latest_revision_request_id: UUID | None = None
    latest_answer_integration_task_id: UUID | None = None
    current_ai_task: WeeklyReviewAITaskSummary | None = None
    recent_ai_tasks: list[WeeklyReviewAITaskSummary] = Field(default_factory=list)
    recent_ai_results: list[WeeklyReviewAIResultDebugSummary] = Field(default_factory=list)
    final_report_candidates: list[WeeklyReviewFinalReportRead] = Field(default_factory=list)
    recent_messages: list[WeeklyReviewMessageRead] = Field(default_factory=list)


def week_end_for(week_start: date) -> date:
    return week_start + timedelta(days=6)
