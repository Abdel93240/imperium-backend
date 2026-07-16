import hashlib
import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import IdempotencyStatus
from app.models.event import Event
from app.services.events.emitter import build_event
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumPriorityRule
from app.schemas.imperium import (
    PriorityRulesResponse,
    ReplacePriorityRulesRequest,
)


class IdempotencyConflictError(ValueError):
    pass


def replace_priority_rules(
    db: Session,
    *,
    current_user: User,
    payload: ReplacePriorityRulesRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[PriorityRulesResponse, bool]:
    request_hash = _hash_payload(payload)
    existing_key = _get_existing_idempotency(db, current_user=current_user, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_existing_idempotency(existing_key, request_hash), True

    event_id = f"evt_{uuid4().hex}"
    event_payload = payload.model_dump(mode="json")
    event = _build_event(
        current_user=current_user,
        event_id=event_id,
        idempotency_key=idempotency_key,
        payload=event_payload,
    )
    db.add(event)
    db.flush()

    active_rules = get_active_priority_rules(db, current_user=current_user)
    for rule in active_rules:
        rule.is_active = False
        rule.updated_by_event_id = event.id

    new_rules = [
        ImperiumPriorityRule(
            user_id=current_user.id,
            priority_key=item.priority_key,
            label=item.label,
            rank_order=item.rank_order,
            importance_score=item.importance_score,
            is_active=True,
            updated_by_event_id=event.id,
        )
        for item in sorted(payload.priorities, key=lambda priority: priority.rank_order)
    ]
    db.add_all(new_rules)
    db.flush()

    response = PriorityRulesResponse(
        priorities=new_rules,
        event_id=event_id,
        idempotency_key=idempotency_key,
        status="updated",
    )
    db.add(
        IdempotencyKey(
            user_id=current_user.id,
            idempotency_key=idempotency_key,
            request_method=request_method,
            request_path=request_path,
            request_hash=request_hash,
            status=IdempotencyStatus.completed,
            response_status_code=200,
            response_body=response.model_dump(mode="json"),
        )
    )
    db.commit()
    return response, False


def get_active_priority_rules(db: Session, *, current_user: User) -> list[ImperiumPriorityRule]:
    return list(
        db.scalars(
            select(ImperiumPriorityRule)
            .where(
                ImperiumPriorityRule.user_id == current_user.id,
                ImperiumPriorityRule.is_active.is_(True),
            )
            .order_by(ImperiumPriorityRule.rank_order.asc(), ImperiumPriorityRule.created_at.asc())
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
) -> PriorityRulesResponse:
    if existing_key.request_hash != request_hash:
        raise IdempotencyConflictError("Idempotency key already used with different payload.")
    if existing_key.response_body is None:
        raise IdempotencyConflictError("Idempotency key is already processing.")
    return PriorityRulesResponse(**existing_key.response_body)


def _build_event(
    *,
    current_user: User,
    event_id: str,
    idempotency_key: str,
    payload: dict,
) -> Event:
    # E2 (passe 0): shared emitter (canonical: decision.priorities.updated, root).
    return build_event(
        None,
        user_id=current_user.id,
        event_type="priority.rules.updated",
        payload=payload,
        idempotency_key=idempotency_key,
        event_id=event_id,
    )


def _hash_payload(payload: ReplacePriorityRulesRequest) -> str:
    canonical = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
