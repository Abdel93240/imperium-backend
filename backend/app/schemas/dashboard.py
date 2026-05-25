from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.imperium import ActiveMissionRead
from app.schemas.path import PathTodayItemRead
from app.schemas.pulse import PulseEntryRead


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
    currency: str
    mission: ImperiumDashboardMissionSection
    vault: ImperiumDashboardVaultSection
    path: ImperiumDashboardPathSection
    pulse: ImperiumDashboardPulseSection
    readiness: ImperiumDashboardReadinessSection
    meta: ImperiumDashboardMetaSection
    safe_explanation: str = "Imperium dashboard snapshot for current user."
