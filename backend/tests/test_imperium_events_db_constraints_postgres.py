"""PostgreSQL checks for Patch 23A Imperium event invariants.

These tests require a migrated PostgreSQL database. They skip locally when
IMPERIUM_TEST_DATABASE_URL is not set and fail in CI if the variable is missing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("Imperium events DB constraint tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, text  # noqa: E402


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


def _make_user(conn) -> str:
    user_id = str(uuid4())
    conn.execute(
        text(
            "INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
            "VALUES (:id, :email, FALSE, now(), now())"
        ),
        {"id": user_id, "email": f"imperium-events-{user_id}@example.test"},
    )
    return user_id


def _insert_imperium_event(
    conn,
    *,
    user_id: str,
    event_type: str = "mission_started",
    source_module: str = "mission",
    schema_version: str = "v1",
    idempotency_key: str | None = "event-idem-1",
) -> str:
    event_id = str(uuid4())
    occurred_at = datetime(2026, 5, 26, 8, 45, tzinfo=UTC)
    conn.execute(
        text(
            "INSERT INTO imperium_events "
            "(id, user_id, event_type, source_module, occurred_at, payload_json, "
            "schema_version, idempotency_key, created_at, updated_at) "
            "VALUES (:id, :user_id, :event_type, :source_module, :occurred_at, '{}'::jsonb, "
            ":schema_version, :idempotency_key, now(), now())"
        ),
        {
            "id": event_id,
            "user_id": user_id,
            "event_type": event_type,
            "source_module": source_module,
            "occurred_at": occurred_at,
            "schema_version": schema_version,
            "idempotency_key": idempotency_key,
        },
    )
    return event_id


def _expect_constraint_failure(exc: Exception) -> None:
    msg = str(exc).lower()
    assert "check" in msg or "unique" in msg or "violates" in msg or "constraint" in msg, (
        f"Expected database constraint error, got: {exc!r}"
    )


def test_imperium_events_reject_blank_event_type(engine) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            user_id = _make_user(conn)
            _insert_imperium_event(conn, user_id=user_id, event_type="   ")

    _expect_constraint_failure(excinfo.value)


def test_imperium_events_reject_blank_source_module(engine) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            user_id = _make_user(conn)
            _insert_imperium_event(conn, user_id=user_id, source_module="   ")

    _expect_constraint_failure(excinfo.value)


def test_imperium_events_reject_invalid_source_module(engine) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            user_id = _make_user(conn)
            _insert_imperium_event(conn, user_id=user_id, source_module="ocr")

    _expect_constraint_failure(excinfo.value)


def test_imperium_events_reject_blank_schema_version(engine) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            user_id = _make_user(conn)
            _insert_imperium_event(conn, user_id=user_id, schema_version="   ")

    _expect_constraint_failure(excinfo.value)


def test_imperium_events_reject_duplicate_idempotency_key_for_same_user(engine) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            user_id = _make_user(conn)
            _insert_imperium_event(conn, user_id=user_id, idempotency_key="event-idem-duplicate")
            _insert_imperium_event(conn, user_id=user_id, idempotency_key="event-idem-duplicate")

    _expect_constraint_failure(excinfo.value)


def test_imperium_events_have_expected_indexes(engine) -> None:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT indexname, indexdef "
                "FROM pg_indexes "
                "WHERE tablename = 'imperium_events' "
                "ORDER BY indexname"
            )
        ).all()

    index_map = {row.indexname: row.indexdef for row in rows}
    assert "imperium_events_user_occurred_at_desc_idx" in index_map
    assert "imperium_events_user_source_module_occurred_at_desc_idx" in index_map
    assert "imperium_events_user_event_type_occurred_at_desc_idx" in index_map
    assert "imperium_events_user_idempotency_key_unique_idx" in index_map
    assert "where (idempotency_key is not null)" in index_map["imperium_events_user_idempotency_key_unique_idx"].lower()
