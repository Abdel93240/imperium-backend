"""Séances de sport Pulse (doc 40 §13.1–§13.2)."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Intensity = Literal["low", "medium", "high"]
SessionType = Literal["strength", "hypertrophy", "cardio", "mobility", "technique", "mental"]


def _strip(cls, value: object) -> object:  # noqa: ARG001 (validateur partagé)
    return value.strip() if isinstance(value, str) else value


class ExerciseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    sets: int | None = Field(default=None, ge=1, le=50)
    reps: int | None = Field(default=None, ge=1, le=1000)
    duration_seconds: int | None = Field(default=None, ge=1, le=36000)
    weight_kg: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1000"), max_digits=6, decimal_places=2)
    notes: str | None = Field(default=None, max_length=500)
    muscle_group: str | None = Field(default=None, min_length=1, max_length=40)  # compte le volume du programme

    _strip_name = field_validator("name", mode="before")(_strip)


class ExerciseRead(ExerciseIn):
    model_config = ConfigDict(extra="ignore")

    done_sets: int | None = None
    done_reps: list[int] | None = None
    skipped: bool = False
    skip_reason: str | None = None


class WorkoutCreate(BaseModel):
    """Séance planifiée à la main (PUL-05)."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    planned_at: datetime
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    intensity: Intensity | None = None
    exercises: list[ExerciseIn] = Field(default_factory=list, max_length=50)
    equipment: list[str] = Field(default_factory=list, max_length=30)
    source_mission_id: UUID | None = None
    program_id: UUID | None = None
    session_type: SessionType | None = None
    systemic_load: int | None = Field(default=None, ge=1, le=10)

    _strip_title = field_validator("title", mode="before")(_strip)

    @field_validator("equipment")
    @classmethod
    def clean_equipment(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip()[:80] for value in values if value.strip()]
        return list(dict.fromkeys(cleaned))


class WorkoutUpdate(BaseModel):
    """Modification d'une séance planifiée : la version lue est obligatoire (doc 40 §8)."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=120)
    planned_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    intensity: Intensity | None = None
    exercises: list[ExerciseIn] | None = Field(default=None, max_length=50)
    equipment: list[str] | None = Field(default=None, max_length=30)
    session_type: SessionType | None = None
    systemic_load: int | None = Field(default=None, ge=1, le=10)

    _strip_title = field_validator("title", mode="before")(_strip)

    @model_validator(mode="after")
    def require_a_change(self) -> "WorkoutUpdate":
        if not (self.model_fields_set - {"version"}):
            raise ValueError("Nothing to update.")
        for required in ("title", "planned_at", "exercises", "equipment"):
            if required in self.model_fields_set and getattr(self, required) is None:
                raise ValueError(f"{required} cannot be null.")
        return self


class WorkoutStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body_state: str | None = Field(default=None, max_length=500)


class ExerciseResultIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    done_sets: int | None = Field(default=None, ge=0, le=50)
    done_reps: list[int] | None = Field(default=None, max_length=50)
    skipped: bool = False
    skip_reason: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def reason_when_skipped(self) -> "ExerciseResultIn":
        if self.skipped and not (self.skip_reason or "").strip():
            raise ValueError("skip_reason is required when an exercise is skipped.")
        if self.done_reps and any(rep < 0 or rep > 1000 for rep in self.done_reps):
            raise ValueError("done_reps out of range.")
        return self


class WorkoutCompleteRequest(BaseModel):
    """Fin de séance (PUL-06) ; les exercices sans résultat restent tels que planifiés."""

    model_config = ConfigDict(extra="forbid")

    intensity_score: int | None = Field(default=None, ge=1, le=10)
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    notes: str | None = Field(default=None, max_length=2000)
    results: list[ExerciseResultIn] = Field(default_factory=list, max_length=50)


class WorkoutSkipRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=300)

    @field_validator("reason")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason is empty.")
        return value.strip()


class WorkoutRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    status: str
    planned_at: datetime
    duration_minutes: int | None
    intensity: str | None
    exercises: list[ExerciseRead]
    equipment: list[str]
    source_mission_id: UUID | None
    program_id: UUID | None = None
    session_type: str | None = None
    systemic_load: int | None = None
    started_at: datetime | None
    completed_at: datetime | None
    actual_duration_minutes: int | None
    intensity_score: int | None
    body_state_at_start: str | None
    notes_post_workout: str | None
    skip_reason: str | None
    version: int
    created_at: datetime


class WorkoutListResponse(BaseModel):
    items: list[WorkoutRead]


class EquipmentCreate(BaseModel):
    """Matériel possédé (doc 40 §13-EQUIP), ajouté depuis les réglages."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    notes: str | None = Field(default=None, max_length=300)

    _strip_name = field_validator("name", mode="before")(_strip)


class EquipmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    notes: str | None
    status: str
    removed_at: datetime | None
    created_at: datetime


class EquipmentListResponse(BaseModel):
    items: list[EquipmentRead]
