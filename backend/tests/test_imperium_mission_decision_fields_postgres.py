"""PostgreSQL checks for Patch 7F-1 mission decision fields.

These tests require a migrated PostgreSQL database. They skip locally when
IMPERIUM_TEST_DATABASE_URL is not set and fail in CI if the variable is missing.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("mission decision field DB tests")

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
        {"id": user_id, "email": f"mission-df-{user_id}@example.test"},
    )
    return user_id


def _insert_mission(
    conn,
    *,
    user_id: str,
    status: str = "active",
    domain: str | None = None,
    priority_level: int | None = None,
    mission_type_category: str | None = None,
) -> str:
    mission_id = str(uuid4())
    conn.execute(
        text(
            "INSERT INTO imperium_missions "
            "(id, user_id, title, status, domain, priority_level, mission_type_category, started_at, created_at, updated_at) "
            "VALUES (:id, :user_id, :title, :status, :domain, :priority_level, :mission_type_category, :now, :now, :now)"
        ),
        {
            "id": mission_id,
            "user_id": user_id,
            "title": f"Mission {mission_id}",
            "status": status,
            "domain": domain,
            "priority_level": priority_level,
            "mission_type_category": mission_type_category,
            "now": datetime.now(UTC),
        },
    )
    return mission_id


def _expect_check_failure(exc: Exception) -> None:
    msg = str(exc).lower()
    assert "check" in msg or "violates" in msg or "constraint" in msg, f"Expected check constraint error, got: {exc!r}"


def test_imperium_missions_domain_check_constraint(engine) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            user_id = _make_user(conn)
            _insert_mission(conn, user_id=user_id, domain="family")
    _expect_check_failure(excinfo.value)


def test_imperium_missions_priority_level_check_constraint(engine) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            user_id = _make_user(conn)
            _insert_mission(conn, user_id=user_id, priority_level=11)
    _expect_check_failure(excinfo.value)


def test_imperium_missions_mission_type_category_check_constraint(engine) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            user_id = _make_user(conn)
            _insert_mission(conn, user_id=user_id, mission_type_category="cat_z")
    _expect_check_failure(excinfo.value)


def test_imperium_missions_status_accepts_backlog(engine) -> None:
    with engine.begin() as conn:
        user_id = _make_user(conn)
        mission_id = _insert_mission(
            conn,
            user_id=user_id,
            status="backlog",
            domain="business",
            priority_level=4,
            mission_type_category="cat_e",
        )
        stored_status = conn.scalar(text("SELECT status FROM imperium_missions WHERE id = :id"), {"id": mission_id})

    assert stored_status == "backlog"


def test_imperium_missions_status_accepts_abandoned(engine) -> None:
    with engine.begin() as conn:
        user_id = _make_user(conn)
        mission_id = _insert_mission(
            conn,
            user_id=user_id,
            status="abandoned",
            domain="business",
            priority_level=4,
            mission_type_category="cat_e",
        )
        stored_status = conn.scalar(text("SELECT status FROM imperium_missions WHERE id = :id"), {"id": mission_id})

    assert stored_status == "abandoned"


def test_imperium_mission_scores_unique_user_mission_source(engine) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            user_id = _make_user(conn)
            mission_id = _insert_mission(
                conn,
                user_id=user_id,
                status="backlog",
                domain="business",
                priority_level=4,
                mission_type_category="cat_e",
            )
            params = {
                "score_id": str(uuid4()),
                "user_id": user_id,
                "mission_id": mission_id,
                "domain": "business",
                "intrinsic_score": 10,
                "domain_coefficient": 8,
                "weighted_score": 80,
                "explanation": "{}",
                "source": "decision_framework_v1",
                "now": datetime.now(UTC),
            }
            conn.execute(
                text(
                    "INSERT INTO imperium_mission_scores "
                    "(id, user_id, mission_id, domain, intrinsic_score, domain_coefficient, weighted_score, "
                    "explanation, source, created_at, updated_at) "
                    "VALUES (:score_id, :user_id, :mission_id, :domain, :intrinsic_score, "
                    ":domain_coefficient, :weighted_score, CAST(:explanation AS jsonb), :source, :now, :now)"
                ),
                params,
            )
            params["score_id"] = str(uuid4())
            conn.execute(
                text(
                    "INSERT INTO imperium_mission_scores "
                    "(id, user_id, mission_id, domain, intrinsic_score, domain_coefficient, weighted_score, "
                    "explanation, source, created_at, updated_at) "
                    "VALUES (:score_id, :user_id, :mission_id, :domain, :intrinsic_score, "
                    ":domain_coefficient, :weighted_score, CAST(:explanation AS jsonb), :source, :now, :now)"
                ),
                params,
            )
    msg = str(excinfo.value).lower()
    assert "unique" in msg or "duplicate" in msg or "constraint" in msg
