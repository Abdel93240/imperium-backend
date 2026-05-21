import hashlib
import json
from datetime import UTC, date, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import IdempotencyStatus, PrivacyLevel, SourceApp
from app.models.event import Event
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumPathItem
from app.schemas.imperium import CreatePathItemRequest, PathItemResponse, PathItemWriteResponse

PARIS_TIMEZONE = "Europe/Paris"


class IdempotencyConflictError(ValueError):
    pass


class PathItemNotFoundError(ValueError):
    pass


def get_path_items_for_day(db: Session, *, current_user: User, local_date: date) -> list[ImperiumPathItem]:
    return list(
        db.scalars(
            _ordered_path_items_query(current_user=current_user).where(
                ImperiumPathItem.local_date == local_date,
            )
        )
    )


def get_today_path_items(
    db: Session,
    *,
    current_user: User,
    timezone: str = PARIS_TIMEZONE,
) -> list[ImperiumPathItem]:
    today = datetime.now(UTC).astimezone(ZoneInfo(timezone)).date()
    return get_path_items_for_day(db, current_user=current_user, local_date=today)


def get_recent_path_items(db: Session, *, current_user: User, limit: int) -> list[ImperiumPathItem]:
    return list(
        db.scalars(
            select(ImperiumPathItem)
            .where(ImperiumPathItem.user_id == current_user.id)
            .order_by(ImperiumPathItem.created_at.desc())
            .limit(limit)
        )
    )


def create_path_item(
    db: Session,
    *,
    current_user: User,
    payload: CreatePathItemRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[PathItemWriteResponse, bool]:
    request_hash = _hash_request("path.item.created", payload.model_dump(mode="json"))
    existing_key = _get_existing_idempotency(db, current_user=current_user, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_existing_idempotency(existing_key, request_hash), True

    item = ImperiumPathItem(
        user_id=current_user.id,
        local_date=payload.local_date,
        timezone=payload.timezone,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        priority_key=payload.priority_key,
        planned_start=payload.planned_start,
        planned_end=payload.planned_end,
        status=payload.status.value,
        source=payload.source.value,
        sort_order=payload.sort_order,
        item_metadata=payload.metadata,
    )
    db.add(item)
    db.flush()

    event_id = f"evt_{uuid4().hex}"
    event = _build_event(
        current_user=current_user,
        event_id=event_id,
        event_type="path.item.created",
        idempotency_key=idempotency_key,
        payload={"item_id": str(item.id), **payload.model_dump(mode="json", exclude_none=True)},
    )
    db.add(event)
    db.flush()

    response = _write_response(
        item=item,
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


def start_path_item(
    db: Session,
    *,
    current_user: User,
    item_id: UUID,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[PathItemWriteResponse, bool]:
    return _transition_path_item(
        db,
        current_user=current_user,
        item_id=item_id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        event_type="path.item.started",
        status_value="in_progress",
        status_text="started",
    )


def complete_path_item(
    db: Session,
    *,
    current_user: User,
    item_id: UUID,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[PathItemWriteResponse, bool]:
    return _transition_path_item(
        db,
        current_user=current_user,
        item_id=item_id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        event_type="path.item.completed",
        status_value="completed",
        status_text="completed",
    )


def skip_path_item(
    db: Session,
    *,
    current_user: User,
    item_id: UUID,
    skip_reason: str,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[PathItemWriteResponse, bool]:
    return _transition_path_item(
        db,
        current_user=current_user,
        item_id=item_id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        event_type="path.item.skipped",
        status_value="skipped",
        status_text="skipped",
        payload_extra={"skip_reason": skip_reason},
        skip_reason=skip_reason,
    )


def cancel_path_item(
    db: Session,
    *,
    current_user: User,
    item_id: UUID,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[PathItemWriteResponse, bool]:
    return _transition_path_item(
        db,
        current_user=current_user,
        item_id=item_id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        event_type="path.item.cancelled",
        status_value="cancelled",
        status_text="cancelled",
    )


def _transition_path_item(
    db: Session,
    *,
    current_user: User,
    item_id: UUID,
    idempotency_key: str,
    request_method: str,
    request_path: str,
    event_type: str,
    status_value: str,
    status_text: str,
    payload_extra: dict | None = None,
    skip_reason: str | None = None,
) -> tuple[PathItemWriteResponse, bool]:
    payload = {"item_id": str(item_id), **(payload_extra or {})}
    request_hash = _hash_request(event_type, payload)
    existing_key = _get_existing_idempotency(db, current_user=current_user, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_existing_idempotency(existing_key, request_hash), True

    item = _get_user_path_item(db, current_user=current_user, item_id=item_id)
    if item is None:
        raise PathItemNotFoundError("Path item not found.")

    now = datetime.now(UTC)
    item.status = status_value
    if status_value == "completed":
        item.completed_at = now
    elif status_value == "skipped":
        item.skipped_at = now
        item.skip_reason = skip_reason
    elif status_value == "cancelled":
        item.cancelled_at = now
    db.flush()

    event_id = f"evt_{uuid4().hex}"
    event = _build_event(
        current_user=current_user,
        event_id=event_id,
        event_type=event_type,
        idempotency_key=idempotency_key,
        payload=payload,
    )
    db.add(event)
    db.flush()

    response = _write_response(
        item=item,
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


def _ordered_path_items_query(*, current_user: User):
    return (
        select(ImperiumPathItem)
        .where(ImperiumPathItem.user_id == current_user.id)
        .order_by(
            ImperiumPathItem.sort_order.asc(),
            ImperiumPathItem.planned_start.asc().nulls_last(),
            ImperiumPathItem.created_at.asc(),
        )
    )


def _get_user_path_item(
    db: Session,
    *,
    current_user: User,
    item_id: UUID,
) -> ImperiumPathItem | None:
    return db.scalar(
        select(ImperiumPathItem).where(
            ImperiumPathItem.id == item_id,
            ImperiumPathItem.user_id == current_user.id,
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
) -> PathItemWriteResponse:
    if existing_key.request_hash != request_hash:
        raise IdempotencyConflictError("Idempotency key already used with different payload.")
    if existing_key.response_body is None:
        raise IdempotencyConflictError("Idempotency key is already processing.")
    return PathItemWriteResponse(**existing_key.response_body)


def _build_event(
    *,
    current_user: User,
    event_id: str,
    event_type: str,
    idempotency_key: str,
    payload: dict,
) -> Event:
    now = datetime.now(UTC)
    return Event(
        event_id=event_id,
        event_type=event_type,
        schema_version="1.0",
        occurred_at=now,
        received_at=now,
        source_app=SourceApp.imperium,
        device_id=None,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        correlation_id=f"corr_{event_type.replace('.', '_')}_{uuid4().hex}",
        causation_id=None,
        privacy_level=PrivacyLevel.medium,
        payload=payload,
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
    response: PathItemWriteResponse,
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
    item: ImperiumPathItem,
    event_id: str,
    idempotency_key: str,
    status_text: str,
) -> PathItemWriteResponse:
    item_response = PathItemResponse.model_validate(item)
    item_response.idempotency_key = idempotency_key
    return PathItemWriteResponse(
        item=item_response,
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
