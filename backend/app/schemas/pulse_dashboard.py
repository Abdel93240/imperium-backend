"""Tableau de bord Pulse du jour (PUL-01, doc 40 §9) : lecture seule, aucun calcul de santé."""

from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.schemas.pulse import FoodStockExpiryRead, PulseEntryRead
from app.schemas.pulse_meals import MealTotalsRead
from app.schemas.pulse_workouts import WorkoutRead


class DashboardMealsRead(BaseModel):
    count: int
    totals: MealTotalsRead
    without_macros: int
    drafts_pending: int  # brouillons du jour pas encore validés


class DashboardHydrationRead(BaseModel):
    total_ml: int
    target: dict | None
    target_message: str | None


class DashboardBannerRead(BaseModel):
    kind: Literal["red_flag", "stock_expiry", "pain_open", "medical_rules", "fasting", "meal_drafts", "meals_without_macros", "health_score_incomplete"]
    level: Literal["info", "warning", "error"]
    message: str


class PulseDashboardRead(BaseModel):
    day: date
    entry: PulseEntryRead | None  # sommeil, énergie, fatigue, poids, séance du jour
    meals: DashboardMealsRead
    hydration: DashboardHydrationRead
    workouts: list[WorkoutRead]  # séances du jour, de la plus tôt à la plus tard
    stock: FoodStockExpiryRead
    health_score: None = None  # jamais affiché sans explication (doc 40 §9) : pas encore calculé
    banners: list[DashboardBannerRead]
