import hashlib
import json
from datetime import UTC, date, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import IdempotencyStatus
from app.models.event import Event
from app.models.idempotency import IdempotencyKey
from app.models.imperium import (
    ImperiumDailyPlan,
    ImperiumDayReview,
    ImperiumMission,
)
from app.schemas.imperium import CreateDailyPlanRequest, DailyPlanResponse, DailyPlanWriteResponse
from app.services.events.emitter import build_event
from app.services.path.canonical import path_today_view
from app.services.imperium.decision_framework import get_canonical_priority_order

PARIS_TIMEZONE = "Europe/Paris"
CANONICAL_PRIORITY_LABELS = {
    "religious": "Religious",
    "business": "Business",
    "finance": "Finance",
    "health": "Health",
}


class IdempotencyConflictError(ValueError):
    pass


class DailyPlanAlreadyExistsError(ValueError):
    pass


class DailyPlanNotFoundError(ValueError):
    pass


class DailyPlanStateConflictError(ValueError):
    pass


def create_daily_plan(
    db: Session,
    *,
    current_user: User,
    payload: CreateDailyPlanRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[DailyPlanWriteResponse, bool]:
    request_hash = _hash_request("day.plan.created", payload.model_dump(mode="json"))
    existing_key = _get_existing_idempotency(db, current_user=current_user, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_existing_idempotency(existing_key, request_hash), True

    existing_plan = get_daily_plan_for_date(db, current_user=current_user, local_date=payload.local_date)
    if existing_plan is not None:
        raise DailyPlanAlreadyExistsError("Daily plan already exists for this local_date.")

    sources = _collect_plan_sources(db, current_user=current_user, local_date=payload.local_date)
    plan = ImperiumDailyPlan(
        user_id=current_user.id,
        local_date=payload.local_date,
        timezone=payload.timezone,
        plan_status="draft",
        title=payload.title,
        summary=payload.summary,
        focus_priority_key=payload.focus_priority_key,
        current_mission_id=sources["current_mission_id"],
        generated_from=sources["generated_from"],
        plan_blocks=sources["plan_blocks"],
        notes=payload.notes,
    )
    db.add(plan)
    db.flush()

    event_id = f"evt_{uuid4().hex}"
    event = _build_event(
        db,
        current_user=current_user,
        event_id=event_id,
        event_type="day.plan.created",
        idempotency_key=idempotency_key,
        payload={
            "plan_id": str(plan.id),
            **payload.model_dump(mode="json", exclude_none=True),
            "generated_from": plan.generated_from,
        },
    )
    db.add(event)
    db.flush()

    response = _write_response(
        plan=plan,
        event_id=event_id,
        idempotency_key=idempotency_key,
        status_text="created",
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


def get_daily_plan_for_date(
    db: Session,
    *,
    current_user: User,
    local_date: date,
) -> ImperiumDailyPlan | None:
    return db.scalar(
        select(ImperiumDailyPlan).where(
            ImperiumDailyPlan.user_id == current_user.id,
            ImperiumDailyPlan.local_date == local_date,
        )
    )


def get_today_daily_plan(
    db: Session,
    *,
    current_user: User,
    timezone: str = PARIS_TIMEZONE,
) -> ImperiumDailyPlan | None:
    today = datetime.now(UTC).astimezone(ZoneInfo(timezone)).date()
    return get_daily_plan_for_date(db, current_user=current_user, local_date=today)


def activate_daily_plan(
    db: Session,
    *,
    current_user: User,
    plan_id: UUID,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[DailyPlanWriteResponse, bool]:
    return _transition_daily_plan(
        db,
        current_user=current_user,
        plan_id=plan_id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        event_type="day.plan.activated",
        allowed_statuses={"draft"},
        new_status="active",
        status_text="activated",
    )


def complete_daily_plan(
    db: Session,
    *,
    current_user: User,
    plan_id: UUID,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[DailyPlanWriteResponse, bool]:
    return _transition_daily_plan(
        db,
        current_user=current_user,
        plan_id=plan_id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        event_type="day.plan.completed",
        allowed_statuses={"draft", "active"},
        new_status="completed",
        status_text="completed",
    )


def cancel_daily_plan(
    db: Session,
    *,
    current_user: User,
    plan_id: UUID,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[DailyPlanWriteResponse, bool]:
    return _transition_daily_plan(
        db,
        current_user=current_user,
        plan_id=plan_id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        event_type="day.plan.cancelled",
        allowed_statuses={"draft", "active"},
        new_status="cancelled",
        status_text="cancelled",
    )


def _find_plan_creation_event(
    db: Session,
    *,
    current_user: User,
    plan_id: UUID,
) -> Event | None:
    return db.scalar(
        select(Event)
        .where(
            Event.user_id == current_user.id,
            Event.event_type.in_(["planning.daily_plan.generated", "day.plan.created"]),
            Event.payload["plan_id"].astext == str(plan_id),
        )
        .order_by(Event.occurred_at.desc())
        .limit(1)
    )


def _transition_daily_plan(
    db: Session,
    *,
    current_user: User,
    plan_id: UUID,
    idempotency_key: str,
    request_method: str,
    request_path: str,
    event_type: str,
    allowed_statuses: set[str],
    new_status: str,
    status_text: str,
) -> tuple[DailyPlanWriteResponse, bool]:
    payload = {"plan_id": str(plan_id), "new_status": new_status}
    request_hash = _hash_request(event_type, payload)
    existing_key = _get_existing_idempotency(db, current_user=current_user, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_existing_idempotency(existing_key, request_hash), True

    plan = _get_user_daily_plan(db, current_user=current_user, plan_id=plan_id)
    if plan is None:
        raise DailyPlanNotFoundError("Daily plan not found.")
    if plan.plan_status not in allowed_statuses:
        raise DailyPlanStateConflictError(f"Daily plan cannot move from {plan.plan_status} to {new_status}.")

    plan.plan_status = new_status
    db.flush()

    creation_event = _find_plan_creation_event(db, current_user=current_user, plan_id=plan_id)
    event_id = f"evt_{uuid4().hex}"
    event = _build_event(
        db,
        current_user=current_user,
        event_id=event_id,
        event_type=event_type,
        idempotency_key=idempotency_key,
        payload={**payload, "trigger": status_text},
        causation_event=creation_event,
    )
    db.add(event)
    db.flush()

    response = _write_response(
        plan=plan,
        event_id=event_id,
        idempotency_key=idempotency_key,
        status_text=status_text,
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


def _collect_plan_sources(db: Session, *, current_user: User, local_date: date) -> dict:
    current_mission = db.scalar(
        select(ImperiumMission).where(
            ImperiumMission.user_id == current_user.id,
            ImperiumMission.status == "active",
        )
    )
    # C-1 / AD-2 (passe 0): canonical Path source = habits/check-ins.
    path_items = path_today_view(db, current_user=current_user, local_date=local_date)
    priorities = get_canonical_priority_order(db, current_user=current_user)
    latest_day_review = db.scalar(
        select(ImperiumDayReview)
        .where(ImperiumDayReview.user_id == current_user.id)
        .order_by(ImperiumDayReview.local_date.desc(), ImperiumDayReview.created_at.desc())
        .limit(1)
    )

    plan_blocks = []
    if current_mission is not None:
        plan_blocks.append(
            {
                "block_type": "current_mission",
                "source_id": str(current_mission.id),
                "title": current_mission.title,
                "category": current_mission.category,
                "status": current_mission.status,
                "planned_start": _json_dt(current_mission.planned_start_at),
                "planned_end": _json_dt(current_mission.planned_end_at),
            }
        )

    for item in path_items:
        plan_blocks.append(
            {
                "block_type": "path_item",
                "source": "canonical_habit",
                "source_id": str(item.id),
                "title": item.title,
                "category": item.category,
                "priority_key": item.priority_key,
                "status": item.status,
                "sort_order": item.sort_order,
                "planned_start": _json_dt(item.planned_start),
                "planned_end": _json_dt(item.planned_end),
            }
        )

    if priorities:
        plan_blocks.append(
            {
                "block_type": "priority_context",
                "source": "decision_framework",
                "priorities": [
                    {
                        "source_id": str(priority.id) if priority.id else None,
                        "priority_key": priority.domain,
                        "label": CANONICAL_PRIORITY_LABELS.get(
                            priority.domain,
                            priority.domain.replace("_", " ").title(),
                        ),
                        "rank_order": priority.position,
                        "importance_score": None,
                    }
                    for priority in priorities
                ],
            }
        )

    return {
        "current_mission_id": current_mission.id if current_mission else None,
        "generated_from": {
            "current_mission_id": str(current_mission.id) if current_mission else None,
            "path_item_ids": [str(item.id) for item in path_items],
            "priority_source": "decision_framework",
            "decision_framework_priority_ids": [str(priority.id) for priority in priorities if priority.id],
            "latest_day_review_id": str(latest_day_review.id) if latest_day_review else None,
        },
        "plan_blocks": plan_blocks,
    }


def _get_user_daily_plan(
    db: Session,
    *,
    current_user: User,
    plan_id: UUID,
) -> ImperiumDailyPlan | None:
    return db.scalar(
        select(ImperiumDailyPlan).where(
            ImperiumDailyPlan.id == plan_id,
            ImperiumDailyPlan.user_id == current_user.id,
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
) -> DailyPlanWriteResponse:
    if existing_key.request_hash != request_hash:
        raise IdempotencyConflictError("Idempotency key already used with different payload.")
    if existing_key.response_body is None:
        raise IdempotencyConflictError("Idempotency key is already processing.")
    return DailyPlanWriteResponse(**existing_key.response_body)


def _build_event(
    db: Session,
    *,
    current_user: User,
    event_id: str,
    event_type: str,
    idempotency_key: str,
    payload: dict,
    causation_event: Event | None = None,
    correlation_id: str | None = None,
) -> Event:
    # E2 (passe 0): shared emitter — canonical type, real depth, plan dossier.
    return build_event(
        db,
        user_id=current_user.id,
        event_type=event_type,
        payload=payload,
        idempotency_key=idempotency_key,
        event_id=event_id,
        causation_id=causation_event.event_id if causation_event is not None else None,
        correlation_id=correlation_id,
    )


def _store_idempotency(
    db: Session,
    *,
    current_user: User,
    idempotency_key: str,
    request_method: str,
    request_path: str,
    request_hash: str,
    response_status_code: int,
    response: DailyPlanWriteResponse,
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


def _write_response(
    *,
    plan: ImperiumDailyPlan,
    event_id: str,
    idempotency_key: str,
    status_text: str,
) -> DailyPlanWriteResponse:
    plan_response = DailyPlanResponse.model_validate(plan)
    plan_response.idempotency_key = idempotency_key
    return DailyPlanWriteResponse(
        plan=plan_response,
        event_id=event_id,
        idempotency_key=idempotency_key,
        status=status_text,
    )


def _hash_request(action: str, payload: dict) -> str:
    canonical = json.dumps(
        {"action": action, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _json_dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
