from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PulseEntryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_date: date
    sleep_hours: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("24"), max_digits=4, decimal_places=2)
    energy_level: int | None = Field(default=None, ge=1, le=10)
    fatigue_level: int | None = Field(default=None, ge=1, le=10)
    weight_kg: Decimal | None = Field(default=None, gt=Decimal("0"), max_digits=5, decimal_places=2)
    workout_done: bool | None = None
    workout_type: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("workout_type", "notes", mode="before")
    @classmethod
    def strip_optional_text(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            return None
        return stripped

    @model_validator(mode="after")
    def validate_business_rules(self) -> "PulseEntryCreate":
        business_values = (
            self.sleep_hours,
            self.energy_level,
            self.fatigue_level,
            self.weight_kg,
            self.workout_done,
            self.workout_type,
            self.notes,
        )
        if all(value is None for value in business_values):
            raise ValueError("At least one Pulse field must be provided.")
        if self.workout_done is False and self.workout_type is not None:
            raise ValueError("workout_type is forbidden when workout_done is false.")
        return self


class PulseEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entry_date: date
    sleep_hours: float | None
    energy_level: int | None
    fatigue_level: int | None
    weight_kg: float | None
    workout_done: bool | None
    workout_type: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class PulseEntryListResponse(BaseModel):
    items: list[PulseEntryRead]
    count: int
    limit: int
    offset: int
    safe_explanation: str = "Pulse entries for current user."


class PulseTodayResponse(BaseModel):
    date: date
    entry: PulseEntryRead | None
    safe_explanation: str = "Pulse today entry for current user."


class PulseStatsSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_count: int
    average_sleep_hours: float | None
    average_energy_level: float | None
    average_fatigue_level: float | None
    latest_weight_kg: float | None
    workout_count: int
    safe_explanation: str = "Pulse summary statistics for current user."
