import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import IdempotencyStatus
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumWeeklyReviewState
from app.schemas.imperium import (
    DashboardWeeklyReviewBanner,
    WeeklyReviewLaunchResponse,
    WeeklyReviewStateResponse,
)

PARIS_TIMEZONE = "Europe/Paris"


class InvalidWeekStartError(ValueError):
    pass


class WeeklyReviewNotReadyError(ValueError):
    pass


class WeeklyReviewAlreadyLaunchedError(ValueError):
    pass


class IdempotencyConflictError(ValueError):
    pass


def get_or_create_weekly_review_state(
    db: Session,
    *,
    current_user: User,
    week_start: date,
) -> ImperiumWeeklyReviewState:
    _validate_week_start(week_start)
    state = _get_weekly_review_state(db, current_user=current_user, week_start=week_start)
    if state is not None:
        return state

    state = ImperiumWeeklyReviewState(
        user_id=current_user.id,
        week_start=week_start,
        ready=False,
        launched=False,
        analysis_status="pending",
    )
    db.add(state)
    db.flush()
    return state


def mark_weekly_review_ready(
    db: Session,
    *,
    current_user: User,
    week_start: date,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[WeeklyReviewStateResponse, bool]:
    _validate_week_start(week_start)
    request_hash = _hash_request("weekly_review.ready", {"week_start": week_start.isoformat()})
    existing_key = _get_existing_idempotency(db, current_user=current_user, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_ready_idempotency(existing_key, request_hash), True

    state = get_or_create_weekly_review_state(db, current_user=current_user, week_start=week_start)
    if state.ready:
        return WeeklyReviewStateResponse.model_validate(state), True

    state.ready = True
    state.ready_at = datetime.now(UTC)
    db.flush()

    response = WeeklyReviewStateResponse.model_validate(state)
    _store_idempotency(
        db,
        current_user=current_user,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=200,
        response=response,
    )
    db.commit()
    return response, False


def launch_weekly_review(
    db: Session,
    *,
    current_user: User,
    week_start: date,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[WeeklyReviewLaunchResponse, bool]:
    _validate_week_start(week_start)
    request_hash = _hash_request("weekly_review.launched", {"week_start": week_start.isoformat()})
    existing_key = _get_existing_idempotency(db, current_user=current_user, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_launch_idempotency(existing_key, request_hash), True

    state = get_or_create_weekly_review_state(db, current_user=current_user, week_start=week_start)
    if not state.ready:
        raise WeeklyReviewNotReadyError("Weekly review is not ready yet.")
    if state.launched:
        raise WeeklyReviewAlreadyLaunchedError("Weekly review has already been launched.")

    state.launched = True
    state.launched_at = datetime.now(UTC)
    state.analysis_status = "running"
    db.flush()

    response = WeeklyReviewLaunchResponse(
        id=state.id,
        week_start=state.week_start,
        launched=state.launched,
        launched_at=state.launched_at,
        analysis_status=state.analysis_status,
    )
    _store_idempotency(
        db,
        current_user=current_user,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=201,
        response=response,
    )
    db.commit()
    return response, False


def get_weekly_review_banner(db: Session, *, current_user: User) -> DashboardWeeklyReviewBanner | None:
    week_start = _current_week_start()
    state = _get_weekly_review_state(db, current_user=current_user, week_start=week_start)
    if state is None:
        return None

    return DashboardWeeklyReviewBanner(
        week_start=state.week_start,
        ready=state.ready,
        launched=state.launched,
        analysis_status=state.analysis_status,
        show_banner=state.ready and not state.launched,
    )


def _validate_week_start(week_start: date) -> None:
    if week_start.weekday() != 0:
        raise InvalidWeekStartError("week_start must be a Monday.")


def _current_week_start() -> date:
    today = datetime.now(UTC).astimezone(ZoneInfo(PARIS_TIMEZONE)).date()
    return today - timedelta(days=today.weekday())


def _get_weekly_review_state(
    db: Session,
    *,
    current_user: User,
    week_start: date,
) -> ImperiumWeeklyReviewState | None:
    return db.scalar(
        select(ImperiumWeeklyReviewState).where(
            ImperiumWeeklyReviewState.user_id == current_user.id,
            ImperiumWeeklyReviewState.week_start == week_start,
        )
    )


def _get_existing_idempotency(
    db: Session,
    *,
    current_user: User,
    idempotency_key: str,
) -> IdempotencyKey | None:
    return db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == current_user.id,
            IdempotencyKey.idempotency_key == idempotency_key,
        )
    )


def _handle_ready_idempotency(
    existing_key: IdempotencyKey,
    request_hash: str,
) -> WeeklyReviewStateResponse:
    if existing_key.request_hash != request_hash:
        raise IdempotencyConflictError("Idempotency key already used with different payload.")
    if existing_key.response_body is None:
        raise IdempotencyConflictError("Idempotency key is already processing.")
    return WeeklyReviewStateResponse.model_validate(existing_key.response_body)


def _handle_launch_idempotency(
    existing_key: IdempotencyKey,
    request_hash: str,
) -> WeeklyReviewLaunchResponse:
    if existing_key.request_hash != request_hash:
        raise IdempotencyConflictError("Idempotency key already used with different payload.")
    if existing_key.response_body is None:
        raise IdempotencyConflictError("Idempotency key is already processing.")
    return WeeklyReviewLaunchResponse.model_validate(existing_key.response_body)


def _store_idempotency(
    db: Session,
    *,
    current_user: User,
    idempotency_key: str,
    request_method: str,
    request_path: str,
    request_hash: str,
    response_status_code: int,
    response,
) -> None:
    db.add(
        IdempotencyKey(
            user_id=current_user.id,
            idempotency_key=idempotency_key,
            request_method=request_method,
            request_path=request_path,
            request_hash=request_hash,
            status=IdempotencyStatus.completed,
            response_status_code=response_status_code,
            response_body=response.model_dump(mode="json"),
        )
    )


def _hash_request(action: str, payload: dict) -> str:
    canonical = json.dumps(
        {"action": action, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
