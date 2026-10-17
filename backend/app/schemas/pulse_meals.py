"""Repas Pulse (doc 40 §10.1–§10.3) : brouillon, validation, décompte du stock."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.pulse import FoodStockItemRead, StockUnit

_KCAL = {"ge": Decimal("0"), "le": Decimal("99999.9"), "max_digits": 6, "decimal_places": 1}
_GRAMS = {"ge": Decimal("0"), "le": Decimal("9999.9"), "max_digits": 5, "decimal_places": 1}


class MealMacrosIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = Field(default=None, min_length=1, max_length=120)
    eaten_at: datetime | None = None
    calories: Decimal | None = Field(default=None, **_KCAL)
    protein_g: Decimal | None = Field(default=None, **_GRAMS)
    carbs_g: Decimal | None = Field(default=None, **_GRAMS)
    fat_g: Decimal | None = Field(default=None, **_GRAMS)


class MealDraftCreate(MealMacrosIn):
    """Saisie PUL-02 : texte tapé ou dicté ; les macros sont facultatives."""

    description: str = Field(min_length=1, max_length=2000)
    source: Literal["text", "voice", "manual", "chatbot"] = "text"

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("description is empty.")
        return value.strip()


class MealStockLineRead(BaseModel):
    """Ligne de décompte proposée ; `used_in_stock_unit` est None si les unités ne se convertissent pas."""

    index: int
    name: str
    quantity: Decimal
    unit: str
    stock_item_id: UUID | None = None
    stock_name: str | None = None
    stock_quantity: Decimal | None = None
    stock_unit: str | None = None
    used_in_stock_unit: Decimal | None = None
    confidence: Literal["high", "low"]
    checked: bool  # cochée par défaut seulement si la confiance est haute
    insufficient: bool = False


class MealStockDecrementIn(BaseModel):
    """Ligne cochée à la validation ; `finish` marque la ligne de stock finie (obligatoire si tout est utilisé)."""

    model_config = ConfigDict(extra="forbid")

    stock_item_id: UUID
    quantity: Decimal = Field(gt=Decimal("0"), max_digits=10, decimal_places=3)
    unit: StockUnit
    finish: bool = False


class MealConfirmRequest(MealMacrosIn):
    stock_lines: list[MealStockDecrementIn] = Field(default_factory=list, max_length=50)


class MealRead(BaseModel):
    id: UUID
    status: str
    label: str
    description: str
    source: str
    eaten_at: datetime
    calories: Decimal | None
    protein_g: Decimal | None
    carbs_g: Decimal | None
    fat_g: Decimal | None
    stock_lines: list[MealStockLineRead]
    warnings: list[str]
    stock_decrement_applied: bool
    stock_items: list[FoodStockItemRead] = Field(default_factory=list)
    confirmed_at: datetime | None
    created_at: datetime


class MealTotalsRead(BaseModel):
    calories: Decimal
    protein_g: Decimal
    carbs_g: Decimal
    fat_g: Decimal


class MealDayRead(BaseModel):
    """Repas validés d'un jour de Paris (PUL-10), du plus tôt au plus tard."""

    day: date
    meals: list[MealRead]
    totals: MealTotalsRead
    meals_without_macros: int
