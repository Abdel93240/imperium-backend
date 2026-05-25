from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator


class PathHabitFrequency(StrEnum):
    daily = "daily"
    weekly = "weekly"


class PathCheckInStatus(StrEnum):
    done = "done"
    missed = "missed"


class PathTodayStatus(StrEnum):
    pending = "pending"
    done = "done"
    missed = "missed"


SUPPORTED_PATH_HABIT_DOMAINS = {"worship", "health", "discipline", "family", "work", "custom"}


class PathHabitCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    domain: str | None = Field(default=None, max_length=80)
    frequency: PathHabitFrequency

    @field_validator("title", "description", "domain", mode="before")
    @classmethod
    def strip_habit_text(cls, value: object, info: ValidationInfo) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            if info.field_name == "title":
                raise ValueError("Value cannot be empty.")
            return None
        return stripped

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.lower()
        if normalized not in SUPPORTED_PATH_HABIT_DOMAINS:
            allowed = ", ".join(sorted(SUPPORTED_PATH_HABIT_DOMAINS))
            raise ValueError(f"domain must be one of {allowed}.")
        return normalized


class PathCheckInCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_date: date
    status: PathCheckInStatus
    reason: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("reason", "note", mode="before")
    @classmethod
    def strip_check_in_text(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            return None
        return stripped

    @model_validator(mode="after")
    def validate_reason(self) -> "PathCheckInCreate":
        if self.status == PathCheckInStatus.missed and self.reason is None:
            raise ValueError("reason is required when status is missed.")
        if self.status == PathCheckInStatus.done and self.reason is not None:
            raise ValueError("reason must be null when status is done; use note for comments.")
        return self


class PathHabitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    domain: str | None
    frequency: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


PathHabitLifecycleStatus = Literal["archived", "reactivated", "already_archived", "already_active"]
PathHabitLifecycleGuardrail = Literal["OWNERSHIP_CONFIRMED", "IDEMPOTENCY_KEY_ACCEPTED"]


class PathHabitLifecycleSummary(BaseModel):
    status: PathHabitLifecycleStatus
    guardrails_checked: list[PathHabitLifecycleGuardrail]
    safe_explanation: str


class PathHabitLifecycleResponse(BaseModel):
    habit: PathHabitRead
    lifecycle_summary: PathHabitLifecycleSummary


class PathCheckInRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    habit_id: UUID
    check_date: date
    status: str
    reason: str | None
    note: str | None
    created_at: datetime


class PathHabitListResponse(BaseModel):
    items: list[PathHabitRead]
    count: int
    limit: int
    offset: int
    safe_explanation: str


class PathCheckInListResponse(BaseModel):
    items: list[PathCheckInRead]
    count: int
    limit: int
    offset: int
    safe_explanation: str


class PathTodayItemRead(BaseModel):
    habit: PathHabitRead
    check_in: PathCheckInRead | None
    status: PathTodayStatus


class PathTodayResponse(BaseModel):
    date: date
    items: list[PathTodayItemRead]
    count: int
    safe_explanation: str
