"""PostgreSQL : Historique — journées opérationnelles et bloc Finances (doc 65 §7.5, doc 43 §6.1)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("history days and finances DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_history  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.imperium import ImperiumMission, PlanningDay  # noqa: E402
from app.schemas.vault import ImperiumVaultTransactionCreate  # noqa: E402
from app.services.imperium import history, vault_transactions  # noqa: E402

TODAY = date(2026, 10, 18)
D1 = datetime(2026, 10, 16, 6, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    with Session(engine) as session:
        yield session
        session.rollback()


def _user(db) -> User:
    user_id = uuid4()
    db.execute(
        text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) VALUES (:id, :email, FALSE, now(), now())"),
        {"id": str(user_id), "email": f"histdays-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_history.router, prefix="/api/imperium")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _mission(db, user, status, ended_at, **extra) -> ImperiumMission:
    mission = ImperiumMission(user_id=user.id, title=status, status=status, started_at=ended_at - timedelta(hours=1),
                              ended_at=ended_at, **extra)
    db.add(mission)
    db.flush()
    return mission


def _tx(db, user, kind, cents, day: date) -> None:
    vault_transactions.create_vault_transaction(
        db, current_user=user,
        payload=ImperiumVaultTransactionCreate(transaction_type=kind, amount_cents=cents, timezone="Europe/Paris",
                                               occurred_at=datetime(day.year, day.month, day.day, 10, 0, tzinfo=UTC),
                                               category="courses"),
        idempotency_key=uuid4().hex, request_method="POST", request_path="/t",
    )


def test_days_with_their_missions(db) -> None:
    user = _user(db)
    first = PlanningDay(user_id=user.id, started_at=D1, finished_at=D1 + timedelta(hours=12), start_local_date=D1.date(),
                        timezone="Europe/Paris", felt_energy=4, idempotency_key=uuid4().hex)
    second_start = datetime(2026, 10, 18, 5, 0, tzinfo=UTC)
    second = PlanningDay(user_id=user.id, started_at=second_start, start_local_date=second_start.date(),
                         timezone="Europe/Paris", felt_energy=2, idempotency_key=uuid4().hex)
    db.add_all([first, second])
    done = _mission(db, user, "completed", D1 + timedelta(hours=2))
    _mission(db, user, "completed", D1 + timedelta(hours=3), annex_of_mission_id=done.id)
    _mission(db, user, "failed", D1 + timedelta(hours=5))
    _mission(db, user, "cancelled", second_start + timedelta(hours=1))
    _mission(db, user, "completed", D1 - timedelta(days=2))  # hors de toute journée
    db.commit()
    body = history.list_history_days(db, current_user=user, now=second_start + timedelta(hours=3)).model_dump(mode="json")
    assert [(d["status"], d["felt_energy"], d["duration_minutes"]) for d in body["items"]] == [("open", 2, 180), ("finished", 4, 720)]
    open_day, closed_day = body["items"]
    assert (open_day["missions_cancelled"], open_day["missions_completed"]) == (1, 0)
    assert (closed_day["missions_completed"], closed_day["missions_failed"], closed_day["annexes_completed"]) == (1, 1, 1)
    page = _client(db, user).get("/api/imperium/history/days", params={"limit": 1}).json()
    assert (page["count"], page["has_more"], page["items"][0]["planning_day_id"]) == (1, True, str(second.id))
    assert _client(db, _user(db)).get("/api/imperium/history/days").json()["items"] == []


def test_finances_curve_and_previous_period(db) -> None:
    user = _user(db)
    _tx(db, user, "income", 10000, date(2026, 10, 17))
    _tx(db, user, "expense", 2500, date(2026, 10, 17))
    _tx(db, user, "expense", 1000, date(2026, 10, 12))
    _tx(db, user, "income", 5000, date(2026, 10, 5))
    week = history.history_finances(db, current_user=user, period="week", today=TODAY)
    assert (week.from_day, len(week.points), week.period_net_cents) == (date(2026, 10, 12), 7, 6500)
    assert (week.previous_period_net_cents, week.delta_cents, week.balance_cents) == (5000, 1500, None)
    assert [(p.day.day, p.net_cents) for p in week.points if p.net_cents] == [(12, -1000), (17, 7500)]
    everything = history.history_finances(db, current_user=user, period="all", today=TODAY)
    assert (everything.from_day, everything.previous_period_net_cents, everything.delta_cents) == (date(2026, 10, 5), None, 11500)
    empty = _client(db, _user(db)).get("/api/imperium/history/finances", params={"period": "all"}).json()
    assert (empty["points"], empty["period_net_cents"], empty["from_day"]) == ([], 0, None)
    assert _client(db, user).get("/api/imperium/history/finances", params={"period": "decade"}).status_code == 422
