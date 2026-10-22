"""Diète Pulse (doc 40 §10.4–§10.9) : recettes, plan de la semaine, préparations, courses."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.pulse import StockUnit

MealSlot = Literal["breakfast", "lunch", "dinner", "snack"]
_KCAL = {"ge": Decimal("0"), "le": Decimal("99999.9"), "max_digits": 6, "decimal_places": 1}
_GRAMS = {"ge": Decimal("0"), "le": Decimal("9999.9"), "max_digits": 5, "decimal_places": 1}
_WEIGHT = {"gt": Decimal("0"), "le": Decimal("5000"), "max_digits": 5, "decimal_places": 1}


def _texts(values: list[str]) -> list[str]:
    cleaned = [value.strip() for value in values]
    if any(not value for value in cleaned):
        raise ValueError("Empty line.")
    return cleaned


class IngredientIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    quantity: Decimal = Field(gt=0, le=100000, max_digits=9, decimal_places=3)
    unit: StockUnit

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name is empty.")
        return value.strip()


class RecipeCreate(BaseModel):
    """Recette pour `servings` portions ; apports PAR PORTION, facultatifs (jamais devinés par l'appli)."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    servings: int = Field(ge=1, le=60)
    portion_weight_g: Decimal | None = Field(default=None, **_WEIGHT)
    ingredients: list[IngredientIn] = Field(min_length=1, max_length=40)
    steps: list[str] = Field(min_length=1, max_length=40)
    packaging: list[str] = Field(default_factory=list, max_length=20)
    shelf_life_days: int | None = Field(default=None, ge=0, le=60)
    calories: Decimal | None = Field(default=None, **_KCAL)
    protein_g: Decimal | None = Field(default=None, **_GRAMS)
    carbs_g: Decimal | None = Field(default=None, **_GRAMS)
    fat_g: Decimal | None = Field(default=None, **_GRAMS)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title is empty.")
        return value.strip()

    @field_validator("steps", "packaging")
    @classmethod
    def strip_lines(cls, values: list[str]) -> list[str]:
        if any(len(value) > 1000 for value in values):
            raise ValueError("Line too long.")
        return _texts(values)


class IngredientRead(BaseModel):
    name: str
    quantity: Decimal
    unit: str


class RecipeRead(BaseModel):
    id: UUID
    title: str
    servings: int
    portion_weight_g: Decimal | None
    ingredients: list[IngredientRead]
    steps: list[str]
    packaging: list[str]
    shelf_life_days: int | None
    calories: Decimal | None
    protein_g: Decimal | None
    carbs_g: Decimal | None
    fat_g: Decimal | None
    source: str
    status: str
    created_at: datetime


class RecipeListRead(BaseModel):
    items: list[RecipeRead]


class PlanRequest(BaseModel):
    """Demande au cerveau la semaine du `week_start` (lundi ; défaut : semaine en cours) ; consigne facultative."""

    model_config = ConfigDict(extra="forbid")

    week_start: date | None = None
    note: str | None = Field(default=None, max_length=500)


class MissingLine(BaseModel):
    name: str
    quantity: Decimal
    unit: str
    available: Decimal  # déjà en stock, dans la même unité


class PlanMealRead(BaseModel):
    id: UUID
    day: date
    slot: str
    recipe_id: UUID
    recipe_title: str
    portions: Decimal
    status: str
    meal_id: UUID | None
    calories: Decimal | None  # apports prévus = apports par portion × portions ; inconnus → null
    protein_g: Decimal | None
    carbs_g: Decimal | None
    fat_g: Decimal | None


class PreparationRead(BaseModel):
    id: UUID
    plan_id: UUID
    recipe_id: UUID
    recipe_title: str
    planned_day: date
    portions_planned: int
    portion_weight_g_planned: Decimal | None
    status: str
    missing: list[MissingLine]
    started_at: datetime | None
    done_at: datetime | None
    portions_made: int | None
    portion_weight_g: Decimal | None
    stock_item_id: UUID | None


class NeedLine(BaseModel):
    """Ingrédient pour les portions prévues de la préparation, comparé au stock actif."""

    name: str
    quantity: Decimal
    unit: str
    available: Decimal
    enough: bool


class PreparationDetailRead(PreparationRead):
    recipe: RecipeRead
    needs: list[NeedLine]


class PlanRead(BaseModel):
    id: UUID
    week_start: date
    status: str
    source: str | None
    note: str | None
    rationale_fr: str | None
    error: str | None
    created_at: datetime
    activated_at: datetime | None
    meals: list[PlanMealRead]
    preparations: list[PreparationRead]


class WeekRead(BaseModel):
    """Semaine (lundi → dimanche) : plan validé et, à côté, la dernière demande pas encore tranchée."""

    week_start: date
    active: PlanRead | None
    pending: PlanRead | None
    shopping_open: int


class PreparationComplete(BaseModel):
    """Fin de préparation (P06) : portions réelles et poids commun d'une portion, préremplis et modifiables."""

    model_config = ConfigDict(extra="forbid")

    portions: int = Field(ge=1, le=100)
    portion_weight_g: Decimal | None = Field(default=None, **_WEIGHT)


class ShoppingItemRead(BaseModel):
    id: UUID
    plan_id: UUID
    name: str
    quantity: Decimal  # ce qui manque encore au stock
    unit: str
    status: str
    checked: bool


class ShoppingListRead(BaseModel):
    items: list[ShoppingItemRead]


class ShoppingItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checked: bool


class PulseAttentionRead(BaseModel):
    """Attention requise dans Imperium (`GET /diet/attention`) : une préparation ne démarre pas, il manque des ingrédients."""

    preparation_id: UUID
    recipe_title: str
    planned_day: date
    missing: list[MissingLine]
    message_fr: str

