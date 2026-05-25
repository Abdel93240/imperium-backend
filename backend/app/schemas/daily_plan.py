from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.dashboard import ImperiumDashboardFoundationResponse
from app.schemas.imperium import ActiveMissionResponse
from app.schemas.path import PathTodayResponse
from app.schemas.pulse import PulseTodayResponse


class DailyPlanSummarySection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    has_active_mission: bool
    path_items_count: int
    pulse_entry_present: bool
    safe_explanation: str = "Daily plan summary computed from existing read-only snapshots."


class DailyPlanReadinessSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dashboard_present: bool
    mission_present: bool
    path_items_count: int
    pulse_entry_present: bool
    read_only: bool
    safe_explanation: str = "Daily plan readiness snapshot computed from existing read-only data."


class DailyPlanMetaSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_generated_at: datetime
    daily_plan_version: str
    read_only: bool
    safe_explanation: str = "Daily plan metadata snapshot."


class DailyPlanModuleSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: str
    read_only: bool


class DailyPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    dashboard: ImperiumDashboardFoundationResponse
    mission: ActiveMissionResponse
    path: PathTodayResponse
    pulse: PulseTodayResponse
    modules: list[DailyPlanModuleSection]
    readiness: DailyPlanReadinessSection
    summary: DailyPlanSummarySection
    meta: DailyPlanMetaSection
    safe_explanation: str = "Imperium daily plan snapshot for current user."
