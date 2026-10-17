"""Tableau de bord Pulse du jour (PUL-01, doc 40 §9)."""

from datetime import date

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.pulse_dashboard import PulseDashboardRead
from app.services.pulse.dashboard import build_dashboard
from app.services.pulse.expiry import paris_today

router = APIRouter()


@router.get("/dashboard", response_model=PulseDashboardRead)
def pulse_dashboard_route(current_user: CurrentUserDep, db: SessionDep, day: date | None = None) -> PulseDashboardRead:
    """Vue du jour de Paris (aujourd'hui par défaut) : saisie du jour, repas, eau, stock, bannières."""
    return build_dashboard(db, current_user=current_user, day=day or paris_today())
