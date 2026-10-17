"""Tableau de bord Pulse du jour (PUL-01, doc 40 §9).

Assemble ce qui existe pour un jour de Paris : saisie du jour (sommeil, énergie,
fatigue, poids, séance), repas validés et leurs totaux, eau bue, séances du jour,
dates limites du stock, et des bannières courtes. Lecture seule.

Le score santé n'est jamais affiché sans explication : tant qu'il n'est pas calculé,
il reste vide et une bannière « données incomplètes » le dit. Jeûne (Path), règles
médicales (doc 34) : pas encore. Douleurs : bannière sans détail.
"""

from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.imperium import PulseMeal
from app.schemas.pulse import FoodStockExpiryAlertRead, FoodStockExpiryRead
from app.schemas.pulse_dashboard import (
    DashboardBannerRead,
    DashboardHydrationRead,
    DashboardMealsRead,
    PulseDashboardRead,
)
from app.services.pulse import entries, expiry, hydration, meals, pain, workouts

HEALTH_SCORE_INCOMPLETE = "Score santé masqué : pas encore assez de données pour l'expliquer."


def build_dashboard(db: Session, *, current_user: User, day: date) -> PulseDashboardRead:
    meal_day = meals.list_day(db, current_user=current_user, day=day)
    start = datetime.combine(day, time.min, tzinfo=expiry.PARIS)
    drafts = db.scalar(
        select(func.count()).select_from(PulseMeal).where(
            PulseMeal.user_id == current_user.id, PulseMeal.status == "draft",
            PulseMeal.eaten_at >= start, PulseMeal.eaten_at < start + timedelta(days=1),
        )
    ) or 0
    water = hydration.day_view(db, current_user=current_user, day=day)
    report = expiry.compute_alerts(db, current_user=current_user, today=day)
    stock = FoodStockExpiryRead(
        today=report.today, level=report.level, to_consume=report.to_consume, message_fr=report.message_fr,
        alerts=[FoodStockExpiryAlertRead(**alert.__dict__) for alert in report.alerts],
    )
    banners = []
    if report.message_fr:
        banners.append(DashboardBannerRead(kind="stock_expiry", level=report.level, message=report.message_fr))
    open_pain, strong_pain = pain.open_summary(db, current_user=current_user)
    if open_pain:
        message = f"{open_pain} douleur{'s' if open_pain > 1 else ''} en cours"
        message += f", dont {strong_pain} forte{'s' if strong_pain > 1 else ''}." if strong_pain else "."
        banners.append(DashboardBannerRead(kind="pain_open", level="warning" if strong_pain else "info", message=message))
    if drafts:
        banners.append(DashboardBannerRead(
            kind="meal_drafts", level="info",
            message=f"{drafts} repas en brouillon à valider.",
        ))
    if meal_day.meals_without_macros:
        count = meal_day.meals_without_macros
        banners.append(DashboardBannerRead(
            kind="meals_without_macros", level="info",
            message=f"{count} repas sans macros : les totaux sont incomplets.",
        ))
    banners.append(DashboardBannerRead(kind="health_score_incomplete", level="info", message=HEALTH_SCORE_INCOMPLETE))
    return PulseDashboardRead(
        day=day,
        entry=entries.get_pulse_today_entry(db, current_user=current_user, local_date=day).entry,
        meals=DashboardMealsRead(count=len(meal_day.meals), totals=meal_day.totals,
                                 without_macros=meal_day.meals_without_macros, drafts_pending=drafts),
        hydration=DashboardHydrationRead(total_ml=water.total_ml, target=water.target, target_message=water.target_message),
        workouts=workouts.list_workouts(db, current_user=current_user, from_day=day, to_day=day).items,
        stock=stock,
        banners=banners,
    )
