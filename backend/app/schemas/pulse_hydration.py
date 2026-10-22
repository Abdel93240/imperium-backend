"""Hydratation Pulse (doc 40 §12) : appuis rapides, journée, décompte de l'eau du stock."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.pulse import FoodStockItemRead


class HydrationLogCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_ml: int = Field(gt=0, le=5000, strict=True)
    drink: str | None = Field(default=None, max_length=80)  # absent : de l'eau ; sinon « Autre » en texte libre
    logged_at: datetime | None = None  # absent : maintenant ; une heure passée est acceptée (saisie après coup)
    source: Literal["quick", "manual", "chatbot"] = "quick"
    decrement_stock: bool = True


class HydrationLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    amount_ml: int
    drink: str | None = None
    logged_at: datetime
    source: str
    stock_decrement_applied: bool
    created_at: datetime


class HydrationLogResult(BaseModel):
    log: HydrationLogRead
    stock_items: list[FoodStockItemRead]
    warnings: list[str]


class HydrationDayRead(BaseModel):
    """Journée de Paris ; la cible personnalisée (min / bien / très bien) viendra du programme santé."""

    day: date
    total_ml: int
    logs: list[HydrationLogRead]
    target: dict | None
    target_message: str | None
