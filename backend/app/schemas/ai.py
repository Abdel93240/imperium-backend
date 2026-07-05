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

SUPPORTED_AI_MEMORY_TYPES = frozenset(
    {
        "user_preference",
        "behavioral_pattern",
        "failure_pattern",
        "planning_insight",
        "vtc_zone_pattern",
        "financial_pattern",
        "sport_adaptation",
        "worship_preference",
        "correction",
        "system_note",
    }
)

SUPPORTED_AI_MEMORY_SOURCE_DOMAINS = frozenset(
    {
        "finance",
        "worship",
        "health",
        "rides",
        "planning",
        "decision",
        "review",
        "calendar",
        "vehicle",
        "system",
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
    source_domain: str
    source_table: str | None = None
    source_id: str | None = None


class AIMemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    content: str
    embedding: list[float]
    embedding_model: str
    memory_type: str
    learning_element_type: str | None
    source_domain: str
    source_table: str | None
    source_id: str | None
    confidence: Decimal | None
    privacy_level: str
    is_active: bool
    supersedes_memory_id: UUID | None
    correction_reason: str | None
    expires_at: datetime | None
    metadata: dict | None = Field(default=None, validation_alias="metadata_json")
    idempotency_key: str | None = None
    created_at: datetime
    updated_at: datetime


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
    content: str = Field(min_length=1)
    embedding: list[float] = Field(min_length=1024, max_length=1024)
    embedding_model: str = Field(min_length=1)
    memory_type: str | None = None
    learning_element_type: str | None = None
    source_domain: str | None = None
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    privacy_level: str | None = None
    reason: str | None = None
    payload: dict | None = None


class AIMemoryDraftRead(BaseModel):
    user_id: UUID
    content: str
    embedding: list[float] = Field(min_length=1024, max_length=1024)
    embedding_model: str
    memory_type: str
    learning_element_type: str | None = None
    source_domain: str
    source_table: str | None = None
    source_id: str | None = None
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    privacy_level: str = "private"
    is_active: bool = True
    supersedes_memory_id: UUID | None = None
    correction_reason: str | None = None
    expires_at: datetime | None = None
    metadata: dict | None = None
    idempotency_key: str | None = None


class AIMemorySchemaHealth(BaseModel):
    storage_enabled: bool = False
    table_defined: bool = True
    embeddings_enabled: bool = False
    pgvector_enabled: bool = True
    supported_memory_types: list[str]
    supported_source_domains: list[str]
    supported_privacy_levels: list[str]
    commit_endpoint: str | None = None
    index_endpoint: str = "/api/imperium/memories"
    detail_endpoint: str = "/api/imperium/memories/{memory_id}"
    note: str = "Vector memory schema is defined. Canonical writes wait for the embedding service."


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
