"""Coran Path (doc 41 §12) : point de reprise (PAT-07), objectif, plans de lecture."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

QuranPlanType = Literal["daily_pages", "finish_in_days", "juz_based"]


class QuranLocationRead(BaseModel):
    page: int
    juz: int
    surah: int  # sourate en cours en haut de la page
    surahs_on_page: list[int]


class QuranProgressRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int | None = Field(default=None, ge=1, le=604, strict=True)
    surah: int | None = Field(default=None, ge=1, le=114, strict=True)  # début de la sourate
    juz: int | None = Field(default=None, ge=1, le=30, strict=True)  # début du juz
    base_version: int | None = Field(default=None, ge=1)  # requis si un point existe déjà
    confirm_regression: bool = False

    @model_validator(mode="after")
    def exactly_one(self):
        if sum(value is not None for value in (self.page, self.surah, self.juz)) != 1:
            raise ValueError("Give exactly one of page, surah or juz.")
        return self


class QuranObjectiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daily_objective_pages: int | None = Field(ge=1, le=604)


class QuranKhatmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: Literal[True]
    base_version: int = Field(ge=1)


class QuranPlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_type: QuranPlanType
    pages_per_day: int | None = Field(default=None, ge=1, le=604, strict=True)  # daily_pages
    end_date: date | None = None  # finish_in_days
    juz_per_day: int | None = Field(default=None, ge=1, le=30, strict=True)  # juz_based


class QuranPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_type: QuranPlanType
    pages_per_day: int
    end_date: date | None
    start_page: int
    started_on: date
    active: bool
    ended_at: datetime | None


class QuranPlanTodayRead(BaseModel):
    plan: QuranPlanRead
    page_planned_today: int  # page visée en fin de journée selon le plan (repère, jamais un rattrapage)


class QuranContinuationRead(BaseModel):
    started: bool
    location: QuranLocationRead | None  # dernier point validé
    resume_page: int | None  # page suivante à lire
    last_validated_at: datetime | None
    daily_objective_pages: int | None
    khatm_count: int
    khatm_available: bool  # page 604 validée : le khatm peut être confirmé
    version: int | None
    plan: QuranPlanTodayRead | None
