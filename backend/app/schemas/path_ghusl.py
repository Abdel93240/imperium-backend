"""Ghusl Path (doc 41 §10) : état requis (PAT-04) et adresses (PAT-10)."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

GhuslAddressType = Literal["home", "mosque", "gym", "work", "other"]


class GhuslCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_id: UUID  # l'activation lue : une activation plus récente ouvre un conflit


class GhuslStateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: Literal["required", "completed"]
    required_since: datetime
    completed_at: datetime | None
    next_prayer: str | None
    mission_id: UUID | None
    replan_event_id: UUID | None
    replan_status: Literal["pending", "requested", "no_open_day", "replan_in_progress", "failed"]


class GhuslCurrentRead(BaseModel):
    ghusl_required: bool
    state: GhuslStateRead | None  # activation en cours, sinon la dernière
    message: str | None


class GhuslAddressCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=100)
    address_type: GhuslAddressType
    address_text: str | None = Field(default=None, max_length=500)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, decimal_places=6)
    is_default: bool = False

    @field_validator("label")
    @classmethod
    def strip_label(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("label is empty.")
        return value.strip()

    @model_validator(mode="after")
    def coordinates_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude go together.")
        return self


class GhuslAddressUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    label: str | None = Field(default=None, min_length=1, max_length=100)
    address_type: GhuslAddressType | None = None
    address_text: str | None = Field(default=None, max_length=500)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, decimal_places=6)
    is_default: bool | None = None


class GhuslAddressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    label: str
    address_type: GhuslAddressType
    address_text: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    is_default: bool
    version: int
    created_at: datetime
    updated_at: datetime


class GhuslAddressListResponse(BaseModel):
    items: list[GhuslAddressRead]
