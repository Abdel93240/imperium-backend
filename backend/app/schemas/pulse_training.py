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


# --- Programme conçu par le cerveau (P3, migration 0133) -------------------------------------------------------

Weekday = Literal["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
MUSCLE_GROUPS = ("chest", "back", "shoulders", "biceps", "triceps", "quads", "hamstrings", "glutes", "calves", "core")


class ProgramRequestCreate(BaseModel):
    """Ce que l'utilisateur donne au cerveau : niveau, jours, durée d'une séance, heure, précision facultative ; les
    objectifs eux-mêmes viennent de sa liste classée (accueil)."""

    model_config = ConfigDict(extra="forbid")

    goal: str | None = Field(default=None, max_length=300)  # précision pour ce programme
    level: Literal["beginner", "intermediate", "advanced"]
    days: list[Weekday] = Field(min_length=1, max_length=7)
    session_minutes: int = Field(ge=10, le=180)
    preferred_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    note: str | None = Field(default=None, max_length=500)

    @field_validator("goal", "note", mode="before")
    @classmethod
    def _strip_texts(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("days")
    @classmethod
    def _unique_days(cls, value: list[str]) -> list[str]:
        return sorted(set(value), key=["MO", "TU", "WE", "TH", "FR", "SA", "SU"].index)


class DesignExercise(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    muscle_group: str | None = None
    sets: int = Field(ge=1, le=10)
    reps: int | None = Field(default=None, ge=1, le=100)
    duration_seconds: int | None = Field(default=None, ge=10, le=3600)
    rest_seconds: int = Field(ge=0, le=300)
    equipment: list[str] = Field(default_factory=list, max_length=5)
    notes: str = Field(min_length=1, max_length=300)


class DesignSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekday: Weekday
    title: str = Field(min_length=1, max_length=120)
    session_type: Literal["strength", "hypertrophy", "cardio", "mobility", "technique", "mental"]
    duration_minutes: int = Field(ge=5, le=180)
    intensity: Literal["low", "medium", "high"]
    systemic_load: int = Field(ge=1, le=10)
    exercises: list[DesignExercise] = Field(min_length=1, max_length=12)


class ProgramDesign(BaseModel):
    """Sortie du cerveau relue par le code ; les cibles hebdomadaires se calculent depuis les séances."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    phase: str = Field(min_length=1, max_length=40)
    weeks_total: int = Field(ge=2, le=12)
    progression_fr: str = Field(min_length=1, max_length=400)
    recovery_fr: str = Field(min_length=1, max_length=400)
    rationale_fr: str = Field(min_length=1, max_length=600)
    sessions: list[DesignSession] = Field(min_length=1, max_length=7)


class ProgramRequestRead(BaseModel):
    id: UUID
    status: str
    inputs: dict
    design: ProgramDesign | None
    weekly_sets: dict[str, int]
    rationale_fr: str | None
    error: str | None
    program_id: UUID | None
    created_at: datetime


class ProgramRequestLatest(BaseModel):
    request: ProgramRequestRead | None
