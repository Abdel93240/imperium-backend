import hashlib
import json
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import IdempotencyStatus
from app.models.event import Event
from app.models.idempotency import IdempotencyKey
from app.schemas.events import EventEnvelope, EventIngestResponse

logger = logging.getLogger(__name__)


def ingest_event(
    db: Session,
    *,
    envelope: EventEnvelope,
    current_user: User,
    request_method: str,
    request_path: str,
) -> tuple[EventIngestResponse, bool]:
    request_hash = _hash_envelope(envelope)
    existing_key = db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == current_user.id,
            IdempotencyKey.idempotency_key == envelope.idempotency_key,
        )
    )

    if existing_key is not None:
        if existing_key.request_hash != request_hash:
            raise ValueError("Idempotency key already used with a different request payload.")
        if existing_key.response_body is None:
            raise ValueError("Idempotency key is already processing.")

        logger.info(
            "Duplicate event ingestion retry ignored safely.",
            extra={
                "user_id": str(current_user.id),
                "idempotency_key": envelope.idempotency_key,
                "event_id": envelope.event_id,
            },
        )
        return EventIngestResponse(**existing_key.response_body), True

    response = EventIngestResponse(event_id=envelope.event_id, status="stored", duplicate=False)
    idempotency_key = IdempotencyKey(
        user_id=current_user.id,
        idempotency_key=envelope.idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        status=IdempotencyStatus.completed,
        response_status_code=201,
        response_body=response.model_dump(mode="json"),
    )
    event = Event(
        event_id=envelope.event_id,
        event_type=envelope.event_type,
        schema_version=envelope.schema_version,
        occurred_at=envelope.occurred_at,
        received_at=envelope.received_at or datetime.now(UTC),
        source_app=envelope.source_app,
        device_id=envelope.device_id,
        user_id=current_user.id,
        idempotency_key=envelope.idempotency_key,
        correlation_id=envelope.correlation_id,
        causation_id=envelope.causation_id,
        depth=envelope.depth,
        privacy_level=envelope.privacy_level,
        payload=envelope.payload,
    )

    db.add(idempotency_key)
    db.add(event)
    db.commit()
    return response, False


def _hash_envelope(envelope: EventEnvelope) -> str:
    payload = envelope.model_dump(mode="json")
    if payload.get("depth") is None:
        payload.pop("depth", None)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
