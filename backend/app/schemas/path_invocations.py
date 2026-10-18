"""Invocations à lire (doc 41 §11-bis) : bibliothèque par situation, favoris, matin et soir."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Situation = Literal["quotidien", "voyage", "protection", "difficulte", "maladie", "peur_anxiete"]
Period = Literal["morning", "evening"]


def _strip(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


class InvocationCreate(BaseModel):
    """Contenu validé par l'utilisateur ; la source est obligatoire (l'IA n'est jamais la source)."""

    model_config = ConfigDict(extra="forbid")

    situation: Situation
    arabic_text: str = Field(min_length=1, max_length=5000)
    translation_fr: str = Field(min_length=1, max_length=5000)
    source: str = Field(min_length=1, max_length=500)
    audio_url: str | None = Field(default=None, max_length=1000, pattern=r"^https://")
    daily_period: Period | None = None
    daily_order: int | None = Field(default=None, ge=1, le=200)

    _strip_texts = field_validator("arabic_text", "translation_fr", "source", "audio_url")(_strip)

    @model_validator(mode="after")
    def check(self):
        if not (self.arabic_text and self.translation_fr and self.source):
            raise ValueError("arabic_text, translation_fr and source are required.")
        if (self.daily_period is None) != (self.daily_order is None):
            raise ValueError("daily_period and daily_order go together.")
        return self


class InvocationUpdate(BaseModel):
    """Champs absents : inchangés. daily_period et daily_order à null retirent l'invocation du matin/soir."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    situation: Situation | None = None
    arabic_text: str | None = Field(default=None, min_length=1, max_length=5000)
    translation_fr: str | None = Field(default=None, min_length=1, max_length=5000)
    source: str | None = Field(default=None, min_length=1, max_length=500)
    audio_url: str | None = Field(default=None, max_length=1000, pattern=r"^https://")
    daily_period: Period | None = None
    daily_order: int | None = Field(default=None, ge=1, le=200)


class InvocationFavoriteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_favorite: bool


class InvocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    situation: str
    arabic_text: str
    translation_fr: str
    source: str
    audio_url: str | None
    is_favorite: bool
    daily_period: str | None
    daily_order: int | None
    version: int
    created_at: datetime


class InvocationListResponse(BaseModel):
    items: list[InvocationRead]


class InvocationCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day: date | None = None  # jour de Paris ; aujourd'hui par défaut
    checked: bool = True


class DailyInvocationRead(BaseModel):
    invocation: InvocationRead
    checked: bool
    checked_at: datetime | None


class DailyBlockRead(BaseModel):
    items: list[DailyInvocationRead]
    done: int
    total: int


class DailyInvocationsResponse(BaseModel):
    day: date
    morning: DailyBlockRead
    evening: DailyBlockRead
