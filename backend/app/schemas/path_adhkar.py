"""Adhkar Path (doc 41 §11) : routines et compteurs (PAT-06, PAT-11e)."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.path_worship import PrayerName

AdhkarType = Literal["morning", "evening", "istighfar", "salawat", "tasbih", "tahmid", "takbir", "personal"]
AdhkarFrequency = Literal["daily", "weekly", "per_prayer"]


class AdhkarRoutineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=64)
    adhkar_type: AdhkarType
    target_count: int = Field(ge=1, le=10000, strict=True)
    frequency: AdhkarFrequency = "daily"

    @field_validator("label")
    @classmethod
    def strip_label(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("label is empty.")
        return value.strip()


class AdhkarRoutineUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    label: str | None = Field(default=None, min_length=1, max_length=64)
    target_count: int | None = Field(default=None, ge=1, le=10000, strict=True)
    frequency: AdhkarFrequency | None = None
    active: bool | None = None


class AdhkarRoutineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    label: str
    adhkar_type: AdhkarType
    target_count: int
    frequency: AdhkarFrequency
    active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class AdhkarCounterRead(BaseModel):
    routine_id: UUID
    period_key: str
    count: int
    target_count: int
    target_reached: bool


class AdhkarRoutineWithCountRead(AdhkarRoutineRead):
    counters: list[AdhkarCounterRead]  # période en cours ; une par prière pour per_prayer


class AdhkarRoutineListResponse(BaseModel):
    day: date
    items: list[AdhkarRoutineWithCountRead]


class AdhkarSuggestionRead(BaseModel):
    label: str
    adhkar_type: AdhkarType
    target_count: int
    frequency: AdhkarFrequency


class AdhkarIncrementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: int = Field(default=1, ge=1, le=1000, strict=True)
    prayer: PrayerName | None = None  # obligatoire pour une routine per_prayer
    day: date | None = None  # absent : aujourd'hui (Paris)
    source: Literal["tap", "voice"] = "tap"
    confidence: float | None = Field(default=None, ge=0, le=1)  # comptage à la voix
    validated: bool = False  # confiance faible : l'utilisateur a relu le nombre

    @model_validator(mode="after")
    def voice_needs_confidence(self):
        if self.source == "voice" and self.confidence is None:
            raise ValueError("confidence is required for voice counting.")
        return self


class AdhkarResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_count: int = Field(ge=0)  # le compte affiché : différent → conflit (appuis en file)
    prayer: PrayerName | None = None
    day: date | None = None
