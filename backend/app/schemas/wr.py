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
