"""PostgreSQL checks for Patch 10I Path invariants.

These tests require a migrated PostgreSQL database. They skip locally when
IMPERIUM_TEST_DATABASE_URL is not set and fail in CI if the variable is missing.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("Path DB constraint tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.services.path.habits import (  # noqa: E402
    PathHabitNotFoundError,
    get_path_habit_detail,
    get_path_today_view,
    list_path_check_ins,
    list_path_habits,
)


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


def _make_user(conn):
    user_id = uuid4()
    conn.execute(
        text(
            "INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
            "VALUES (:id, :email, FALSE, now(), now())"
        ),
        {"id": str(user_id), "email": f"path-db-{user_id}@example.test"},
    )
    return user_id


def _insert_path_habit(
    conn,
    *,
    user_id,
    title: str = "Fajr on time",
    domain: str = "worship",
    frequency: str = "daily",
    is_active: bool = True,
):
    habit_id = uuid4()
    conn.execute(
        text(
            "INSERT INTO imperium_path_habits "
            "(id, user_id, title, description, domain, frequency, is_active, created_at, updated_at) "
            "VALUES (:id, :user_id, :title, NULL, :domain, :frequency, :is_active, now(), now())"
        ),
        {
            "id": str(habit_id),
            "user_id": str(user_id),
            "title": title,
            "domain": domain,
            "frequency": frequency,
            "is_active": is_active,
        },
    )
    return habit_id


def _insert_path_check_in(
    conn,
    *,
    user_id,
    habit_id,
    check_date: date = date(2026, 5, 25),
    status: str = "done",
    reason: str | None = None,
    note: str | None = None,
):
    check_in_id = uuid4()
    conn.execute(
        text(
            "INSERT INTO imperium_path_check_ins "
            "(id, user_id, habit_id, check_date, status, reason, note, created_at, updated_at) "
            "VALUES (:id, :user_id, :habit_id, :check_date, :status, :reason, :note, now(), now())"
        ),
        {
            "id": str(check_in_id),
            "user_id": str(user_id),
            "habit_id": str(habit_id),
            "check_date": check_date,
            "status": status,
            "reason": reason,
            "note": note,
        },
    )
    return check_in_id


def _expect_constraint_failure(exc: Exception) -> None:
    msg = str(exc).lower()
    assert "check" in msg or "foreign key" in msg or "unique" in msg or "violates" in msg or "constraint" in msg, (
        f"Expected database constraint error, got: {exc!r}"
    )


def test_imperium_path_check_ins_reject_duplicate_habit_date_for_same_user(engine) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            user_id = _make_user(conn)
            habit_id = _insert_path_habit(conn, user_id=user_id)
            _insert_path_check_in(conn, user_id=user_id, habit_id=habit_id)
            _insert_path_check_in(conn, user_id=user_id, habit_id=habit_id)

    _expect_constraint_failure(excinfo.value)


def test_imperium_path_habits_reject_invalid_frequency(engine) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            user_id = _make_user(conn)
            _insert_path_habit(conn, user_id=user_id, frequency="monthly")

    _expect_constraint_failure(excinfo.value)


def test_imperium_path_check_ins_reject_invalid_status(engine) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            user_id = _make_user(conn)
            habit_id = _insert_path_habit(conn, user_id=user_id)
            _insert_path_check_in(conn, user_id=user_id, habit_id=habit_id, status="late")

    _expect_constraint_failure(excinfo.value)


def test_imperium_path_check_ins_reject_missing_habit_fk(engine) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            user_id = _make_user(conn)
            _insert_path_check_in(conn, user_id=user_id, habit_id=uuid4())

    _expect_constraint_failure(excinfo.value)


def test_imperium_path_services_are_user_scoped_against_real_postgres(engine) -> None:
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            user_id = _make_user(conn)
            other_user_id = _make_user(conn)
            habit_id = _insert_path_habit(conn, user_id=user_id, title="User Path Habit")
            other_habit_id = _insert_path_habit(conn, user_id=other_user_id, title="Foreign Path Habit")
            check_in_id = _insert_path_check_in(
                conn,
                user_id=user_id,
                habit_id=habit_id,
                status="done",
                note="Completed",
            )
            _insert_path_check_in(
                conn,
                user_id=other_user_id,
                habit_id=other_habit_id,
                status="missed",
                reason="Foreign record",
            )

            with Session(bind=conn) as session:
                current_user = SimpleNamespace(id=user_id)

                habits = list_path_habits(
                    session,
                    current_user=current_user,
                    is_active=None,
                    domain=None,
                    limit=20,
                    offset=0,
                )
                check_ins = list_path_check_ins(
                    session,
                    current_user=current_user,
                    habit_id=None,
                    status=None,
                    date_from=date(2026, 5, 25),
                    date_to=date(2026, 5, 25),
                    limit=20,
                    offset=0,
                )
                today = get_path_today_view(
                    session,
                    current_user=current_user,
                    local_date=date(2026, 5, 25),
                    domain=None,
                    frequency=None,
                )

                assert [item.id for item in habits.items] == [habit_id]
                assert [item.id for item in check_ins.items] == [check_in_id]
                assert today.count == 1
                assert today.items[0].habit.id == habit_id
                assert today.items[0].check_in is not None
                assert today.items[0].check_in.id == check_in_id
                assert today.items[0].status == "done"
                with pytest.raises(PathHabitNotFoundError):
                    get_path_habit_detail(session, current_user=current_user, habit_id=other_habit_id)
        finally:
            transaction.rollback()
