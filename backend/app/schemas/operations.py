"""Contrats Opérations : projets, missions de projet, routines (doc 71 §3, §4.1, §8)."""

from datetime import date, datetime, time
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _strip(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- Projets ----------

class ProjectCreate(_Strict):
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    source: Literal["manual", "chatbot"] = "manual"

    @field_validator("title")
    @classmethod
    def require_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("title cannot be empty.")
        return stripped

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        return _strip(value)


class ProjectUpdate(_Strict):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=4000)

    @field_validator("title")
    @classmethod
    def non_blank_title(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("title cannot be empty.")
        return value.strip() if value else value


class ProjectReorderRequest(_Strict):
    project_ids: list[UUID] = Field(min_length=1, max_length=200)

    @field_validator("project_ids")
    @classmethod
    def no_duplicates(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("project_ids must not contain duplicates.")
        return value


class MissionReorderRequest(_Strict):
    mission_ids: list[UUID] = Field(min_length=1, max_length=500)

    @field_validator("mission_ids")
    @classmethod
    def no_duplicates(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("mission_ids must not contain duplicates.")
        return value


class ProjectProgressUpdate(_Strict):
    """Estimation de la Weekly Review (doc 71 §3.1) : pourcentage + justification."""

    percent: int = Field(ge=0, le=100)
    why: str = Field(max_length=1000)

    @field_validator("why")
    @classmethod
    def require_why(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("why cannot be empty.")
        return stripped


class ProjectMissionCreate(_Strict):
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=4000)
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)

    @field_validator("title")
    @classmethod
    def require_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("title cannot be empty.")
        return stripped

    @field_validator("description", "notes")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return _strip(value)


class MissionContentUpdate(_Strict):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=4000)
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)

    @field_validator("title")
    @classmethod
    def non_blank_title(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("title cannot be empty.")
        return value.strip() if value else value


class ProjectMissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    status: str
    description: str | None
    notes: str | None
    estimated_minutes: int | None
    project_position: int | None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    rank: int = Field(validation_alias="rank_order")
    active: bool = False
    status: str
    source: str
    progress_percent: int | None
    progress_why: str | None
    progress_at: datetime | None
    completed_at: datetime | None
    missions: list[ProjectMissionRead] = Field(default_factory=list)
    next_mission_title: str | None = None


class ProjectListResponse(BaseModel):
    projects: list[ProjectRead]
    active_count: int


# ---------- Routines ----------

class RoutineFrequency(StrEnum):
    daily = "daily"
    weekly = "weekly"
    biweekly = "biweekly"
    monthly = "monthly"


class RoutinePriority(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class RoutineCreate(_Strict):
    """Formulaire de la maquette 12 : pas de jour ni d'heure (doc 71 §4.1)."""

    name: str = Field(max_length=200)
    frequency: RoutineFrequency
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    priority: RoutinePriority = RoutinePriority.medium
    notes: str | None = Field(default=None, max_length=4000)
    active: bool = True

    @field_validator("name")
    @classmethod
    def require_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name cannot be empty.")
        return stripped

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, value: str | None) -> str | None:
        return _strip(value)


class RoutineUpdate(_Strict):
    """Modification ; pinned_* ne sont posés que par le chatbot (non affichés dans l'UI)."""

    name: str | None = Field(default=None, max_length=200)
    frequency: RoutineFrequency | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    priority: RoutinePriority | None = None
    notes: str | None = Field(default=None, max_length=4000)
    active: bool | None = None
    pinned_weekday: int | None = Field(default=None, ge=1, le=7)
    pinned_month_day: int | None = Field(default=None, ge=1, le=31)
    pinned_time: time | None = None
    clear_pins: bool = False

    @model_validator(mode="after")
    def non_blank_name(self) -> "RoutineUpdate":
        if self.name is not None and not self.name.strip():
            raise ValueError("name cannot be empty.")
        return self


class RoutineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    frequency: str
    estimated_minutes: int | None
    priority: str
    notes: str | None
    active: bool
    pinned_weekday: int | None
    pinned_month_day: int | None
    pinned_time: time | None
    anchor_date: date


class RoutineListResponse(BaseModel):
    routines: list[RoutineRead]


class RoutineTodayItem(BaseModel):
    routine_id: UUID
    name: str
    frequency: str
    estimated_minutes: int | None
    priority: str
    done: bool


class RoutineTodayResponse(BaseModel):
    operational_date: date | None
    items: list[RoutineTodayItem]
    total_minutes: int


class RoutineCheckRequest(_Strict):
    done: bool


class RoutinePlaceRequest(_Strict):
    """Placement d'une routine non quotidienne sur la journée en cours (planificateur ou chatbot)."""

    operational_date: date | None = None
