from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import text

from app.models.enums import PrivacyLevel, SourceApp
from app.models.event import Event
from app.schemas.events import EventEnvelope
from app.services.events.ingestion import _hash_envelope


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _event_kwargs(**overrides):
    event_id = f"event-{uuid4()}"
    values = {
        "event_id": event_id,
        "event_type": "test.depth.recorded",
        "schema_version": "1.0",
        "occurred_at": datetime.now(UTC),
        "received_at": datetime.now(UTC),
        "source_app": SourceApp.core,
        "device_id": None,
        "user_id": uuid4(),
        "idempotency_key": f"idem-{event_id}",
        "correlation_id": f"corr-{event_id}",
        "causation_id": None,
        "privacy_level": PrivacyLevel.low,
        "payload": {},
    }
    values.update(overrides)
    return values


def _envelope_kwargs(**overrides):
    values = _event_kwargs(**overrides)
    values["source_app"] = values["source_app"].value
    values["privacy_level"] = values["privacy_level"].value
    return values


def test_event_model_accepts_depth_and_null_depth() -> None:
    root_event = Event(**_event_kwargs(depth=1))
    legacy_event = Event(**_event_kwargs())

    assert root_event.depth == 1
    assert legacy_event.depth is None


def test_event_envelope_accepts_depth_and_preserves_legacy_null_depth_hash() -> None:
    envelope = EventEnvelope(**_envelope_kwargs(depth=1))
    legacy_envelope = EventEnvelope(**_envelope_kwargs())

    assert envelope.depth == 1
    assert legacy_envelope.depth is None

    legacy_payload = legacy_envelope.model_dump(mode="json")
    legacy_payload.pop("depth", None)
    expected_hash = hashlib.sha256(
        json.dumps(legacy_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert _hash_envelope(legacy_envelope) == expected_hash


def test_event_envelope_rejects_zero_depth() -> None:
    with pytest.raises(ValidationError):
        EventEnvelope(**_envelope_kwargs(depth=0))


def test_events_depth_migration_adds_nullable_depth_with_positive_check() -> None:
    migration_text = (
        BACKEND_ROOT / "alembic" / "versions" / "20260707_0036_events_depth.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "20260707_0036"' in migration_text
    assert 'down_revision: str | None = "20260707_0035"' in migration_text
    assert 'op.add_column("events", sa.Column("depth", sa.Integer(), nullable=True))' in migration_text
    assert "server_default" not in migration_text
    assert "ck_events_depth_positive_check" in migration_text
    assert "depth IS NULL OR depth >= 1" in migration_text
    assert 'op.drop_column("events", "depth")' in migration_text


def test_events_depth_postgres_accepts_positive_and_null_rejects_zero() -> None:
    pytest.importorskip("psycopg")
    from sqlalchemy import create_engine

    from _postgres import require_test_database_url

    engine = create_engine(require_test_database_url("events depth constraint tests"), future=True)
    try:
        with engine.begin() as conn:
            user_id = str(uuid4())
            conn.execute(
                text(
                    "INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"
                ),
                {"id": user_id, "email": f"events-depth-{user_id}@example.test"},
            )

            root_id = _insert_event_row(conn, user_id=user_id, depth=1)
            legacy_id = _insert_event_row(conn, user_id=user_id, depth=None)

            rows = conn.execute(
                text("SELECT id, depth FROM events WHERE id IN (:root_id, :legacy_id)"),
                {"root_id": root_id, "legacy_id": legacy_id},
            ).mappings()
            depths_by_id = {str(row["id"]): row["depth"] for row in rows}
            assert depths_by_id[root_id] == 1
            assert depths_by_id[legacy_id] is None

        with pytest.raises(Exception):
            with engine.begin() as conn:
                _insert_event_row(conn, user_id=user_id, depth=0)
    finally:
        engine.dispose()


def _insert_event_row(conn, *, user_id: str, depth: int | None) -> str:
    event_pk = str(uuid4())
    conn.execute(
        text(
            "INSERT INTO events (id, event_id, event_type, schema_version, occurred_at, "
            "received_at, source_app, user_id, idempotency_key, correlation_id, depth, "
            "privacy_level, payload, created_at) "
            "VALUES (:id, :event_id, 'test.depth.recorded', '1.0', :now, :now, 'core', "
            ":user_id, :idem, :corr, :depth, 'low', '{}'::jsonb, :now)"
        ),
        {
            "id": event_pk,
            "event_id": f"evt-{event_pk}",
            "now": datetime.now(UTC),
            "user_id": user_id,
            "idem": f"idem-{event_pk}",
            "corr": f"corr-{event_pk}",
            "depth": depth,
        },
    )
    return event_pk
