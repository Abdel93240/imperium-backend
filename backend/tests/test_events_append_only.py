"""Append-only trigger verification tests for events and auth_events.

These tests require a real PostgreSQL database with the migrations applied
(append-only triggers are installed by migrations 0002 and 0003). They are
skipped automatically when IMPERIUM_TEST_DATABASE_URL is not set, so the
default fast unit-test suite continues to pass on machines without Postgres.

Run locally:

    export IMPERIUM_TEST_DATABASE_URL=postgresql+psycopg://imperium_user:...@localhost:5432/imperium_core_test
    python -m pytest tests/test_events_append_only.py
"""
from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

_TEST_DB_URL = os.environ.get("IMPERIUM_TEST_DATABASE_URL")
if not _TEST_DB_URL:
    pytest.skip(
        "IMPERIUM_TEST_DATABASE_URL not set; skipping append-only trigger tests.",
        allow_module_level=True,
    )

pytestmark = pytest.mark.postgres


from sqlalchemy import create_engine, text  # noqa: E402

from app.models.auth import AuthEvent, User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.enums import PrivacyLevel, SourceApp  # noqa: E402


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
        {"id": user_id, "email": f"trigger-test-{user_id}@example.test"},
    )
    return user_id


def _insert_event(conn, *, user_id: str) -> str:
    event_pk = str(uuid4())
    conn.execute(
        text(
            "INSERT INTO events (id, event_id, event_type, schema_version, occurred_at, "
            "received_at, source_app, user_id, idempotency_key, correlation_id, "
            "privacy_level, payload, created_at) "
            "VALUES (:id, :event_id, :event_type, '1.0', :now, :now, 'imperium', "
            ":user_id, :idem, :corr, 'low', '{}'::jsonb, :now)"
        ),
        {
            "id": event_pk,
            "event_id": f"evt-{event_pk}",
            "event_type": "test.append_only",
            "now": datetime.now(UTC),
            "user_id": user_id,
            "idem": f"idem-{event_pk}",
            "corr": f"corr-{event_pk}",
        },
    )
    return event_pk


def _insert_auth_event(conn, *, user_id: str) -> str:
    auth_event_pk = str(uuid4())
    conn.execute(
        text(
            "INSERT INTO auth_events (id, user_id, event_type, success, "
            "ip_address, user_agent, reason, created_at) "
            "VALUES (:id, :user_id, 'login', TRUE, '127.0.0.1', 'pytest', NULL, :now)"
        ),
        {"id": auth_event_pk, "user_id": user_id, "now": datetime.now(UTC)},
    )
    return auth_event_pk


def _expect_append_only_failure(exc: Exception) -> None:
    msg = str(exc).lower()
    assert (
        "append-only" in msg
        or "permission denied" in msg
        or "trigger" in msg
        or "not allowed" in msg
    ), f"Expected append-only / trigger error, got: {exc!r}"


# ---- events ----------------------------------------------------------------


def test_event_update_is_rejected_by_trigger(engine) -> None:
    with engine.begin() as conn:
        user_id = _make_user(conn)
        event_pk = _insert_event(conn, user_id=user_id)

    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE events SET event_type = 'mutated' WHERE id = :id"),
                {"id": event_pk},
            )
    _expect_append_only_failure(excinfo.value)


def test_event_delete_is_rejected_by_trigger(engine) -> None:
    with engine.begin() as conn:
        user_id = _make_user(conn)
        event_pk = _insert_event(conn, user_id=user_id)

    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM events WHERE id = :id"), {"id": event_pk})
    _expect_append_only_failure(excinfo.value)


def test_event_truncate_is_rejected_by_trigger(engine) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE events"))
    _expect_append_only_failure(excinfo.value)


# ---- auth_events ----------------------------------------------------------


def test_auth_event_update_is_rejected_by_trigger(engine) -> None:
    with engine.begin() as conn:
        user_id = _make_user(conn)
        auth_event_pk = _insert_auth_event(conn, user_id=user_id)

    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE auth_events SET event_type = 'mutated' WHERE id = :id"),
                {"id": auth_event_pk},
            )
    _expect_append_only_failure(excinfo.value)


def test_auth_event_delete_is_rejected_by_trigger(engine) -> None:
    with engine.begin() as conn:
        user_id = _make_user(conn)
        auth_event_pk = _insert_auth_event(conn, user_id=user_id)

    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM auth_events WHERE id = :id"), {"id": auth_event_pk})
    _expect_append_only_failure(excinfo.value)


def test_auth_event_truncate_is_rejected_by_trigger(engine) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE auth_events"))
    _expect_append_only_failure(excinfo.value)


# Reference imports used to keep models in this module's coverage even when
# the test suite is skipped — also surfaces import errors at collection time.
_ = (Event, AuthEvent, User, PrivacyLevel, SourceApp)
