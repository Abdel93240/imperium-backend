"""Docket du WR (spec WR §3.1, §7, §12) : lecture et décision."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

DocketItemType = Literal[
    "chain_proposal", "pattern_new", "pattern_contradiction", "anomaly", "belief_review_due",
    "user_question", "plan_delta_proposal", "autoaccept_spotcheck", "investigation_result", "red_flag_ref",
]
DocketStatus = Literal["pending", "presented", "validated", "refused", "deferred", "archived"]
DocketDecision = Literal["validated", "refused", "deferred", "archived"]


class DocketItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    item_type: DocketItemType
    domain: str
    title_fr: str
    payload: dict
    evidence_refs: dict
    confidence: int | None
    impact_estimate: int
    severity: Literal["normal", "elevated", "red"]
    priority: float
    status: DocketStatus
    consecutive_defers: int
    force_decision: bool
    source_worker: str
    created_at: datetime
    decided_at: datetime | None
    decision_note: str | None


class DocketListResponse(BaseModel):
    items: list[DocketItemRead]


class DocketDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: DocketDecision
    decision_note: str | None = Field(default=None, max_length=2000)
    modified_payload: dict | None = None

    @model_validator(mode="after")
    def _modification_needs_validation(self) -> "DocketDecisionRequest":
        if self.modified_payload is not None and self.decision != "validated":
            raise ValueError("modified_payload is only allowed with decision 'validated'.")
        return self


class DigestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    review_session_id: UUID
    window_from: date
    window_to: date
    digest: dict
    token_estimate: int
    created_at: datetime


class WrMetricsWeekRead(BaseModel):
    """Métriques d'une semaine (spec WR §3.8) ; NULL = pas encore mesurable."""

    model_config = ConfigDict(from_attributes=True)

    week_start: date
    factory_runs: int | None
    events_processed: int | None
    chain_proposals: int | None
    patterns_new: int | None
    patterns_reinforced: int | None
    contradictions: int | None
    docket_created: int | None
    docket_validated: int | None
    docket_refused: int | None
    docket_deferred: int | None
    docket_forced_decisions: int | None
    wr_duration_min: int | None
    wr_mode: Literal["full", "light", "skipped"] | None
    cloud_cost_estimate: float | None
    agreement_by_slot: dict | None
    computed_at: datetime


class WrMetricsWeeklyResponse(BaseModel):
    weeks: list[WrMetricsWeekRead]


class SlotAuditWeekRead(BaseModel):
    week_start: date
    samples: int
    agreement_pct: float


class SlotAuditStateRead(BaseModel):
    """État d'audit d'un slot IA (spec WR §3.7) ; la décroissance n'est qu'une proposition."""

    slot_code: str
    domain: str
    tier: Literal["local_default", "cloud_forced", "routed"]
    audit_sample_pct: int
    agreement_target_pct: int | None
    version: int
    weeks: list[SlotAuditWeekRead]
    decay_proposed: bool
    proposed_audit_sample_pct: int | None


class SlotAuditStatesResponse(BaseModel):
    slots: list[SlotAuditStateRead]


class SlotTransitionUpdateRequest(BaseModel):
    """Décision utilisateur sur l'audit d'un slot. Le tier ne se change pas ici (routage doc 30)."""

    slot_code: str = Field(min_length=1, max_length=128)
    audit_sample_pct: int | None = Field(default=None, ge=0, le=100)
    agreement_target_pct: int | None = Field(default=None, ge=1, le=100)
    reason_fr: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _something_changes(self) -> "SlotTransitionUpdateRequest":
        if self.audit_sample_pct is None and self.agreement_target_pct is None:
            raise ValueError("Give audit_sample_pct or agreement_target_pct.")
        return self
