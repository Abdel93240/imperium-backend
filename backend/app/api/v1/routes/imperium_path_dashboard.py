"""Tableau de bord Path (PAT-01, doc 59 §16.1)."""

from datetime import date

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.path_dashboard import PathDashboardRead
from app.services.path import dashboard, fasting

router = APIRouter()


@router.get("/dashboard", response_model=PathDashboardRead)
def path_dashboard_route(current_user: CurrentUserDep, db: SessionDep, day: date | None = None) -> PathDashboardRead:
    """Vue du jour de Paris (aujourd'hui par défaut) : prières, jeûne, sadaqa, ghusl, adhkar, Coran, qibla."""
    return dashboard.build_dashboard(db, current_user=current_user, day=day or fasting.paris_today())
