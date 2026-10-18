"""Réglages Path (PAT-11, doc 41 §6.4) : méthode de calcul, madhhab, ville."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CalculationMethod = Literal["MuslimWorldLeague", "Karachi", "Egypt", "ISNA"]
Madhhab = Literal["Hanafi", "Maliki", "Shafii", "Hanbali", "Jafari"]


class PathCity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    latitude: Decimal = Field(ge=-90, le=90, decimal_places=6)
    longitude: Decimal = Field(ge=-180, le=180, decimal_places=6)


class PathSettingsUpdate(BaseModel):
    """Champs absents : inchangés. `city: null` revient à Paris."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=0)
    calculation_method: CalculationMethod | None = None
    madhhab: Madhhab | None = None
    city: PathCity | None = None


class PathSettingsRead(BaseModel):
    calculation_method: str
    madhhab: str
    city: PathCity | None
    version: int  # 0 tant que l'utilisateur n'a rien enregistré
    updated_at: datetime | None
    location_source: Literal["mosque", "city", "default"]
    times_source: Literal["mawaqit", "calculated"]
    supported_methods: list[str]
    supported_madhhabs: list[str]
