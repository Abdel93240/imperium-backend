"""PostgreSQL checks for Patch 7H calendar event constraints.

These tests require a migrated PostgreSQL database and skip automatically when
IMPERIUM_TEST_DATABASE_URL is not set.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

_TEST_DB_URL = os.environ.get("IMPERIUM_TEST_DATABASE_URL")
if not _TEST_DB_URL:
    pytest.skip(
        "IMPERIUM_TEST_DATABASE_URL not set; skipping calendar event DB tests.",
        allow_module_level=True,
    )

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
        {"id": user_id, "email": f"calendar-{user_id}@example.test"},
    )
    return user_id


def _insert_calendar_event(
    conn,
    *,
    user_id: str,
    event_type: str = "event",
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
) -> str:
    event_id = str(uuid4())
    start_value = starts_at or datetime(2026, 6, 1, 9, 0, tzinfo=UTC)
    conn.execute(
        text(
            "INSERT INTO imperium_calendar_events "
            "(id, user_id, event_type, title, starts_at, ends_at, blocks_time, created_at, updated_at) "
            "VALUES (:id, :user_id, :event_type, :title, :starts_at, :ends_at, TRUE, now(), now())"
        ),
        {
            "id": event_id,
            "user_id": user_id,
            "event_type": event_type,
            "title": f"Calendar event {event_id}",
            "starts_at": start_value,
            "ends_at": ends_at,
        },
    )
    return event_id


def _expect_check_failure(exc: Exception) -> None:
    msg = str(exc).lower()
    assert "check" in msg or "violates" in msg or "constraint" in msg, f"Expected check constraint error, got: {exc!r}"


def test_calendar_event_event_type_check_constraint(engine) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            user_id = _make_user(conn)
            _insert_calendar_event(conn, user_id=user_id, event_type="recurring")
    _expect_check_failure(excinfo.value)


def test_calendar_event_ends_at_after_starts_at_constraint(engine) -> None:
    starts_at = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            user_id = _make_user(conn)
            _insert_calendar_event(
                conn,
                user_id=user_id,
                starts_at=starts_at,
                ends_at=starts_at - timedelta(minutes=1),
            )
    _expect_check_failure(excinfo.value)
