"""Tableau de bord Path (PAT-01, doc 59 §16.1, doc 41 §19)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.path_adhkar import AdhkarRoutineWithCountRead
from app.schemas.path_ghusl import GhuslCurrentRead
from app.schemas.path_quran import QuranContinuationRead
from app.schemas.path_sadaqa import SadaqaWeekRead
from app.schemas.path_worship import FastingStateRead, PrayerDayRead, PrayerName


class NextPrayerRead(BaseModel):
    prayer_name: PrayerName
    adhan_at: datetime
    countdown_seconds: int


class QiblaRead(BaseModel):
    direction_degrees: float  # depuis le nord géographique, sens horaire
    location_source: Literal["reference_mosque", "default_city"]


class PathBannerRead(BaseModel):
    kind: Literal["ghusl_required", "fasting", "sadaqa_carry", "sadaqa_vault_pending"]
    level: Literal["info", "warning"]
    message: str


class PathDashboardRead(BaseModel):
    day: date
    prayers: PrayerDayRead
    next_prayer: NextPrayerRead | None  # None pour un autre jour qu'aujourd'hui
    fasting: FastingStateRead
    sadaqa: SadaqaWeekRead
    ghusl: GhuslCurrentRead
    adhkar: list[AdhkarRoutineWithCountRead]  # routines actives et compteurs du jour
    quran: QuranContinuationRead
    qibla: QiblaRead
    banners: list[PathBannerRead]
