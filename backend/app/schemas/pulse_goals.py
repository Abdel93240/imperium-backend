"""Objectifs Pulse : écrits et classés par l'utilisateur ; base du programme d'entraînement et de la diète."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


class GoalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=500)

    _strip_texts = field_validator("title", "notes", mode="before")(lambda cls, value: _strip(value))


class GoalUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=500)
    status: Literal["active", "achieved"] | None = None

    _strip_texts = field_validator("title", "notes", mode="before")(lambda cls, value: _strip(value))


class GoalOrder(BaseModel):
    """Nouvel ordre des objectifs en cours : tous leurs identifiants, du plus important au moins important."""

    model_config = ConfigDict(extra="forbid")

    ids: list[UUID] = Field(min_length=1, max_length=50)


class GoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    notes: str | None
    rank: int
    status: str
    achieved_at: datetime | None
    created_at: datetime


class GoalList(BaseModel):
    items: list[GoalRead]  # en cours, par rang
    achieved: list[GoalRead]  # atteints, le plus récent d'abord
