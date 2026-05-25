from datetime import date

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.daily_plan import DailyPlanResponse
from app.services.imperium.daily_plan import get_daily_plan_snapshot
from app.services.imperium.missions import MultipleActiveMissionsError

router = APIRouter()


@router.get("/daily-plan", response_model=DailyPlanResponse)
def imperium_daily_plan_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    query_date: date | None = Query(default=None, alias="date"),
) -> DailyPlanResponse:
    try:
        return get_daily_plan_snapshot(
            db,
            current_user=current_user,
            local_date=query_date,
        )
    except MultipleActiveMissionsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Multiple active missions found for current user.",
        ) from exc
