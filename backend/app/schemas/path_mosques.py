"""Mosquées enregistrées (PAT-09, doc 41 §6.3) : la mosquée par défaut sert de référence aux horaires."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Prayer = Literal["fajr", "dhuhr", "asr", "maghrib", "isha"]
# Décalage de l'adhan de la mosquée par rapport au calcul local (minutes, signé) ; attente adhan → iqama.
AdhanOffsets = dict[Prayer, Annotated[int, Field(ge=-120, le=120)]]
IqamaOffsets = dict[Prayer, Annotated[int, Field(ge=0, le=90)]]


class MosqueCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, decimal_places=6)
    mawaqit_id: str | None = Field(default=None, max_length=128)
    is_default: bool = False
    adhan_offsets: AdhanOffsets = Field(default_factory=dict)
    iqama_offsets: IqamaOffsets = Field(default_factory=dict)

    @model_validator(mode="after")
    def check(self):
        if not self.name.strip():
            raise ValueError("name is empty.")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude go together.")
        return self


class MosqueUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, decimal_places=6)
    mawaqit_id: str | None = Field(default=None, max_length=128)
    is_default: bool | None = None
    adhan_offsets: AdhanOffsets | None = None
    iqama_offsets: IqamaOffsets | None = None


class MosqueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str | None
    address: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    mawaqit_id: str | None
    is_default: bool
    adhan_offsets: dict = Field(default_factory=dict)
    iqama_offsets: dict = Field(default_factory=dict)
    version: int
    added_at: datetime


class MosqueListResponse(BaseModel):
    items: list[MosqueRead]
    times_source: str  # mawaqit (cache de la mosquée par défaut) ou calculated


class MosqueDetailRead(BaseModel):
    """PAT-08 : horaires d'un jour pour une mosquée (cache MAWAQIT + calcul local) et qibla."""

    mosque: MosqueRead
    day: date
    times: dict[str, str]  # HH:MM, source principale
    times_source: Literal["mawaqit", "calculated"]
    mawaqit_times: dict[str, str] | None
    mawaqit_data_quality: Literal["fresh", "stale", "expired", "missing"]
    mawaqit_fetched_at: datetime | None
    calculated_times: dict[str, str]
    calculation_location: Literal["mosque", "city", "default"]
    qibla_direction_degrees: float | None  # sans coordonnées : pas de qibla propre à la mosquée
    message: str | None
