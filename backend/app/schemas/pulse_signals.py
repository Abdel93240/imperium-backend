"""Board Pulse et signalements subjectifs (spec Pulse §3.1, §4, §14)."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.pulse_health import RedFlagRead


class BoardSignalRead(BaseModel):
    code: str
    label_fr: str | None
    unit: str | None
    state: Literal["fresh", "stale", "no_data"]
    value: float | None = None
    band: str | None = None  # green|yellow|orange|red ; null = informatif
    flag: bool = False  # jamais vrai pour une valeur périmée
    measured_at: datetime | None = None
    age_min: int | None = None
    detail: dict = Field(default_factory=dict)


class BoardRead(BaseModel):
    generated_at: datetime
    red_flags: list[RedFlagRead]
    signals: list[BoardSignalRead]
    flags_count: int
    max_band: str


class SubjectiveReportCreate(BaseModel):
    """Fatigue, humeur ou stress : 1 = bien, 5 = mal (même sens pour les trois). La douleur passe par pain-logs."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["fatigue", "mood", "stress"]
    level: int = Field(ge=1, le=5)
    reported_at: datetime | None = None


class SubjectiveReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    level: int
    reported_at: datetime
    created_at: datetime


class SubjectiveReportListResponse(BaseModel):
    day: date | None = None
    items: list[SubjectiveReportRead]


class DispatchRead(BaseModel):
    """Réveil de la sentinelle (spec Pulse §3.2) ; `output` porte `dry_run: true` tant que l'IA est coupée."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    triggered_by: str
    subject_ref: str | None
    board_snapshot_id: UUID
    flag_set: dict
    status: str
    model_used: str | None
    output: dict | None
    valid: bool | None
    escalated: bool
    procedures_named: list[str] | None
    outcome: str | None
    user_reaction: str | None
    reacted_at: datetime | None
    created_at: datetime
    completed_at: datetime | None


class DispatchListResponse(BaseModel):
    items: list[DispatchRead]


class DispatchReactionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reaction: Literal["useful", "useless", "missed"]


class MetricsDayRead(BaseModel):
    """Compteurs d'un jour de Paris ; null = pas encore mesurable (propositions, solveur)."""

    model_config = ConfigDict(from_attributes=True)

    metric_date: date
    dispatches: int
    skipped_passes: int
    dispatches_useful: int
    dispatches_useless: int
    missed_reports: int
    escalations: int
    invalid_fallbacks: int
    red_flags: int
    proposals: int | None = None
    accepted: int | None = None
    refused: int | None = None
    modified: int | None = None
    solver_runs: int | None = None
    solver_infeasible: int | None = None
    agreement_by_slot: dict | None = None


class MetricsSlotRead(BaseModel):
    slot_code: str
    tier: str
    audit_sample_pct: int
    agreement_target_pct: int | None
    last_week_agreement_pct: float | None
    decay_proposed: bool


class MetricsSummaryRead(BaseModel):
    days: list[MetricsDayRead]  # jours clos enregistrés par le rollup, du plus ancien au plus récent
    today: MetricsDayRead  # calculé à la volée, jamais enregistré
    slots: list[MetricsSlotRead]


class ProposalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    payload: dict
    summary_fr: str
    presented_at: datetime | None
    expires_at: datetime | None
    decision: str | None
    decided_at: datetime | None
    user_explanation: str | None
    modified_payload: dict | None
    applied: bool
    applied_at: datetime | None


class ProposalListResponse(BaseModel):
    items: list[ProposalRead]


class ProposalDecisionRequest(BaseModel):
    """Refus : explication obligatoire. Modification : `modified_payload` porte le coup et ses paramètres."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["accepted", "refused", "modified"]
    user_explanation: str | None = Field(default=None, max_length=1000)
    modified_payload: dict | None = None

    @model_validator(mode="after")
    def _modified_has_payload(self):
        if self.decision == "modified" and not self.modified_payload:
            raise ValueError("modified_payload is required for a modified decision.")
        return self


class AdaptRequest(BaseModel):
    """« Adapter à mon état » : une raison choisie dans une liste (jamais de texte libre dans le prompt)."""

    model_config = ConfigDict(extra="forbid")

    reason: Literal["fatigue", "pain", "short_time", "other"]


class AdaptRead(BaseModel):
    proposal: ProposalRead | None
    outcome: str  # proposed | session_unavailable | red_flag_block
