"""Mosquées enregistrées (PAT-09, doc 41 §6.3) : la mosquée par défaut sert de référence aux horaires."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MosqueCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, decimal_places=6)
    mawaqit_id: str | None = Field(default=None, max_length=128)
    is_default: bool = False

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


class MosqueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str | None
    address: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    mawaqit_id: str | None
    is_default: bool
    version: int
    added_at: datetime


class MosqueListResponse(BaseModel):
    items: list[MosqueRead]
    times_source: str  # mawaqit (cache de la mosquée par défaut) ou calculated
