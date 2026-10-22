"""Analyses de sang Pulse : valeurs proposées (brouillon de Nourrir l'IA), validées, dernières mesures."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_NUMBER = {"ge": Decimal("-1000000"), "le": Decimal("1000000"), "max_digits": 14, "decimal_places": 4}


class LabResultIn(BaseModel):
    """Une valeur : nom de l'analyse, résultat chiffré OU texte (« négatif »), unité, norme du labo."""

    model_config = ConfigDict(extra="forbid")

    analyte: str = Field(min_length=1, max_length=120)
    value: Decimal | None = Field(default=None, **_NUMBER)
    value_text: str | None = Field(default=None, max_length=120)
    unit: str | None = Field(default=None, max_length=40)
    ref_low: Decimal | None = Field(default=None, **_NUMBER)
    ref_high: Decimal | None = Field(default=None, **_NUMBER)
    ref_text: str | None = Field(default=None, max_length=120)

    @field_validator("analyte", "value_text", "unit", "ref_text")
    @classmethod
    def strip_texts(cls, value: str | None) -> str | None:
        return (value or "").strip() or None if value is not None else None

    @model_validator(mode="after")
    def needs_a_value(self) -> "LabResultIn":
        if not self.analyte:
            raise ValueError("analyte is empty.")
        if self.value is None and not self.value_text:
            raise ValueError("A result needs a value or a text value.")
        return self


class LabResultCreate(LabResultIn):
    """Saisie à la main d'une valeur (le résultat est validé par sa saisie même)."""

    measured_on: date


class LabResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    analyte: str
    analyte_key: str
    value: Decimal | None
    value_text: str | None
    unit: str | None
    ref_low: Decimal | None
    ref_high: Decimal | None
    ref_text: str | None
    measured_on: date
    source: str
    created_at: datetime


class LabPrevious(BaseModel):
    value: Decimal | None
    value_text: str | None
    measured_on: date


class LabLatestRead(LabResultRead):
    """Dernière valeur d'une analyse ; `position` = par rapport à la norme DU LABO (pas un diagnostic)."""

    position: Literal["below", "within", "above", "unknown"]
    previous: LabPrevious | None
    count: int


class LabLatestList(BaseModel):
    items: list[LabLatestRead]
    pending_inbox: int  # prises de sang lues dans Nourrir l'IA, à vérifier puis valider


class LabHistory(BaseModel):
    items: list[LabResultRead]
