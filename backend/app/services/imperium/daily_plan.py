from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.core.dates import get_default_local_date
from app.models.auth import User
from app.schemas.daily_plan import (
    DailyPlanMetaSection,
    DailyPlanReadinessSection,
    DailyPlanResponse,
    DailyPlanSummarySection,
)
from app.schemas.imperium import ActiveMissionResponse
from app.services.imperium.dashboard import get_imperium_dashboard_foundation
from app.services.imperium.missions import get_current_active_mission
from app.services.path.habits import get_path_today_view
from app.services.pulse.entries import get_pulse_today_entry


def get_daily_plan_snapshot(
    db: Session,
    *,
    current_user: User,
    local_date: date | None = None,
) -> DailyPlanResponse:
    snapshot_date = local_date or get_default_local_date()
    dashboard = get_imperium_dashboard_foundation(
        db,
        current_user=current_user,
        local_date=snapshot_date,
    )

    mission = get_current_active_mission(db, current_user=current_user)
    path = get_path_today_view(
        db,
        current_user=current_user,
        local_date=snapshot_date,
        domain=None,
        frequency=None,
    )
    pulse = get_pulse_today_entry(
        db,
        current_user=current_user,
        local_date=snapshot_date,
    )

    return DailyPlanResponse(
        date=snapshot_date,
        dashboard=dashboard,
        mission=ActiveMissionResponse(
            mission=mission.mission,
            safe_explanation=mission.safe_explanation,
        ),
        path=path,
        pulse=pulse,
        readiness=DailyPlanReadinessSection(
            dashboard_present=dashboard is not None,
            mission_present=mission.mission is not None,
            path_items_count=path.count,
            pulse_entry_present=pulse.entry is not None,
            read_only=True,
        ),
        summary=DailyPlanSummarySection(
            has_active_mission=mission.mission is not None,
            path_items_count=path.count,
            pulse_entry_present=pulse.entry is not None,
        ),
        meta=DailyPlanMetaSection(
            snapshot_generated_at=datetime.now(UTC),
            daily_plan_version="v1",
            read_only=True,
        ),
    )
