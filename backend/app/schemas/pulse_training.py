"""Programme d'entraînement Pulse, cibles et dette de volume (spec Pulse §3.6)."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Mesocycle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: str = Field(min_length=1, max_length=40)
    week_current: int = Field(ge=1, le=52)
    weeks_total: int = Field(ge=1, le=52)
    progression_model: str | None = Field(default=None, max_length=60)


class ProgramCreate(BaseModel):
    """Programme saisi à la main ; il remplace le programme actif."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    mesocycle: Mesocycle
    objective_weights: dict[str, float] = Field(default_factory=dict, max_length=20)

    @field_validator("name", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ProgramRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    objective_weights: dict
    mesocycle: dict
    doctrine_sheet_code: str | None
    status: str
    version: int
    created_at: datetime


class ProgramStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["active", "paused", "completed"]


class TargetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    muscle_group: str = Field(min_length=1, max_length=40)
    target_sets: int = Field(ge=0, le=60)
    tolerance_sets: int = Field(default=2, ge=0, le=20)


class TargetsReplace(BaseModel):
    """Remplace les cibles d'une semaine (ramenée à son lundi)."""

    model_config = ConfigDict(extra="forbid")

    week_start: date
    targets: list[TargetIn] = Field(max_length=30)


class TargetRead(BaseModel):
    muscle_group: str
    target_sets: int
    tolerance_sets: int
    planned_sets: int


class DebtRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    muscle_group: str
    debt_sets: int
    status: str
    origin_workout_id: UUID
    repayment_workout_id: UUID | None
    created_at: datetime


class ProgramCurrentRead(BaseModel):
    program: ProgramRead | None
    week_start: date
    targets: list[TargetRead]
    debts: list[DebtRead]
