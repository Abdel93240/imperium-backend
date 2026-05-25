import hashlib
import json
from datetime import date
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import IdempotencyStatus
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumPathCheckIn, ImperiumPathHabit
from app.schemas.path import (
    PathCheckInCreate,
    PathCheckInListResponse,
    PathCheckInRead,
    PathHabitCreate,
    PathHabitDetailResponse,
    PathHabitLifecycleResponse,
    PathHabitLifecycleSummary,
    PathHabitListResponse,
    PathHabitRead,
    PathTodayItemRead,
    PathTodayResponse,
    PathTodayStatus,
)

SAFE_EXPLANATION = "Path habits/check-ins for current user."
TODAY_SAFE_EXPLANATION = "Path today view for current user."
LIFECYCLE_SAFE_EXPLANATION = "Path habit lifecycle updated without deleting history."
HABIT_DETAIL_SAFE_EXPLANATION = "Path habit detail for current user."

ResponseT = TypeVar("ResponseT", bound=BaseModel)


class PathIdempotencyConflictError(ValueError):
    pass


class PathHabitNotFoundError(ValueError):
    pass


class PathHabitInactiveError(ValueError):
    pass


class PathCheckInConflictError(ValueError):
    pass


def create_path_habit(
    db: Session,
    *,
    current_user: User,
    payload: PathHabitCreate,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[PathHabitRead, bool]:
    request_hash = _hash_request("path.habit.created", payload.model_dump(mode="json"))
    existing_key = _get_existing_idempotency(db, current_user=current_user, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_existing_idempotency(existing_key, request_hash, PathHabitRead), True

    habit = ImperiumPathHabit(
        user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        domain=payload.domain,
        frequency=payload.frequency.value,
        is_active=True,
    )
    db.add(habit)
    db.flush()

    response = PathHabitRead.model_validate(habit)
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


def list_path_habits(
    db: Session,
    *,
    current_user: User,
    is_active: bool | None,
    domain: str | None,
    limit: int,
    offset: int,
) -> PathHabitListResponse:
    query = select(ImperiumPathHabit).where(ImperiumPathHabit.user_id == current_user.id)
    if is_active is not None:
        query = query.where(ImperiumPathHabit.is_active == is_active)
    if domain:
        query = query.where(ImperiumPathHabit.domain == domain)
    query = query.order_by(
        ImperiumPathHabit.is_active.desc(),
        ImperiumPathHabit.created_at.desc(),
        ImperiumPathHabit.id.asc(),
    ).limit(limit).offset(offset)
    items = [PathHabitRead.model_validate(habit) for habit in db.scalars(query)]
    return PathHabitListResponse(
        items=items,
        count=len(items),
        limit=limit,
        offset=offset,
        safe_explanation=SAFE_EXPLANATION,
    )


def get_path_habit_detail(
    db: Session,
    *,
    current_user: User,
    habit_id: UUID,
) -> PathHabitDetailResponse:
    habit = _get_user_habit(db, current_user=current_user, habit_id=habit_id)
    if habit is None:
        raise PathHabitNotFoundError("Path habit not found.")
    return PathHabitDetailResponse(
        habit=PathHabitRead.model_validate(habit),
        safe_explanation=HABIT_DETAIL_SAFE_EXPLANATION,
    )


def create_path_check_in(
    db: Session,
    *,
    current_user: User,
    habit_id: UUID,
    payload: PathCheckInCreate,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[PathCheckInRead, bool]:
    request_hash = _hash_request(
        "path.check_in.created",
        {"habit_id": str(habit_id), **payload.model_dump(mode="json")},
    )
    existing_key = _get_existing_idempotency(db, current_user=current_user, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_existing_idempotency(existing_key, request_hash, PathCheckInRead), True

    habit = _get_user_habit(db, current_user=current_user, habit_id=habit_id)
    if habit is None:
        raise PathHabitNotFoundError("Path habit not found.")
    if not habit.is_active:
        raise PathHabitInactiveError("Path habit is inactive.")

    existing_check_in = _get_existing_check_in(
        db,
        current_user=current_user,
        habit_id=habit_id,
        check_date=payload.check_date,
    )
    if existing_check_in is not None:
        raise PathCheckInConflictError("Path check-in already exists for this habit and date.")

    check_in = ImperiumPathCheckIn(
        user_id=current_user.id,
        habit_id=habit_id,
        check_date=payload.check_date,
        status=payload.status.value,
        reason=payload.reason,
        note=payload.note,
    )
    db.add(check_in)
    db.flush()

    response = PathCheckInRead.model_validate(check_in)
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


def list_path_check_ins(
    db: Session,
    *,
    current_user: User,
    habit_id: UUID | None,
    status: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> PathCheckInListResponse:
    query = select(ImperiumPathCheckIn).where(ImperiumPathCheckIn.user_id == current_user.id)
    if habit_id is not None:
        query = query.where(ImperiumPathCheckIn.habit_id == habit_id)
    if status is not None:
        query = query.where(ImperiumPathCheckIn.status == status)
    if date_from is not None:
        query = query.where(ImperiumPathCheckIn.check_date >= date_from)
    if date_to is not None:
        query = query.where(ImperiumPathCheckIn.check_date <= date_to)
    query = query.order_by(
        ImperiumPathCheckIn.check_date.desc(),
        ImperiumPathCheckIn.created_at.desc(),
        ImperiumPathCheckIn.id.asc(),
    ).limit(limit).offset(offset)
    items = [PathCheckInRead.model_validate(check_in) for check_in in db.scalars(query)]
    return PathCheckInListResponse(
        items=items,
        count=len(items),
        limit=limit,
        offset=offset,
        safe_explanation=SAFE_EXPLANATION,
    )


def get_path_today_view(
    db: Session,
    *,
    current_user: User,
    local_date: date,
    domain: str | None,
    frequency: str | None,
) -> PathTodayResponse:
    habit_query = select(ImperiumPathHabit).where(
        ImperiumPathHabit.user_id == current_user.id,
        ImperiumPathHabit.is_active.is_(True),
    )
    if domain is not None:
        habit_query = habit_query.where(ImperiumPathHabit.domain == domain)
    if frequency is not None:
        habit_query = habit_query.where(ImperiumPathHabit.frequency == frequency)
    habit_query = habit_query.order_by(
        ImperiumPathHabit.created_at.asc(),
        ImperiumPathHabit.id.asc(),
    )
    habits = list(db.scalars(habit_query))
    if not habits:
        return PathTodayResponse(
            date=local_date,
            items=[],
            count=0,
            safe_explanation=TODAY_SAFE_EXPLANATION,
        )

    habit_ids = [habit.id for habit in habits]
    check_in_query = select(ImperiumPathCheckIn).where(
        ImperiumPathCheckIn.user_id == current_user.id,
        ImperiumPathCheckIn.check_date == local_date,
        ImperiumPathCheckIn.habit_id.in_(habit_ids),
    )
    check_ins = list(db.scalars(check_in_query))
    check_in_by_habit_id = {check_in.habit_id: check_in for check_in in check_ins}

    items = []
    for habit in habits:
        check_in = check_in_by_habit_id.get(habit.id)
        if check_in is None:
            status = PathTodayStatus.pending
        elif check_in.status == PathTodayStatus.done.value:
            status = PathTodayStatus.done
        else:
            status = PathTodayStatus.missed
        items.append(
            PathTodayItemRead(
                habit=PathHabitRead.model_validate(habit),
                check_in=PathCheckInRead.model_validate(check_in) if check_in is not None else None,
                status=status,
            )
        )

    return PathTodayResponse(
        date=local_date,
        items=items,
        count=len(items),
        safe_explanation=TODAY_SAFE_EXPLANATION,
    )


def _get_user_habit(
    db: Session,
    *,
    current_user: User,
    habit_id: UUID,
) -> ImperiumPathHabit | None:
    return db.scalar(
        select(ImperiumPathHabit).where(
            ImperiumPathHabit.id == habit_id,
            ImperiumPathHabit.user_id == current_user.id,
        )
    )


def _get_existing_check_in(
    db: Session,
    *,
    current_user: User,
    habit_id: UUID,
    check_date: date,
) -> ImperiumPathCheckIn | None:
    return db.scalar(
        select(ImperiumPathCheckIn).where(
            ImperiumPathCheckIn.user_id == current_user.id,
            ImperiumPathCheckIn.habit_id == habit_id,
            ImperiumPathCheckIn.check_date == check_date,
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


def _handle_existing_idempotency(
    existing_key: IdempotencyKey,
    request_hash: str,
    response_model: type[ResponseT],
) -> ResponseT:
    if existing_key.request_hash != request_hash:
        raise PathIdempotencyConflictError("Idempotency key already used with different payload.")
    if existing_key.response_body is None:
        raise PathIdempotencyConflictError("Idempotency key is already processing.")
    return response_model(**existing_key.response_body)


def _store_idempotency(
    db: Session,
    *,
    current_user: User,
    idempotency_key: str,
    request_method: str,
    request_path: str,
    request_hash: str,
    response_status_code: int,
    response: BaseModel,
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


def archive_path_habit(
    db: Session,
    *,
    current_user: User,
    habit_id: UUID,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[PathHabitLifecycleResponse, bool]:
    return _transition_path_habit_lifecycle(
        db,
        current_user=current_user,
        habit_id=habit_id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_action="path.habit.archived",
        desired_is_active=False,
        status_if_changed="archived",
        status_if_unchanged="already_archived",
    )


def reactivate_path_habit(
    db: Session,
    *,
    current_user: User,
    habit_id: UUID,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[PathHabitLifecycleResponse, bool]:
    return _transition_path_habit_lifecycle(
        db,
        current_user=current_user,
        habit_id=habit_id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_action="path.habit.reactivated",
        desired_is_active=True,
        status_if_changed="reactivated",
        status_if_unchanged="already_active",
    )


def _transition_path_habit_lifecycle(
    db: Session,
    *,
    current_user: User,
    habit_id: UUID,
    idempotency_key: str,
    request_method: str,
    request_path: str,
    request_action: str,
    desired_is_active: bool,
    status_if_changed: str,
    status_if_unchanged: str,
) -> tuple[PathHabitLifecycleResponse, bool]:
    request_hash = _hash_request(request_action, {"habit_id": str(habit_id)})
    existing_key = _get_existing_idempotency(db, current_user=current_user, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_existing_idempotency(existing_key, request_hash, PathHabitLifecycleResponse), True

    habit = _get_user_habit(db, current_user=current_user, habit_id=habit_id)
    if habit is None:
        raise PathHabitNotFoundError("Path habit not found.")

    changed = habit.is_active != desired_is_active
    if changed:
        habit.is_active = desired_is_active

    db.flush()

    response = PathHabitLifecycleResponse(
        habit=PathHabitRead.model_validate(habit),
        lifecycle_summary=PathHabitLifecycleSummary(
            status=status_if_changed if changed else status_if_unchanged,
            guardrails_checked=["OWNERSHIP_CONFIRMED", "IDEMPOTENCY_KEY_ACCEPTED"],
            safe_explanation=LIFECYCLE_SAFE_EXPLANATION,
        ),
    )
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
