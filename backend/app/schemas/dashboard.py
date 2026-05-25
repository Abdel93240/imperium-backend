from datetime import date

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


class ImperiumDashboardFoundationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    currency: str
    mission: ImperiumDashboardMissionSection
    vault: ImperiumDashboardVaultSection
    path: ImperiumDashboardPathSection
    pulse: ImperiumDashboardPulseSection
    safe_explanation: str = "Imperium dashboard snapshot for current user."
