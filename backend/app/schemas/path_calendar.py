"""Calendrier hégirien Path (doc 41 §14, 14-V3)."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

DateStatus = Literal["predicted", "confirmed"]


class HijriDayRead(BaseModel):
    gregorian: date
    hijri_year: int
    hijri_month: int
    hijri_day: int
    month_name: str
    status: DateStatus  # predicted : début de mois pas encore confirmé (± 1 jour)
    source: Literal["calculated", "confirmed"]
    white_day: bool
    sacred_month: bool
    ramadan: bool


class CalendarEventRead(BaseModel):
    kind: Literal["religious", "personal"]
    code: str  # ex. ramadan_start, eid_al_fitr, white_day_13, ou personal:<id>
    label: str
    hijri_year: int
    hijri_month: int
    hijri_day: int
    status: DateStatus
    dates: list[date]  # predicted : J et J+1 ; confirmed : une seule date
    event_id: UUID | None = None


class CalendarEventListResponse(BaseModel):
    from_day: date
    to_day: date
    items: list[CalendarEventRead]


class MonthStartConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hijri_year: int = Field(ge=1300, le=1700)
    hijri_month: int = Field(ge=1, le=12)
    first_day: date  # jour grégorien du 1er du mois, après l'observation


class MonthStartRead(BaseModel):
    hijri_year: int
    hijri_month: int
    month_name: str
    first_day: date
    status: DateStatus


class PersonalEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=500)
    hijri_year: int | None = Field(default=None, ge=1300, le=1700)  # vide : chaque année
    hijri_month: int = Field(ge=1, le=12)
    hijri_day: int = Field(ge=1, le=30)

    @field_validator("label")
    @classmethod
    def strip_label(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("label is empty.")
        return value.strip()


class PersonalEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    label: str
    note: str | None
    hijri_year: int | None
    hijri_month: int
    hijri_day: int
