from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.dashboard import ImperiumDashboardFoundationResponse
from app.services.imperium.dashboard import get_imperium_dashboard_foundation
from app.services.imperium.missions import MultipleActiveMissionsError

router = APIRouter()


@router.get("/dashboard", response_model=ImperiumDashboardFoundationResponse)
def imperium_dashboard_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    query_date: date | None = Query(default=None, alias="date"),
    currency: Annotated[str, Query(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")] = "EUR",
) -> ImperiumDashboardFoundationResponse:
    try:
        return get_imperium_dashboard_foundation(
            db,
            current_user=current_user,
            local_date=query_date,
            currency=currency,
        )
    except MultipleActiveMissionsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Multiple active missions found for current user.",
        ) from exc
