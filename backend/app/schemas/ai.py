from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


ALLOWED_AI_RESULT_TYPES = frozenset(
    {
        "weekly_report.summary",
        "weekly_report.questions",
        "weekly_report.draft",
        "weekly_report.final",
        "weekly_report.revision",
        "vector.event_scan",
        "vector.rail_disruption_triage",
        "vector.zone_recommendation",
        "vault.receipt_extract",
        "vault.weekly_finance_analysis",
        "pulse.meal_suggestion",
        "pulse.training_adjustment",
        "pulse.medical_report.analyze",
        "imperium.email_triage",
        "imperium.daily_plan_assist",
        "imperium.mission_recommendation",
        "imperium.priority_review",
        "imperium.memory_candidate_extract",
        "media.audio_transcription",
        "media.image_ocr",
        "system.health_review",
    }
)

SUPPORTED_AI_MEMORY_KINDS = frozenset(
    {
        "behavior_pattern",
        "blocker",
        "weekly_commitment",
        "preference",
        "operational_signal",
        "risk",
        "achievement",
        "constraint",
        "strategy_note",
    }
)

SUPPORTED_AI_MEMORY_SCOPES = frozenset(
    {
        "user_profile",
        "operating_pattern",
        "weekly_review",
        "module_signal",
        "user_preference",
        "strategy",
        "health",
        "finance",
        "vtc",
    }
)


class AITaskCreate(BaseModel):
    task_type: str = Field(min_length=1)
    source_module: str = Field(pattern=r"^(imperium|vector|vault|pulse|path|system)$")
    input_payload: dict
    prepared_payload: dict | None = None
    router_decision: dict | None = None
    model_hint: str | None = None
    privacy_level: str | None = None


class AITaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None
    task_type: str
    status: str
    source_module: str
    input_payload: dict
    prepared_payload: dict | None
    router_decision: dict | None
    model_hint: str | None
    privacy_level: str | None
    idempotency_key: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    error_code: str | None
    error_message: str | None


class AIResultCallback(BaseModel):
    result_type: str = Field(min_length=1)
    result_payload: dict
    model_used: str | None = None
    provider: str | None = None
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    raw_payload: dict | None = None

    @field_validator("result_type")
    @classmethod
    def validate_result_type(cls, value: str) -> str:
        if value not in ALLOWED_AI_RESULT_TYPES:
            raise ValueError("Unsupported AI result_type.")
        return value


class AIResultInternalRead(BaseModel):
    """Internal-only schema. Includes raw_payload. Never expose via a public route."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    user_id: UUID | None
    result_type: str
    status: str
    result_payload: dict
    raw_payload: dict | None
    model_used: str | None
    provider: str | None
    confidence: Decimal | None
    idempotency_key: str | None
    created_at: datetime
    updated_at: datetime


class AIResultRead(BaseModel):
    """Public-safe AI result schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    user_id: UUID | None
    result_type: str
    status: str
    result_payload: dict
    model_used: str | None
    provider: str | None
    confidence: Decimal | None
    idempotency_key: str | None
    created_at: datetime
    updated_at: datetime


class AIResultValidationCreate(BaseModel):
    validation_status: str = Field(pattern=r"^(accepted|rejected|edited)$")
    validated_payload: dict | None = None
    user_note: str | None = None


class AIResultValidationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    result_id: UUID
    task_id: UUID
    user_id: UUID | None
    validation_status: str
    validated_payload: dict | None
    user_note: str | None
    created_at: datetime


class AIMemorySourceRead(BaseModel):
    source_module: str
    source_type: str
    source_id: str
    source_report_id: UUID | None = None
    source_session_id: UUID | None = None
    source_candidate_id: str | None = None
    source_decision_id: UUID | None = None


class AIMemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    source_module: str
    source_type: str
    source_id: str
    source_report_id: UUID | None
    source_session_id: UUID | None
    source_candidate_id: str | None
    source_decision_id: UUID | None
    kind: str
    scope: str
    title: str
    content: str
    confidence: Decimal
    status: str
    visibility: str
    metadata_json: dict | None = None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    superseded_by_id: UUID | None


class AIMemoryListResponse(BaseModel):
    items: list[AIMemoryRead]
    limit: int
    offset: int
    count: int
    has_more: bool


class AIMemoryArchiveRequest(BaseModel):
    reason: str | None = None
    payload: dict | None = None


class AIMemorySupersedeRequest(BaseModel):
    title: str | None = None
    content: str = Field(min_length=1)
    kind: str | None = None
    scope: str | None = None
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    reason: str | None = None
    payload: dict | None = None


class AIMemoryDraftRead(BaseModel):
    user_id: UUID
    source_module: str
    source_type: str
    source_id: str
    source_report_id: UUID | None = None
    source_session_id: UUID | None = None
    source_candidate_id: str | None = None
    source_decision_id: UUID | None = None
    kind: str
    scope: str
    title: str
    content: str
    confidence: Decimal = Field(ge=0, le=1)
    status: str = "active"
    visibility: str = "private"
    metadata_json: dict | None = None


class AIMemorySchemaHealth(BaseModel):
    storage_enabled: bool = True
    table_defined: bool = True
    embeddings_enabled: bool = False
    pgvector_enabled: bool = False
    supported_kinds: list[str]
    supported_scopes: list[str]
    supported_statuses: list[str]
    supported_visibility: list[str]
    commit_endpoint: str = "/api/imperium/weekly-review/memory-candidates/commit"
    index_endpoint: str = "/api/imperium/memories"
    detail_endpoint: str = "/api/imperium/memories/{memory_id}"
    note: str = "Explicit user-triggered memory commit is enabled. No embeddings are generated."


class AIResultCallbackResponse(BaseModel):
    status: str
    task_id: UUID
    result_id: UUID
    result_status: str
    idempotency_key: str


class AITaskRunningResponse(BaseModel):
    task: AITaskRead
    transitioned: bool


class QwenScoreBreakdown(BaseModel):
    complexity: int = Field(ge=0, le=10)
    context_size: int = Field(ge=0, le=10)
    ambiguity: int = Field(ge=0, le=10)
    error_consequence: int = Field(ge=0, le=10)
    speed_tolerance: int = Field(ge=0, le=10)
    data_sensitivity: int = Field(ge=0, le=10)
    cost_justification: int = Field(ge=0, le=10)


class QwenRoutingDecision(BaseModel):
    task_type: str
    difficulty_score: int = Field(ge=0, le=200)
    score_breakdown: QwenScoreBreakdown
    recommended_model: str
    reason: str
    requires_clarification: bool
    clarification_questions: list[str]
    requires_user_validation: bool
    risk_flags: list[str]


class QwenWeeklySummarySection(BaseModel):
    title: str
    content: str


class QwenWeeklySummary(BaseModel):
    result_type: str = "weekly_report.summary"
    summary: str
    sections: list[QwenWeeklySummarySection]
    questions: list[str]
    confidence: float = Field(ge=0, le=1)
    warnings: list[str]

    @field_validator("result_type")
    @classmethod
    def validate_weekly_summary_result_type(cls, value: str) -> str:
        if value != "weekly_report.summary":
            raise ValueError("Qwen weekly summary result_type must be weekly_report.summary.")
        return value


class QwenSmokeRequest(BaseModel):
    task_type: str = Field(min_length=1)
    input_payload: dict = Field(default_factory=dict)
    mode: str = Field(default="route", pattern=r"^(route|weekly_summary)$")
