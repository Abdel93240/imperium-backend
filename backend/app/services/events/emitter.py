"""Shared event emitter — the E2 envelope is filled AT EMISSION (passe 0, §6).

Every backend service emits through build_event() so the chain fields are real:
- explicit causation_id → depth = parent.depth + 1, correlation inherited from
  the parent (the "dossier" stays one readable story);
- no natural parent → root: depth = 1, fresh correlation_id.

The deterministic pass covers the DECLARED links only (same action, same
direct consequence). Deep chaining stays the WR Phase 3 job (doc 77).
"""

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import PrivacyLevel, SourceApp
from app.models.event import Event
from app.services.events.nomenclature import canonical_event_type

logger = logging.getLogger(__name__)


def build_event(
    db: Session | None,
    *,
    user_id: UUID,
    event_type: str,
    payload: dict,
    idempotency_key: str,
    event_id: str | None = None,
    source_app: SourceApp = SourceApp.imperium,
    privacy_level: PrivacyLevel = PrivacyLevel.medium,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    device_id: UUID | None = None,
    occurred_at: datetime | None = None,
) -> Event:
    event_type = canonical_event_type(event_type)
    now = datetime.now(UTC)
    occurred_at = occurred_at or now

    depth = 1
    if causation_id is not None:
        if db is None:
            raise ValueError("build_event needs a session to resolve a causation parent.")
        parent = db.scalar(
            select(Event).where(Event.user_id == user_id, Event.event_id == causation_id)
        )
        if parent is not None:
            depth = (parent.depth or 1) + 1
            if correlation_id is None:
                correlation_id = parent.correlation_id
        else:
            # Declared cause not found: keep the declaration, stay a root.
            logger.warning(
                "causation_id declared but parent event not found; emitting as root.",
                extra={"event_type": event_type, "causation_id": causation_id},
            )
            causation_id = None

    if correlation_id is None:
        correlation_id = f"corr_{event_type.replace('.', '_')}_{uuid4().hex}"

    return Event(
        event_id=event_id or f"evt_{uuid4().hex}",
        event_type=event_type,
        schema_version="1.0",
        occurred_at=occurred_at,
        received_at=now,
        source_app=source_app,
        device_id=device_id,
        user_id=user_id,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
        causation_id=causation_id,
        depth=depth,
        privacy_level=privacy_level,
        payload=payload,
    )
