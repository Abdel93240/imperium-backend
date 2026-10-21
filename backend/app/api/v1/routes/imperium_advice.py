"""Conseil du jour du Dashboard (« Conseils IA », doc 65 §3) : route à part de la lecture seule du Dashboard."""

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from app.api.deps import CurrentUserDep, SessionDep
from app.services.imperium import advice

router = APIRouter()


class DashboardAdviceRead(BaseModel):
    title: str
    body: str
    source: str  # rules | local
    at: datetime


@router.get("/dashboard/advice", response_model=DashboardAdviceRead | None)
def dashboard_advice_route(
    background_tasks: BackgroundTasks, current_user: CurrentUserDep, db: SessionDep
) -> DashboardAdviceRead | None:
    """Conseil du jour ; null sans journée ouverte. L'état a changé : conseil des règles tout de suite, réécrit
    par le modèle local en arrière-plan pour la lecture suivante."""
    found, rewrite = advice.current(db, current_user=current_user)
    if rewrite:
        background_tasks.add_task(advice.refresh_in_background, current_user.id)
    return DashboardAdviceRead.model_validate(found) if found else None
