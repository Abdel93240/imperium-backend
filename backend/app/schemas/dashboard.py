from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.imperium import ActiveMissionRead
from app.schemas.path import PathTodayItemRead
from app.schemas.pulse import PulseEntryRead
from app.schemas.vault import VaultDailyTargets


class ImperiumDashboardMissionSection(BaseModel):
    active_mission: ActiveMissionRead | None
    safe_explanation: str


class ImperiumDashboardVaultSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str
    total_income_cents: int
    total_expense_cents: int
    net_cents: int
    transaction_count: int
    income_count: int
    expense_count: int
    safe_explanation: str = "Vault summary computed from current user's ledger transactions."


class ImperiumDashboardPathSection(BaseModel):
    date: date
    items: list[PathTodayItemRead]
    count: int
    safe_explanation: str


class ImperiumDashboardPulseSection(BaseModel):
    date: date
    entry: PulseEntryRead | None
    safe_explanation: str


class ImperiumDashboardReadinessSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission_available: bool
    vault_available: bool
    path_available: bool
    pulse_available: bool
    active_mission_present: bool
    vault_transaction_count: int
    path_today_count: int
    pulse_entry_present: bool
    safe_explanation: str = "Dashboard readiness snapshot computed from read-only module data."


class ImperiumDashboardMetaSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_generated_at: datetime
    dashboard_version: str
    included_modules: list[str]
    read_only: bool
    safe_explanation: str = "Dashboard metadata for current snapshot."


class ImperiumDashboardFoundationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    day_status: Literal["not_started", "open"]
    currency: str
    mission: ImperiumDashboardMissionSection
    vault: ImperiumDashboardVaultSection
    path: ImperiumDashboardPathSection
    pulse: ImperiumDashboardPulseSection
    readiness: ImperiumDashboardReadinessSection
    meta: ImperiumDashboardMetaSection
    safe_explanation: str = "Imperium dashboard snapshot for current user."


class DashboardNextPrayerWidget(BaseModel):
    """Compte à rebours de la prochaine prière (doc 59 §12.2) ; mêmes horaires que Path."""

    prayer_name: Literal["fajr", "dhuhr", "asr", "maghrib", "isha"]
    adhan_at: datetime
    countdown_seconds: int
    source: Literal["mawaqit", "calculated"]


class DashboardPressureWidget(BaseModel):
    """Score de pression calculé à la lecture, sans instantané ni événement (doc 11)."""

    score: int = Field(ge=0, le=100)
    label: Literal["safe", "stable", "attention", "pressure", "critical"]
    daily_targets: VaultDailyTargets
    computed_at: datetime


class ImperiumDashboardWidgetsResponse(BaseModel):
    next_prayer: DashboardNextPrayerWidget
    pressure: DashboardPressureWidget
    generated_at: datetime
