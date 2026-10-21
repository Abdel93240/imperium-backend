"""État de la Weekly Review d'une semaine (prête, lancée) et découpage des semaines.

La semaine du WR commence le jour `wr.week_start_weekday` (0 = lundi … ; mardi pour l'utilisateur, décision
2026-10-21 : la nuit de lundi à mardi est le creux de sa semaine) et dure 7 jours. La revue porte sur la
semaine qui vient de finir ; elle est proposée à partir de 1 h de Paris le jour où la suivante commence
(job `wr.week_ready`, semé désactivé).
"""

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
from app.services.params import get_parameter

PARIS_TIMEZONE = "Europe/Paris"
WEEKDAYS_EN = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
READY_LOCAL_HOUR = 1


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
    validate_week_start(db, week_start)
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
    validate_week_start(db, week_start)
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
    validate_week_start(db, week_start)
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


def week_weekday(db: Session) -> int:
    """Premier jour de la semaine du WR (0 = lundi)."""
    return int(get_parameter(db, "wr.week_start_weekday", default=0)) % 7


def validate_week_start(db: Session, week_start: date) -> None:
    weekday = week_weekday(db)
    if week_start.weekday() != weekday:
        raise InvalidWeekStartError(f"week_start must be a {WEEKDAYS_EN[weekday]}.")


def week_start_on(day: date, weekday: int) -> date:
    """Début de la semaine du WR qui contient `day`."""
    return day - timedelta(days=(day.weekday() - weekday) % 7)


def reviewable_weeks(db: Session, now: datetime | None = None) -> list[date]:
    """La semaine qui vient de finir (proposée dès 1 h de Paris), puis la précédente (revue en retard)."""
    local = (now or datetime.now(UTC)).astimezone(ZoneInfo(PARIS_TIMEZONE)) - timedelta(hours=READY_LOCAL_HOUR)
    current = week_start_on(local.date(), week_weekday(db))
    return [current - timedelta(days=7), current - timedelta(days=14)]


def week_ready_job(ctx, window) -> None:
    """Job `wr.week_ready` (horaire) : la semaine qui vient de finir devient prête, une fois."""
    from app.services.wr.metrics import _job_user

    user = _job_user(ctx.db)
    if user is None:
        ctx.items_in = ctx.items_out = 0
        ctx.detail = {"skipped": "no_user"}
        return
    week_start = reviewable_weeks(ctx.db, window.to_ts)[0]
    state = get_or_create_weekly_review_state(ctx.db, current_user=user, week_start=week_start)
    ctx.items_in, ctx.items_out = 1, int(not state.ready)
    if not state.ready:
        state.ready, state.ready_at = True, datetime.now(UTC)
    ctx.db.commit()
    ctx.detail = {"week_start": week_start.isoformat(), "marked_ready": bool(ctx.items_out)}


def get_weekly_review_banner(db: Session, *, current_user: User) -> DashboardWeeklyReviewBanner | None:
    week_start = reviewable_weeks(db)[0]
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
