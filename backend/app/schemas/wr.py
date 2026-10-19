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
    autoaccept_class_id: UUID | None = None


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
        # Spec WR §9 P4 : chaque refus ou modification exige une explication — c'est le label.
        if (self.decision == "refused" or self.modified_payload is not None) and not (self.decision_note or "").strip():
            raise ValueError("decision_note is required to refuse or modify an item.")
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


AutoacceptItemType = Literal[
    "chain_proposal", "pattern_new", "pattern_contradiction", "anomaly", "belief_review_due",
    "plan_delta_proposal", "investigation_result",
]


class AutoacceptClassCreateRequest(BaseModel):
    """Activation d'une classe par l'utilisateur (spec WR §9 P4) ; la raison est obligatoire."""

    model_config = ConfigDict(extra="forbid")

    item_type: AutoacceptItemType
    domain: Literal["pulse", "wr", "daily", "vector", "path", "vault", "imperium", "system"] | None = None
    slot_code: str = Field(min_length=1, max_length=128)
    min_confidence: int = Field(ge=0, le=100)
    rationale_fr: str = Field(min_length=1, max_length=500)


class AutoacceptClassRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    item_type: AutoacceptItemType
    domain: str | None
    slot_code: str
    min_confidence: int
    rationale_fr: str
    enabled: bool
    created_at: datetime
    disabled_at: datetime | None
    agreement_holds: bool = False
    auto_accepted: int = 0
    spotchecks_validated: int = 0
    spotchecks_refused: int = 0


class AutoacceptClassListResponse(BaseModel):
    classes: list[AutoacceptClassRead]


class WalkStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["full", "light"] = "full"


class WalkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    review_session_id: UUID
    mode: Literal["full", "light"]
    budget_min: int
    started_at: datetime
    closed_at: datetime | None


class WalkNextResponse(BaseModel):
    """Prochain item à trancher ; au-delà du budget, seuls les rouges et décisions forcées sont servis."""

    walk: WalkRead
    item: DocketItemRead | None
    elapsed_min: int
    remaining_min: int
    budget_exhausted: bool
    remaining_items: int
    decided_in_walk: int


PLAN_REF_PATTERN = r"^[a-z_]+:[A-Za-z0-9_.:-]{1,120}$"
PLAN_MAX_DAYS = 42


class PlanItem(BaseModel):
    """Un élément du plan : `ref` stable (`mission:…`, `objective:…`) que visent les deltas."""

    model_config = ConfigDict(extra="forbid")

    ref: str = Field(pattern=PLAN_REF_PATTERN)
    title_fr: str = Field(min_length=1, max_length=200)
    week: int = Field(ge=1, le=6)
    params: dict = Field(default_factory=dict)


class PlanContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PlanItem] = Field(min_length=1, max_length=300)
    invariants_fr: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _unique_refs(self) -> "PlanContent":
        refs = [item.ref for item in self.items]
        if len(refs) != len(set(refs)):
            raise ValueError("plan item refs must be unique")
        return self


class PlanInitialRequest(BaseModel):
    """Plan initial SAISI et validé par l'utilisateur (carte ACT-WR-18) : jamais généré ici."""

    model_config = ConfigDict(extra="forbid")

    horizon_start: date
    horizon_end: date
    plan: PlanContent
    rationale_fr: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def _horizon(self) -> "PlanInitialRequest":
        days = (self.horizon_end - self.horizon_start).days + 1
        if not 7 <= days <= PLAN_MAX_DAYS:
            raise ValueError(f"horizon must span 7 to {PLAN_MAX_DAYS} days")
        weeks = -(-days // 7)
        if any(item.week > weeks for item in self.plan.items):
            raise ValueError(f"item week beyond the horizon ({weeks} weeks)")
        return self


class PlanVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    horizon_start: date
    horizon_end: date
    plan: dict
    origin: Literal["initial", "monthly_regen", "shock_regen"]
    status: Literal["proposed", "active", "superseded"]
    rationale_fr: str | None
    created_at: datetime
    activated_at: datetime | None
    superseded_at: datetime | None
    superseded_reason_fr: str | None


class PlanVersionListResponse(BaseModel):
    versions: list[PlanVersionRead]


class PlanSupersedeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_fr: str = Field(min_length=1, max_length=500)


class PlanCurrentRead(BaseModel):
    """v_plan_current : la version active avec ses deltas appliqués, dans l'ordre."""

    plan_version_id: UUID
    horizon_start: date
    horizon_end: date
    origin: str
    activated_at: datetime
    plan: dict
    applied_delta_ids: list[UUID]
