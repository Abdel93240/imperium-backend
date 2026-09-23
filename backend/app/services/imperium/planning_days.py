import hashlib
import json
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dates import DEFAULT_LOCAL_TIMEZONE
from app.models.auth import User
from app.models.enums import IdempotencyStatus
from app.models.idempotency import IdempotencyKey
from app.models.imperium import PlanningDay
from app.schemas.imperium import (
    PlanningDayResponse,
    StartPlanningDayRequest,
    StartPlanningDayResponse,
)
from app.services.events.emitter import build_event


class PlanningDayAlreadyOpenError(ValueError):
    pass


class PlanningDayIdempotencyConflictError(ValueError):
    pass


class PlanningDayTimezoneError(ValueError):
    pass


def get_current_planning_day(db: Session, *, current_user: User) -> PlanningDay | None:
    """Return only the authenticated user's currently open operational day."""
    return db.scalar(
        select(PlanningDay).where(
            PlanningDay.user_id == current_user.id,
            PlanningDay.finished_at.is_(None),
        )
    )


def start_planning_day(
    db: Session,
    *,
    current_user: User,
    payload: StartPlanningDayRequest,
    request_method: str,
    request_path: str,
    now: datetime | None = None,
) -> tuple[StartPlanningDayResponse, bool]:
    request_hash = _hash_start_request(payload)
    existing_key = db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == current_user.id,
            IdempotencyKey.idempotency_key == payload.idempotency_key,
        )
    )
    if existing_key is not None:
        if existing_key.request_path != request_path:
            raise PlanningDayIdempotencyConflictError(
                "Idempotency-Key already used on a different endpoint."
            )
        if existing_key.request_hash != request_hash:
            raise PlanningDayIdempotencyConflictError(
                "Idempotency key already used with different payload."
            )
        if existing_key.response_body is None:
            raise PlanningDayIdempotencyConflictError("Idempotency key is already processing.")
        return StartPlanningDayResponse(**existing_key.response_body), True

    if get_current_planning_day(db, current_user=current_user) is not None:
        raise PlanningDayAlreadyOpenError("An operational day is already open.")

    started_at = now or datetime.now(UTC)
    if started_at.tzinfo is None:
        raise ValueError("Operational day start time must be timezone-aware.")
    started_at = started_at.astimezone(UTC)
    timezone = DEFAULT_LOCAL_TIMEZONE
    try:
        start_local_date = started_at.astimezone(ZoneInfo(timezone)).date()
    except ZoneInfoNotFoundError as exc:
        raise PlanningDayTimezoneError("Current user timezone is invalid.") from exc

    planning_day = PlanningDay(
        user_id=current_user.id,
        started_at=started_at,
        finished_at=None,
        start_local_date=start_local_date,
        timezone=timezone,
        felt_energy=payload.felt_energy,
        day_review_id=None,
        idempotency_key=payload.idempotency_key,
    )
    db.add(planning_day)
    db.flush()

    event = build_event(
        db,
        user_id=current_user.id,
        event_type="planning.day.started",
        payload={
            "planning_day_id": str(planning_day.id),
            "felt_energy": planning_day.felt_energy,
        },
        idempotency_key=payload.idempotency_key,
        occurred_at=started_at,
    )
    db.add(event)
    db.flush()

    response = StartPlanningDayResponse(
        planning_day=PlanningDayResponse.model_validate(planning_day),
        event_id=event.event_id,
    )
    db.add(
        IdempotencyKey(
            user_id=current_user.id,
            idempotency_key=payload.idempotency_key,
            request_method=request_method,
            request_path=request_path,
            request_hash=request_hash,
            status=IdempotencyStatus.completed,
            response_status_code=201,
            response_body=response.model_dump(mode="json"),
        )
    )
    db.commit()
    return response, False


def _hash_start_request(payload: StartPlanningDayRequest) -> str:
    canonical = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
