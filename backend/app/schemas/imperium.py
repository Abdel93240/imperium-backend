from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DayStatus(StrEnum):
    completed = "completed"
    partial = "partial"
    failed = "failed"


class MissedDayItem(BaseModel):
    label: str = Field(min_length=1)
    category: str | None = None
    reason: str | None = None
    user_reported_signal: str | None = None


class CompletedDayItem(BaseModel):
    label: str = Field(min_length=1)
    category: str | None = None


class FinishDayRequest(BaseModel):
    local_date: date
    timezone: str = Field(min_length=1)
    day_status: DayStatus
    energy_level: int | None = Field(default=None, ge=1, le=10)
    fatigue_level: int | None = Field(default=None, ge=1, le=10)
    sleep_quality: int | None = Field(default=None, ge=1, le=10)
    stress_level: int | None = Field(default=None, ge=1, le=10)
    mood: str | None = None
    main_win: str | None = None
    main_problem: str | None = None
    missed_items: list[MissedDayItem] = Field(default_factory=list)
    completed_items: list[CompletedDayItem] = Field(default_factory=list)
    notes: str | None = None
    free_text: str | None = None


class DayReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    local_date: date
    timezone: str
    day_status: str
    energy_level: int | None
    fatigue_level: int | None
    sleep_quality: int | None
    stress_level: int | None
    mood: str | None
    main_win: str | None
    main_problem: str | None
    missed_items: list[dict]
    completed_items: list[dict]
    notes: str | None
    free_text: str | None
    source_event_id: str | None
    created_at: datetime
    updated_at: datetime


class FinishDayResponse(BaseModel):
    review: DayReviewResponse
    event_id: str
    status: str


class MissionStatus(StrEnum):
    backlog = "backlog"
    active = "active"
    completed = "completed"
    failed = "failed"
    abandoned = "abandoned"
    cancelled = "cancelled"


class MissionHistoryStatus(StrEnum):
    completed = "completed"
    failed = "failed"
    abandoned = "abandoned"


SUPPORTED_DECISION_DOMAINS = {"religious", "business", "finance", "health"}
SUPPORTED_MISSION_TYPE_CATEGORIES = {
    "cat_a",
    "cat_b",
    "cat_c",
    "cat_d",
    "cat_e",
    "cat_f",
    "cat_g",
    "cat_h",
    "cat_i",
}
DISALLOWED_CLIENT_SCORE_FIELDS = {
    "intrinsic_score",
    "weighted_score",
    "domain_coefficient",
    "final_weighted_score",
    "coefficient",
    "score",
    "priority_bucket",
}


class StartMissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    category: str | None = None
    domain: str | None = None
    priority_level: int | None = Field(default=None, ge=1, le=10)
    mission_type_category: str | None = None
    deadline_at: datetime | None = None
    impact: int | str | None = None
    mission_type: int | str | None = None
    dependency: int | str | bool | None = None
    recurrence: int | str | None = None
    planned_start_at: datetime | None = None
    planned_end_at: datetime | None = None

    @field_validator("title", "category", "domain", "mission_type_category")
    @classmethod
    def strip_mission_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be empty.")
        return stripped

    @field_validator("domain")
    @classmethod
    def validate_decision_domain(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower().replace("_", "-").replace(" ", "-")
        if normalized not in SUPPORTED_DECISION_DOMAINS:
            raise ValueError("domain must be one of religious, business, finance, health.")
        return normalized

    @field_validator("mission_type_category")
    @classmethod
    def validate_mission_type_category(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized not in SUPPORTED_MISSION_TYPE_CATEGORIES:
            raise ValueError("mission_type_category must be cat_a through cat_i.")
        return normalized

    @field_validator("impact", "mission_type", "dependency", "recurrence", mode="before")
    @classmethod
    def strip_scoring_text(cls, value: int | str | bool | None) -> int | str | bool | None:
        if value is None or isinstance(value, (bool, int)):
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be empty.")
        return stripped

    @model_validator(mode="before")
    @classmethod
    def reject_client_supplied_scores(cls, data):
        if isinstance(data, dict):
            forbidden = sorted(DISALLOWED_CLIENT_SCORE_FIELDS.intersection(data))
            if forbidden:
                joined = ", ".join(forbidden)
                raise ValueError(f"Client-supplied score fields are not accepted: {joined}.")
        return data

    @model_validator(mode="after")
    def validate_scoring_category_consistency(self) -> "StartMissionRequest":
        if self.mission_type is None or self.mission_type_category is None or not isinstance(self.mission_type, str):
            return self
        normalized_mission_type = self.mission_type.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized_mission_type in SUPPORTED_MISSION_TYPE_CATEGORIES and normalized_mission_type != self.mission_type_category:
            raise ValueError("mission_type and mission_type_category conflict.")
        return self


class BacklogMissionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    category: str | None = None
    domain: str | None = None
    priority_level: int | None = Field(default=None, ge=1, le=10)
    mission_type_category: str | None = None
    deadline_at: datetime | None = None
    impact: int | str | None = None
    mission_type: int | str | None = None
    dependency: int | str | bool | None = None
    recurrence: int | str | None = None

    @field_validator("title", "category", "domain", "mission_type_category")
    @classmethod
    def strip_mission_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be empty.")
        return stripped

    @field_validator("domain")
    @classmethod
    def validate_decision_domain(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower().replace("_", "-").replace(" ", "-")
        if normalized not in SUPPORTED_DECISION_DOMAINS:
            raise ValueError("domain must be one of religious, business, finance, health.")
        return normalized

    @field_validator("mission_type_category")
    @classmethod
    def validate_mission_type_category(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized not in SUPPORTED_MISSION_TYPE_CATEGORIES:
            raise ValueError("mission_type_category must be cat_a through cat_i.")
        return normalized

    @field_validator("impact", "mission_type", "dependency", "recurrence", mode="before")
    @classmethod
    def strip_scoring_text(cls, value: int | str | bool | None) -> int | str | bool | None:
        if value is None or isinstance(value, (bool, int)):
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be empty.")
        return stripped

    @model_validator(mode="before")
    @classmethod
    def reject_client_supplied_scores(cls, data):
        if isinstance(data, dict):
            forbidden = sorted(DISALLOWED_CLIENT_SCORE_FIELDS.intersection(data))
            if forbidden:
                joined = ", ".join(forbidden)
                raise ValueError(f"Client-supplied score fields are not accepted: {joined}.")
        return data

    @model_validator(mode="after")
    def validate_scoring_category_consistency(self) -> "BacklogMissionCreateRequest":
        if self.mission_type is None or self.mission_type_category is None or not isinstance(self.mission_type, str):
            return self
        normalized_mission_type = self.mission_type.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized_mission_type in SUPPORTED_MISSION_TYPE_CATEGORIES and normalized_mission_type != self.mission_type_category:
            raise ValueError("mission_type and mission_type_category conflict.")
        return self


class MissionCompletionOutcome(StrEnum):
    completed = "completed"
    failed = "failed"
    abandoned = "abandoned"


class CompleteMissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: MissionCompletionOutcome
    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def require_reason_for_non_completed_outcomes(self) -> "CompleteMissionRequest":
        if self.outcome in {MissionCompletionOutcome.failed, MissionCompletionOutcome.abandoned} and self.reason is None:
            raise ValueError("reason is required for failed or abandoned outcomes.")
        return self


class FailMissionRequest(BaseModel):
    failure_reason: str = Field(min_length=1)
    user_reported_signals: dict | None = None
    ai_usable_reason: bool = True


class MissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    title: str
    category: str | None
    domain: str | None
    priority_level: int | None
    mission_type_category: str | None
    planned_start_at: datetime | None
    planned_end_at: datetime | None
    started_at: datetime
    ended_at: datetime | None
    completion_note: str | None
    failure_reason: str | None
    user_reported_signals: dict | None
    ai_usable_reason: bool | None
    event_id: str | None = None
    idempotency_key: str | None = None


class ActiveMissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    title: str
    category: str | None
    domain: str | None
    priority_level: int | None
    mission_type_category: str | None
    planned_start_at: datetime | None
    planned_end_at: datetime | None
    started_at: datetime
    created_at: datetime
    updated_at: datetime


class ActiveMissionResponse(BaseModel):
    mission: ActiveMissionRead | None
    safe_explanation: str


class MissionCompletionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    title: str
    category: str | None
    domain: str | None
    priority_level: int | None
    mission_type_category: str | None
    planned_start_at: datetime | None
    planned_end_at: datetime | None
    started_at: datetime
    ended_at: datetime | None
    completion_note: str | None
    failure_reason: str | None
    user_reported_signals: dict | None
    ai_usable_reason: bool | None


class MissionCompletionSummary(BaseModel):
    status: Literal["completed", "failed", "abandoned"]
    guardrails_checked: list[str]
    safe_explanation: str


class MissionCompletionResponse(BaseModel):
    mission: MissionCompletionRead
    completion_summary: MissionCompletionSummary


class MissionHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    title: str
    category: str | None
    domain: str | None
    priority_level: int | None
    mission_type_category: str | None
    planned_start_at: datetime | None
    planned_end_at: datetime | None
    started_at: datetime
    ended_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MissionHistoryResponse(BaseModel):
    items: list[MissionHistoryRead]
    count: int
    limit: int
    offset: int
    safe_explanation: str


class MissionDetailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    title: str
    category: str | None
    domain: str | None
    priority_level: int | None
    mission_type_category: str | None
    planned_start_at: datetime | None
    planned_end_at: datetime | None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class MissionDetailResponse(BaseModel):
    mission: MissionDetailRead
    safe_explanation: str


class MissionDecisionScoreSummary(BaseModel):
    # Internal score value retained for backend bookkeeping, but excluded from
    # public JSON serialization.
    intrinsic_score: int | None = Field(default=None, exclude=True)
    priority_bucket: int
    score_status: str
    missing_fields: list[str]
    source: str


class BacklogMissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    title: str
    category: str | None
    domain: str | None
    priority_level: int | None
    mission_type_category: str | None
    planned_start_at: datetime | None
    planned_end_at: datetime | None
    created_at: datetime
    updated_at: datetime
    decision_score: MissionDecisionScoreSummary | None = None


class BacklogMissionCreateResponse(BaseModel):
    mission: BacklogMissionRead
    event_id: str
    idempotency_key: str
    status: str
    score_created: bool = False


class BacklogMissionListResponse(BaseModel):
    items: list[BacklogMissionRead]
    count: int
    ordering: str


class PublicDecisionScoreSummary(BaseModel):
    label: Literal["high", "medium", "low"]
    reason_codes: list[str] | None = None


class BacklogDecisionScoreSummary(PublicDecisionScoreSummary):
    pass


class BacklogDecisionCandidate(BaseModel):
    id: UUID
    title: str
    domain: str | None
    priority_level: int | None
    priority_bucket: int
    score_summary: BacklogDecisionScoreSummary


class BacklogDecisionPreviewResponse(BaseModel):
    recommended_mission_id: UUID | None
    candidate_count: int
    candidates: list[BacklogDecisionCandidate]
    safe_explanation: str


class PromotedBacklogMissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    title: str
    category: str | None
    domain: str | None
    priority_level: int | None
    mission_type_category: str | None
    planned_start_at: datetime | None
    planned_end_at: datetime | None
    started_at: datetime
    created_at: datetime
    updated_at: datetime
    decision_score: MissionDecisionScoreSummary | None = None


class BacklogPromotionSummary(BaseModel):
    status: Literal["promoted"]
    guardrails_checked: list[str]
    safe_explanation: str


class PromoteBacklogMissionResponse(BaseModel):
    mission: PromotedBacklogMissionRead
    promotion_summary: BacklogPromotionSummary
    event_id: str
    idempotency_key: str
    status: str
    decision_score: MissionDecisionScoreSummary | None = None


class MissionWriteResponse(BaseModel):
    mission: MissionResponse
    event_id: str
    idempotency_key: str
    status: str
    score_created: bool = False
    decision_score: MissionDecisionScoreSummary | None = None


class PriorityRuleInput(BaseModel):
    priority_key: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=160)
    rank_order: int = Field(ge=1)
    importance_score: int | None = Field(default=None, ge=1, le=100)

    @field_validator("priority_key", "label")
    @classmethod
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be empty.")
        return stripped


class ReplacePriorityRulesRequest(BaseModel):
    priorities: list[PriorityRuleInput] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def reject_duplicates(self) -> "ReplacePriorityRulesRequest":
        ranks = [priority.rank_order for priority in self.priorities]
        if len(ranks) != len(set(ranks)):
            raise ValueError("Duplicate rank_order values are not allowed.")

        keys = [priority.priority_key.strip().lower() for priority in self.priorities]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate priority_key values are not allowed.")
        return self


class PriorityRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    priority_key: str
    label: str
    rank_order: int
    importance_score: int | None
    is_active: bool
    updated_by_event_id: UUID | None
    created_at: datetime
    updated_at: datetime


class PriorityRulesResponse(BaseModel):
    priorities: list[PriorityRuleResponse]
    event_id: str | None = None
    idempotency_key: str | None = None
    status: str
    deprecated: bool = False
    legacy: bool = False
    superseded_by: str | None = None
    canonical_source: str | None = None
    message: str | None = None


class DecisionFrameworkDomain(StrEnum):
    religious = "religious"
    business = "business"
    finance = "finance"
    health = "health"


class DecisionFrameworkPriorityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    domain: DecisionFrameworkDomain
    position: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DecisionFrameworkPrioritiesResponse(BaseModel):
    priorities: list[DecisionFrameworkPriorityRead]
    idempotency_key: str | None = None
    status: str


class DecisionFrameworkPrioritiesUpdateRequest(BaseModel):
    domains: list[str] = Field(min_length=4, max_length=4)

    @field_validator("domains")
    @classmethod
    def strip_domains(cls, value: list[str]) -> list[str]:
        return [domain.strip().lower() for domain in value]


class CalendarEventType(StrEnum):
    event = "event"
    deadline = "deadline"
    vacation = "vacation"


class CalendarEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: CalendarEventType
    title: str = Field(min_length=1, max_length=200)
    starts_at: datetime
    ends_at: datetime | None = None
    blocks_time: bool = True
    location: str | None = None
    notes: str | None = None

    @field_validator("title")
    @classmethod
    def strip_calendar_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be empty.")
        return stripped

    @field_validator("location", "notes")
    @classmethod
    def strip_optional_calendar_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        return stripped

    @model_validator(mode="after")
    def validate_calendar_range(self) -> "CalendarEventCreate":
        if self.ends_at is not None and self.ends_at < self.starts_at:
            raise ValueError("ends_at must be greater than or equal to starts_at.")
        return self


class CalendarEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    event_type: CalendarEventType
    title: str
    starts_at: datetime
    ends_at: datetime | None
    blocks_time: bool
    location: str | None
    notes: str | None
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    deletion_reason: str | None = None
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime


class CalendarEventDeleteResponse(BaseModel):
    id: UUID
    status: str


class DecisionFrameworkSchemaResponse(BaseModel):
    scoring_enabled: bool
    monthly_planning_enabled: bool
    daily_adaptation_enabled: bool
    real_ai_enabled: bool
    embeddings_enabled: bool
    supported_domains: list[str]
    coefficient_policy: dict
    storage_tables: list[str]
    note: str


class DecisionFrameworkScorePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str
    title: str | None = Field(default=None, min_length=1, max_length=200)
    deadline_at: datetime | date | None = None
    impact: int | str | None = None
    effort: int | str | None = None
    mission_type: int | str | None = None
    dependency: int | bool | str | None = None
    alignment: int | str | None = None
    recurrence: int | str | None = None
    payload: dict | None = None
    impact_points: int | None = Field(default=None, ge=0, le=30, description="Legacy alias for impact.")
    impact_level: int | None = Field(default=None, ge=0, le=30, description="Legacy alias for impact.")
    effort_points: int | None = Field(default=None, ge=0, le=20, description="Legacy alias for mission_type.")
    mission_type_points: int | None = Field(default=None, ge=0, le=20, description="Legacy alias for mission_type.")
    dependency_points: int | None = Field(default=None, ge=0, le=10, description="Legacy alias for dependency.")
    blocked_mission_count: int | None = Field(default=None, ge=0, description="Legacy alias for dependency.")
    alignment_points: int | None = Field(default=None, ge=0, le=10, description="Legacy alias for recurrence.")

    @field_validator("domain", "title", "recurrence")
    @classmethod
    def strip_score_text(cls, value: int | str | None) -> int | str | None:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be empty.")
        return stripped


class DecisionFrameworkScoreExplanation(BaseModel):
    deadline_points: int
    impact_points: int
    mission_type_points: int
    dependency_points: int
    recurrence_points: int
    missing_fields: list[str]
    final_intrinsic_score: int
    flags: list[str] = Field(default_factory=list)


class DecisionFrameworkScoreBreakdownItem(BaseModel):
    label: str
    key: str
    points: int
    max_points: int
    reason: str


class DecisionFrameworkScorePreviewResponse(BaseModel):
    domain: DecisionFrameworkDomain
    domain_position: int
    intrinsic_score: int
    priority_bucket: int
    score_status: str
    display_title: str
    display_summary: str
    explanation: DecisionFrameworkScoreExplanation
    breakdown: list[DecisionFrameworkScoreBreakdownItem]
    missing_fields: list[str]
    warnings: list[str]
    storage_enabled: bool
    source: str


class MissionDecisionScorePublicSummary(PublicDecisionScoreSummary):
    pass


class ImperiumVaultSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str
    occurred_from: datetime | None
    occurred_to: datetime | None
    total_income_cents: int
    total_expense_cents: int
    net_cents: int
    transaction_count: int
    income_count: int
    expense_count: int
    safe_explanation: str = "Vault summary computed from current user's ledger transactions."


class ImperiumVaultMonthlySummaryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    total_income_cents: int
    total_expense_cents: int
    net_cents: int
    transaction_count: int
    income_count: int
    expense_count: int


class ImperiumVaultMonthlySummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str
    items: list[ImperiumVaultMonthlySummaryItem]
    count: int
    safe_explanation: str = "Vault monthly summary computed from current user's ledger transactions."


class ImperiumVaultCategorySummaryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    total_income_cents: int
    total_expense_cents: int
    net_cents: int
    transaction_count: int
    income_count: int
    expense_count: int


class ImperiumVaultCategorySummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str
    items: list[ImperiumVaultCategorySummaryItem]
    count: int
    safe_explanation: str = "Vault category summary computed from current user's ledger transactions."


class ImperiumVaultTransactionDetailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    transaction_type: Literal["income", "expense"]
    amount_cents: int
    currency: str
    occurred_at: datetime
    local_date: date
    timezone: str
    category: str | None
    source: str | None
    note: str | None
    external_ref: str | None
    is_reversal: bool = False
    reversal_of_transaction_id: UUID | None = None
    reversal_reason: str | None = None
    created_at: datetime

    @field_validator("is_reversal", mode="before")
    @classmethod
    def default_is_reversal(cls, value: bool | None) -> bool:
        return False if value is None else value


class ImperiumVaultTransactionDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction: ImperiumVaultTransactionDetailRead
    safe_explanation: str = "Vault transaction detail for current user."


class MissionDecisionScoreRead(BaseModel):
    mission_id: UUID
    status: MissionStatus
    priority_level: int | None
    priority_bucket: int
    score_summary: MissionDecisionScorePublicSummary
    safe_explanation: str


class PathItemStatus(StrEnum):
    planned = "planned"
    in_progress = "in_progress"
    completed = "completed"
    skipped = "skipped"
    cancelled = "cancelled"


class PathItemSource(StrEnum):
    manual = "manual"
    system = "system"
    ai_planned = "ai_planned"


class CreatePathItemRequest(BaseModel):
    local_date: date
    timezone: str = Field(default="Europe/Paris", min_length=1)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    category: str | None = None
    priority_key: str | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    status: PathItemStatus = PathItemStatus.planned
    source: PathItemSource = PathItemSource.manual
    sort_order: int = 0
    metadata: dict = Field(default_factory=dict)

    @field_validator("timezone", "title", "description", "category", "priority_key")
    @classmethod
    def strip_path_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        return stripped


class SkipPathItemRequest(BaseModel):
    skip_reason: str = Field(min_length=1)

    @field_validator("skip_reason")
    @classmethod
    def strip_skip_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("skip_reason cannot be empty.")
        return stripped


class PathItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    local_date: date
    timezone: str
    title: str
    description: str | None
    category: str | None
    priority_key: str | None
    planned_start: datetime | None
    planned_end: datetime | None
    status: str
    source: str
    sort_order: int
    skip_reason: str | None
    completed_at: datetime | None
    skipped_at: datetime | None
    cancelled_at: datetime | None
    metadata: dict = Field(validation_alias="item_metadata")
    created_at: datetime
    updated_at: datetime
    idempotency_key: str | None = None


class PathItemWriteResponse(BaseModel):
    item: PathItemResponse
    event_id: str
    idempotency_key: str
    status: str


class DailyPlanStatus(StrEnum):
    draft = "draft"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class CreateDailyPlanRequest(BaseModel):
    local_date: date
    timezone: str = Field(default="Europe/Paris", min_length=1)
    title: str | None = None
    summary: str | None = None
    focus_priority_key: str | None = None
    notes: str | None = None

    @field_validator("timezone", "title", "summary", "focus_priority_key", "notes")
    @classmethod
    def strip_daily_plan_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        return stripped


class DailyPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    local_date: date
    timezone: str
    plan_status: str
    title: str | None
    summary: str | None
    focus_priority_key: str | None
    current_mission_id: UUID | None
    generated_from: dict
    plan_blocks: list[dict]
    notes: str | None
    created_at: datetime
    updated_at: datetime
    idempotency_key: str | None = None


class DailyPlanWriteResponse(BaseModel):
    plan: DailyPlanResponse
    event_id: str
    idempotency_key: str
    status: str


class WeeklyReviewStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    week_start: date
    ready: bool
    ready_at: datetime | None
    launched: bool
    launched_at: datetime | None
    analysis_status: str
    analysis_completed_at: datetime | None
    created_at: datetime


class WeeklyReviewLaunchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    week_start: date
    launched: bool
    launched_at: datetime
    analysis_status: str


class DashboardMission(BaseModel):
    id: UUID
    status: str
    title: str
    category: str | None
    started_at: datetime
    ended_at: datetime | None
    completed_at: datetime | None = None
    failed_at: datetime | None = None


class DashboardPriority(BaseModel):
    priority_key: str
    label: str
    rank_order: int
    importance_score: int | None


class DashboardDayReview(BaseModel):
    id: UUID
    local_date: date
    timezone: str
    day_status: str
    energy_level: int | None
    fatigue_level: int | None
    sleep_quality: int | None
    stress_level: int | None
    mood: str | None
    main_win: str | None
    main_problem: str | None
    notes: str | None
    created_at: datetime


class DashboardVaultWeek(BaseModel):
    week_start: date
    week_end: date
    income_total: Decimal
    expense_total: Decimal
    net_total: Decimal
    transaction_count: int


class DashboardSystemStatus(BaseModel):
    api_status: str
    db_status: str
    generated_at: datetime


class ImperiumDashboardReadinessSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission_available: bool
    vault_available: bool
    path_available: bool
    system_status_available: bool
    current_mission_present: bool
    recent_missions_count: int
    priorities_count: int
    latest_day_review_present: bool
    vault_transaction_count: int
    path_today_count: int
    daily_plan_present: bool
    weekly_review_banner_present: bool
    safe_explanation: str = "Dashboard readiness snapshot computed from read-only module data."


class DashboardWeeklyReviewBanner(BaseModel):
    week_start: date
    ready: bool
    launched: bool
    analysis_status: str
    show_banner: bool


class ImperiumDashboardResponse(BaseModel):
    current_mission: DashboardMission | None
    recent_missions: list[DashboardMission]
    priorities: list[DashboardPriority]
    latest_day_review: DashboardDayReview | None
    vault_week: DashboardVaultWeek
    path_today: list[PathItemResponse]
    path_counts_today: dict[str, int]
    daily_plan_today: DailyPlanResponse | None
    readiness: ImperiumDashboardReadinessSection
    weekly_review_banner: DashboardWeeklyReviewBanner | None = None
    system_status: DashboardSystemStatus


class WeeklyReportDays(BaseModel):
    total_days: int
    reviewed_days: int
    completed_days: int
    partial_days: int
    failed_days: int
    average_energy_level: Decimal | None
    average_fatigue_level: Decimal | None
    average_sleep_quality: Decimal | None
    average_stress_level: Decimal | None


class WeeklyReportMissionItem(BaseModel):
    id: UUID
    status: str
    title: str
    category: str | None
    started_at: datetime
    ended_at: datetime | None


class WeeklyReportMissions(BaseModel):
    total: int
    active: int
    completed: int
    failed: int
    cancelled: int
    recent: list[WeeklyReportMissionItem]


class WeeklyReportPath(BaseModel):
    total_items: int
    planned: int
    in_progress: int
    completed: int
    skipped: int
    cancelled: int
    completion_rate: Decimal | None


class WeeklyReportDailyPlans(BaseModel):
    total: int
    draft: int
    active: int
    completed: int
    cancelled: int


class WeeklyReportVaultCategory(BaseModel):
    category: str
    income_total: str
    expense_total: str
    correction_total: str
    net_total: str


class WeeklyReportVault(BaseModel):
    income_total: str
    expense_total: str
    net_total: str
    currency: str
    by_category: list[WeeklyReportVaultCategory]


class WeeklyReportPriority(BaseModel):
    rank_order: int
    priority_key: str
    label: str
    importance_score: int | None


class WeeklyReportSignals(BaseModel):
    discipline_signal: str
    fatigue_signal: str
    financial_signal: str
    execution_summary: str


class WeeklyReportResponse(BaseModel):
    week_start: date
    week_end: date
    timezone: str
    days: WeeklyReportDays
    missions: WeeklyReportMissions
    path: WeeklyReportPath
    daily_plans: WeeklyReportDailyPlans
    vault: WeeklyReportVault
    priorities: list[WeeklyReportPriority]
    signals: WeeklyReportSignals
