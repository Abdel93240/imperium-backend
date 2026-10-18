"""Sessions VTC Vector (doc 59 §14) : démarrage, saisies, dépose, revue, clôture."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

ExpenseCategory = Literal["carburant", "peage", "parking", "entretien", "plateformes", "autre"]


class SessionStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_ca_cents: int | None = Field(default=None, ge=1, le=10_000_000, strict=True)
    strategic_direction: str | None = Field(default=None, max_length=120)
    mission_id: UUID | None = None


class SessionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    target_ca_cents: int | None = Field(default=None, ge=1, le=10_000_000, strict=True)
    strategic_direction: str | None = Field(default=None, max_length=120)


class ManualRevenueCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_cents: int = Field(gt=0, le=10_000_000, strict=True)
    occurred_at: datetime | None = None
    zone: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=300)
    wallet: str = Field(default="cash", min_length=1, max_length=80)


class ManualExpenseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_cents: int = Field(gt=0, le=10_000_000, strict=True)
    category: ExpenseCategory
    occurred_at: datetime | None = None
    note: str | None = Field(default=None, max_length=300)
    wallet: str = Field(default="cash", min_length=1, max_length=80)


class DropZoneCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone: str = Field(min_length=1, max_length=120)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, decimal_places=6)
    gps_confidence: Decimal | None = Field(default=None, ge=0, le=1, decimal_places=2)
    real_duration_minutes: int | None = Field(default=None, ge=1, le=600)

    @model_validator(mode="after")
    def coordinates_pair(self):
        if not self.zone.strip():
            raise ValueError("zone is empty.")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude go together.")
        return self


class DropZoneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    zone: str
    latitude: Decimal | None
    longitude: Decimal | None
    gps_confidence: Decimal | None
    real_duration_minutes: int | None
    recorded_at: datetime


class SessionComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_note: str | None = Field(default=None, max_length=2000)


class SessionKpis(BaseModel):
    revenue_cents: int
    expense_cents: int
    net_cents: int
    revenue_entries: int
    expense_entries: int
    drop_zones: int
    elapsed_minutes: int
    target_progress: Decimal | None  # CA / cible, None sans cible
    objective_reached: bool | None  # None sans cible


class SessionRead(BaseModel):
    id: UUID
    status: Literal["active", "completed"]
    started_at: datetime
    ended_at: datetime | None
    target_ca_cents: int | None
    strategic_direction: str | None
    mission_id: UUID | None
    review_note: str | None
    version: int
    kpis: SessionKpis


class CurrentSessionRead(BaseModel):
    session: SessionRead | None


class SessionListResponse(BaseModel):
    items: list[SessionRead]


class SessionEntryResult(BaseModel):
    transaction_id: UUID
    session: SessionRead
