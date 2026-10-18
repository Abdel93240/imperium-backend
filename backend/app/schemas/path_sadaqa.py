"""Sadaqa Path (doc 41 §9) : réglages, objectif de la semaine, dons."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SadaqaPendingChangeRead(BaseModel):
    percentage: Decimal
    safety_margin: Decimal
    applies_from: date


class SadaqaSettingsRead(BaseModel):
    percentage: Decimal
    safety_margin: Decimal
    applies_from: date | None  # None : valeurs par défaut, jamais modifiées
    pending: SadaqaPendingChangeRead | None
    changes_this_week: int
    version: int  # nombre de changements enregistrés ; à renvoyer en base_version


class SadaqaSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    percentage: Decimal | None = Field(default=None, ge=Decimal("0.01"), le=Decimal("0.20"), decimal_places=4)
    safety_margin: Decimal | None = Field(default=None, ge=Decimal("0.10"), le=Decimal("0.15"), decimal_places=4)
    base_version: int = Field(ge=0)
    apply_to_current_week: bool = False  # premier changement de la semaine seulement
    confirm_second_change: bool = False

    @model_validator(mode="after")
    def something_changes(self) -> "SadaqaSettingsUpdate":
        if self.percentage is None and self.safety_margin is None:
            raise ValueError("percentage or safety_margin is required.")
        return self


class SadaqaWeekRead(BaseModel):
    week_start: date
    week_end: date
    closed: bool
    business_profit: Decimal
    profit_source: Literal["vault_summary", "live", "snapshot"]
    percentage: Decimal
    safety_margin: Decimal
    base_target: Decimal  # max(bénéfice, 0) × pourcentage × (1 + marge)
    carried_in: Decimal  # montant reporté des semaines précédentes
    target: Decimal
    donated: Decimal
    remaining: Decimal
    carry_message: str | None
    vault_pending: int


class SadaqaDonationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_cents: int = Field(gt=0, le=10_000_000, strict=True)
    destination: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=500)
    donated_at: datetime | None = None
    record_in_vault: bool = True
    wallet: str = Field(default="cash", min_length=1, max_length=80)


class SadaqaAllocationLine(BaseModel):
    part: Literal["carry", "week_target", "beyond_target"]
    amount_cents: int


class SadaqaDonationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    amount_cents: int
    destination: str | None
    note: str | None
    donated_at: datetime
    related_week_start: date
    allocation: list[SadaqaAllocationLine]
    record_in_vault: bool
    wallet: str
    vault_status: Literal["not_requested", "pending", "recorded"]
    vault_transaction_id: UUID | None
    created_at: datetime


class SadaqaDonationResult(BaseModel):
    donation: SadaqaDonationRead
    week: SadaqaWeekRead
    warnings: list[str]


class SadaqaDonationListResponse(BaseModel):
    items: list[SadaqaDonationRead]


class SadaqaDonationDeleteResult(BaseModel):
    deleted: bool
    vault_reversed: bool
