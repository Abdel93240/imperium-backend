"""Database-level AI ownership constraint tests.

These tests require a PostgreSQL database with migrations applied. They skip
locally when IMPERIUM_TEST_DATABASE_URL is not set and fail in CI if the
variable is missing.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("AI ownership DB constraint tests")

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
        {"id": user_id, "email": f"ai-owner-test-{user_id}@example.test"},
    )
    return user_id


def _make_ai_task(conn, *, user_id: str) -> str:
    task_id = str(uuid4())
    conn.execute(
        text(
            "INSERT INTO ai_tasks (id, user_id, task_type, status, source_module, input_payload, created_at, updated_at) "
            "VALUES (:id, :user_id, 'test.task', 'queued', 'imperium', '{}'::jsonb, now(), now())"
        ),
        {"id": task_id, "user_id": user_id},
    )
    return task_id


def _make_ai_result(conn, *, user_id: str, task_id: str) -> str:
    result_id = str(uuid4())
    conn.execute(
        text(
            "INSERT INTO ai_results (id, task_id, user_id, result_type, status, result_payload, created_at, updated_at) "
            "VALUES (:id, :task_id, :user_id, 'test.result', 'pending_validation', '{}'::jsonb, now(), now())"
        ),
        {"id": result_id, "task_id": task_id, "user_id": user_id},
    )
    return result_id


def test_ai_tasks_reject_null_user_id(engine) -> None:
    with engine.begin() as conn:
        with pytest.raises(Exception):
            conn.execute(
                text(
                    "INSERT INTO ai_tasks (id, user_id, task_type, status, source_module, input_payload, created_at, updated_at) "
                    "VALUES (:id, NULL, 'test.task', 'queued', 'imperium', '{}'::jsonb, now(), now())"
                ),
                {"id": str(uuid4())},
            )


def test_ai_results_reject_null_user_id(engine) -> None:
    with engine.begin() as conn:
        user_id = _make_user(conn)
        task_id = _make_ai_task(conn, user_id=user_id)
        with pytest.raises(Exception):
            conn.execute(
                text(
                    "INSERT INTO ai_results (id, task_id, user_id, result_type, status, result_payload, created_at, updated_at) "
                    "VALUES (:id, :task_id, NULL, 'test.result', 'pending_validation', '{}'::jsonb, now(), now())"
                ),
                {"id": str(uuid4()), "task_id": task_id},
            )


def test_ai_result_validations_reject_null_user_id(engine) -> None:
    with engine.begin() as conn:
        user_id = _make_user(conn)
        task_id = _make_ai_task(conn, user_id=user_id)
        result_id = _make_ai_result(conn, user_id=user_id, task_id=task_id)
        with pytest.raises(Exception):
            conn.execute(
                text(
                    "INSERT INTO ai_result_validations "
                    "(id, result_id, task_id, user_id, validation_status, created_at) "
                    "VALUES (:id, :result_id, :task_id, NULL, 'accepted', now())"
                ),
                {"id": str(uuid4()), "result_id": result_id, "task_id": task_id},
            )
