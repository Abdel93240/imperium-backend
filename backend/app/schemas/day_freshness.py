"""Vérification de fraîcheur au démarrage de journée (DECISION_demarrage_journee, doc 52 §9.1)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class FreshnessCalendarChange(BaseModel):
    id: UUID
    title: str
    starts_at: datetime
    change: Literal["created", "updated", "deleted"]


class FreshnessMission(BaseModel):
    id: UUID
    title: str
    status: str


class FreshnessConstraint(BaseModel):
    code: Literal["ghusl_required", "fasting_active", "replan_open", "standby_decision"]
    message: str


class DayFreshnessResponse(BaseModel):
    planning_day_id: UUID
    checked_at: datetime
    status: Literal["fresh", "review"]
    reasons: list[str]
    plan_id: UUID | None
    plan_generated_at: datetime | None
    calendar_changes: list[FreshnessCalendarChange]
    stale_active_mission: FreshnessMission | None
    prior_day_failed: list[FreshnessMission]
    prior_day_standby: list[FreshnessMission]
    prior_day_returned_to_backlog: int
    constraints: list[FreshnessConstraint]
    message: str
