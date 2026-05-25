"""PostgreSQL checks for Patch 11F Pulse invariants.

These tests require a migrated PostgreSQL database. They skip locally when
IMPERIUM_TEST_DATABASE_URL is not set and fail in CI if the variable is missing.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("Pulse DB constraint tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_pulse  # noqa: E402
from app.services.pulse import entries as pulse_entries_service  # noqa: E402
from app.services.pulse.entries import get_pulse_stats_summary  # noqa: E402


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


def _make_user(conn) -> UUID:
    user_id = uuid4()
    conn.execute(
        text(
            "INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
            "VALUES (:id, :email, FALSE, now(), now())"
        ),
        {"id": str(user_id), "email": f"pulse-db-{user_id}@example.test"},
    )
    return user_id


def _insert_pulse_entry(
    conn,
    *,
    user_id: UUID,
    entry_date: date = date(2026, 5, 25),
    sleep_hours: str | None = "7.50",
    energy_level: int | None = 8,
    fatigue_level: int | None = 3,
    weight_kg: str | None = "92.40",
    workout_done: bool | None = True,
    workout_type: str | None = "street_workout",
    notes: str | None = "Postgres constraint coverage",
    created_at: datetime | None = None,
) -> UUID:
    entry_id = uuid4()
    timestamp = created_at or datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    conn.execute(
        text(
            "INSERT INTO imperium_pulse_entries "
            "(id, user_id, entry_date, sleep_hours, energy_level, fatigue_level, weight_kg, "
            "workout_done, workout_type, notes, created_at, updated_at) "
            "VALUES (:id, :user_id, :entry_date, :sleep_hours, :energy_level, :fatigue_level, :weight_kg, "
            ":workout_done, :workout_type, :notes, :created_at, :updated_at)"
        ),
        {
            "id": str(entry_id),
            "user_id": str(user_id),
            "entry_date": entry_date,
            "sleep_hours": sleep_hours,
            "energy_level": energy_level,
            "fatigue_level": fatigue_level,
            "weight_kg": weight_kg,
            "workout_done": workout_done,
            "workout_type": workout_type,
            "notes": notes,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    return entry_id


def _client(engine, current_user: SimpleNamespace) -> TestClient:
    session_factory = sessionmaker(bind=engine, future=True)
    app = FastAPI()
    app.include_router(imperium_pulse.router, prefix="/imperium/pulse")
    app.dependency_overrides[get_current_user] = lambda: current_user

    def override_get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _valid_payload(**overrides) -> dict:
    payload = {
        "entry_date": "2026-05-25",
        "sleep_hours": 7.5,
        "energy_level": 8,
        "fatigue_level": 3,
        "weight_kg": 92.4,
        "workout_done": True,
        "workout_type": "street_workout",
        "notes": "Postgres route coverage",
    }
    payload.update(overrides)
    return payload


def _expect_constraint_failure(exc: Exception) -> None:
    msg = str(exc).lower()
    assert "check" in msg or "foreign key" in msg or "unique" in msg or "violates" in msg or "constraint" in msg, (
        f"Expected database constraint error, got: {exc!r}"
    )


def test_imperium_pulse_entries_reject_duplicate_user_entry_date(engine) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            user_id = _make_user(conn)
            _insert_pulse_entry(conn, user_id=user_id)
            _insert_pulse_entry(conn, user_id=user_id)

    _expect_constraint_failure(excinfo.value)


def test_create_pulse_entry_duplicate_date_returns_409_against_real_postgres(engine) -> None:
    with engine.begin() as conn:
        user_id = _make_user(conn)
        _insert_pulse_entry(conn, user_id=user_id)

    response = _client(engine, SimpleNamespace(id=user_id)).post(
        "/imperium/pulse/entries",
        headers={"Idempotency-Key": f"pulse-duplicate-date-{uuid4()}"},
        json=_valid_payload(),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Pulse entry already exists for this date."


def test_create_pulse_entry_integrity_error_race_returns_409_against_real_postgres(engine, monkeypatch) -> None:
    with engine.begin() as conn:
        user_id = _make_user(conn)
        _insert_pulse_entry(conn, user_id=user_id)

    monkeypatch.setattr(pulse_entries_service, "_get_existing_entry_for_date", lambda *args, **kwargs: None)

    response = _client(engine, SimpleNamespace(id=user_id)).post(
        "/imperium/pulse/entries",
        headers={"Idempotency-Key": f"pulse-integrity-race-{uuid4()}"},
        json=_valid_payload(),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Pulse entry conflicts with existing data."


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("energy_level", 11),
        ("fatigue_level", 0),
        ("sleep_hours", "24.25"),
        ("weight_kg", "0"),
    ),
)
def test_imperium_pulse_entries_reject_out_of_range_values(engine, field: str, value: object) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            user_id = _make_user(conn)
            _insert_pulse_entry(conn, user_id=user_id, **{field: value})

    _expect_constraint_failure(excinfo.value)


def test_imperium_pulse_entries_reject_workout_type_when_workout_done_false(engine) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            user_id = _make_user(conn)
            _insert_pulse_entry(conn, user_id=user_id, workout_done=False, workout_type="street_workout")

    _expect_constraint_failure(excinfo.value)


def test_pulse_stats_summary_latest_weight_uses_real_postgres_order(engine) -> None:
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            user_id = _make_user(conn)
            _insert_pulse_entry(
                conn,
                user_id=user_id,
                entry_date=date(2026, 5, 24),
                weight_kg="91.10",
                created_at=datetime(2026, 5, 25, 23, 0, tzinfo=UTC),
            )
            _insert_pulse_entry(
                conn,
                user_id=user_id,
                entry_date=date(2026, 5, 25),
                weight_kg="92.20",
                created_at=datetime(2026, 5, 24, 8, 0, tzinfo=UTC),
            )

            with Session(bind=conn) as session:
                summary = get_pulse_stats_summary(
                    session,
                    current_user=SimpleNamespace(id=user_id),
                    date_from=date(2026, 5, 1),
                    date_to=date(2026, 5, 31),
                )

            assert summary.latest_weight_kg == 92.2
        finally:
            if transaction.is_active:
                transaction.rollback()
