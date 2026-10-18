"""Prières marquées (PAT-02, doc 41 §7) et jeûne (PAT-05, doc 41 §8)."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

PrayerName = Literal["fajr", "dhuhr", "asr", "maghrib", "isha"]
PrayerStatus = Literal["accomplished", "not_marked_as_accomplished"]
FastingType = Literal["monday_thursday", "white_days", "ramadan", "custom", "temporary"]


class PrayerMarkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prayer_date: date
    status: PrayerStatus
    prayed_at: datetime | None = None  # accomplished seulement ; absent : maintenant
    note: str | None = Field(default=None, max_length=500)
    base_version: int | None = Field(default=None, ge=1)  # requis pour changer un statut déjà posé


class PrayerClearRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prayer_date: date
    base_version: int = Field(ge=1)


class PrayerRead(BaseModel):
    prayer_name: PrayerName
    prayer_date: date
    adhan_at: datetime
    status: PrayerStatus | None
    prayed_at: datetime | None
    note: str | None
    version: int | None
    log_id: UUID | None


class PrayerDayRead(BaseModel):
    day: date
    times_source: Literal["mawaqit", "calculated"]
    prayers: list[PrayerRead]


class FastStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fasting_type: FastingType
    fasting_date: date | None = None  # absent : aujourd'hui (Paris)
    hydration_daytime_allowed: bool = False


class FastEndRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ended_at: datetime | None = None  # absent : maintenant ; correction après coup acceptée


class FastBreakRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: Literal[True]
    broken_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=500)


class FastCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: Literal[True]


class FastCancelResult(BaseModel):
    cancelled: bool
    fast_id: UUID


class FastRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    fasting_date: date
    fasting_type: FastingType
    status: Literal["active", "ended", "broken"]
    started_at: datetime
    suhoor_at: datetime
    iftar_at: datetime
    times_source: str
    hydration_daytime_allowed: bool
    ended_at: datetime | None
    broken_at: datetime | None
    break_reason: str | None
    version: int


class FastingStateRead(BaseModel):
    """État lu par Pulse et l'écran : `fasting_active` vrai seulement entre suhoor et iftar."""

    fasting_active: bool
    fast: FastRead | None
    hydration_limits: dict[str, bool]
    message: str | None


class FastListResponse(BaseModel):
    items: list[FastRead]
