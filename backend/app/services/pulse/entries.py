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
from app.models.imperium import ImperiumPulseEntry
from app.schemas.pulse import PulseEntryCreate, PulseEntryListResponse, PulseEntryRead

SAFE_EXPLANATION = "Pulse entries for current user."

ResponseT = TypeVar("ResponseT", bound=BaseModel)


class PulseIdempotencyConflictError(ValueError):
    pass


class PulseEntryConflictError(ValueError):
    pass


class PulseEntryNotFoundError(ValueError):
    pass


def create_pulse_entry(
    db: Session,
    *,
    current_user: User,
    payload: PulseEntryCreate,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[PulseEntryRead, bool]:
    request_hash = _hash_request("pulse.entry.created", payload.model_dump(mode="json"))
    existing_key = _get_existing_idempotency(db, current_user=current_user, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_existing_idempotency(existing_key, request_hash, PulseEntryRead), True

    existing_entry = _get_existing_entry_for_date(db, current_user=current_user, entry_date=payload.entry_date)
    if existing_entry is not None:
        raise PulseEntryConflictError("Pulse entry already exists for this date.")

    entry = ImperiumPulseEntry(
        user_id=current_user.id,
        entry_date=payload.entry_date,
        sleep_hours=payload.sleep_hours,
        energy_level=payload.energy_level,
        fatigue_level=payload.fatigue_level,
        weight_kg=payload.weight_kg,
        workout_done=payload.workout_done,
        workout_type=payload.workout_type,
        notes=payload.notes,
    )
    db.add(entry)
    db.flush()

    response = PulseEntryRead.model_validate(entry)
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


def list_pulse_entries(
    db: Session,
    *,
    current_user: User,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> PulseEntryListResponse:
    query = select(ImperiumPulseEntry).where(ImperiumPulseEntry.user_id == current_user.id)
    if date_from is not None:
        query = query.where(ImperiumPulseEntry.entry_date >= date_from)
    if date_to is not None:
        query = query.where(ImperiumPulseEntry.entry_date <= date_to)
    query = query.order_by(
        ImperiumPulseEntry.entry_date.desc(),
        ImperiumPulseEntry.created_at.desc(),
        ImperiumPulseEntry.id.asc(),
    ).limit(limit).offset(offset)
    items = [PulseEntryRead.model_validate(entry) for entry in db.scalars(query)]
    return PulseEntryListResponse(
        items=items,
        count=len(items),
        limit=limit,
        offset=offset,
        safe_explanation=SAFE_EXPLANATION,
    )


def get_pulse_entry(
    db: Session,
    *,
    current_user: User,
    entry_id: UUID,
) -> PulseEntryRead:
    entry = db.scalar(
        select(ImperiumPulseEntry).where(
            ImperiumPulseEntry.id == entry_id,
            ImperiumPulseEntry.user_id == current_user.id,
        )
    )
    if entry is None:
        raise PulseEntryNotFoundError("Pulse entry not found.")
    return PulseEntryRead.model_validate(entry)


def _get_existing_entry_for_date(
    db: Session,
    *,
    current_user: User,
    entry_date: date,
) -> ImperiumPulseEntry | None:
    return db.scalar(
        select(ImperiumPulseEntry).where(
            ImperiumPulseEntry.user_id == current_user.id,
            ImperiumPulseEntry.entry_date == entry_date,
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
        raise PulseIdempotencyConflictError("Idempotency key already used with different payload.")
    if existing_key.response_body is None:
        raise PulseIdempotencyConflictError("Idempotency key is already processing.")
    return response_model.model_validate(existing_key.response_body)


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
