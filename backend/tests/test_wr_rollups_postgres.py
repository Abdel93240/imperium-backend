"""PostgreSQL : W1 rollups quotidiens par domaine (spec WR §4 W1, carte V18 ACT-WR-03)."""
from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("wr rollups DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, delete, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models import ai  # noqa: E402,F401 - FK de la session WR vers ai_tasks
from app.models.auth import User  # noqa: E402
from app.models.imperium import ImperiumMission  # noqa: E402
from app.models.rides import RidesDropZone, RidesSession  # noqa: E402
from app.models.vault import ImperiumVaultTransaction, PressureSnapshot  # noqa: E402
from app.models.wr import WrRollupDaily, WrWorkerCursor, WrWorkerRun  # noqa: E402
from app.services.wr import factory, rollups  # noqa: E402

PARIS = ZoneInfo("Europe/Paris")
DAY = date(2026, 10, 14)


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
        session.execute(delete(WrWorkerRun))
        session.execute(delete(WrWorkerCursor))
        session.commit()


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"rollup-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=PARIS)


def _tx(db, user, kind: str, cents: int, *, day: date = DAY, reversal_of=None) -> ImperiumVaultTransaction:
    row = ImperiumVaultTransaction(
        user_id=user.id, transaction_type=kind, amount_cents=cents, currency="EUR", wallet="cash",
        occurred_at=_at(day, 12), local_date=day, timezone="Europe/Paris", is_reversal=reversal_of is not None,
        reversal_of_transaction_id=reversal_of.id if reversal_of is not None else None,
        reversal_reason="Erreur de saisie." if reversal_of is not None else None,
    )
    db.add(row)
    db.flush()
    return row


def _fixtures(db, user) -> None:
    _tx(db, user, "income", 15000)
    wrong = _tx(db, user, "expense", 1000)
    _tx(db, user, "expense", 3000)
    _tx(db, user, "income", 1000, reversal_of=wrong)  # annule la dépense erronée
    _tx(db, user, "expense", 999, day=DAY + timedelta(days=1))
    db.add(PressureSnapshot(user_id=user.id, computed_at=_at(DAY, 8), score=40, label="stable", factors={},
                            daily_targets={}, inputs_snapshot={}))
    db.add(PressureSnapshot(user_id=user.id, computed_at=_at(DAY, 20), score=55, label="attention", factors={},
                            daily_targets={}, inputs_snapshot={}))
    session = RidesSession(user_id=user.id, status="completed", started_at=_at(DAY, 14), ended_at=_at(DAY, 18),
                           final_revenue_cents=12000, final_expense_cents=2000, idempotency_key=uuid4().hex,
                           request_hash="h")
    db.add(session)
    db.flush()
    for zone in ("Gare de Lyon", "Gare de Lyon", "Orly"):
        db.add(RidesDropZone(user_id=user.id, session_id=session.id, zone=zone, recorded_at=_at(DAY, 15),
                             idempotency_key=uuid4().hex, request_hash="h"))
    for status, ended, deadline in (
        ("completed", _at(DAY, 11), _at(DAY, 10)),  # 60 min de retard
        ("completed", _at(DAY, 12), _at(DAY, 13)),  # à l'heure
        ("failed", _at(DAY, 16), None),
        ("cancelled", _at(DAY, 17), None),
        ("active", None, _at(DAY, 9)),  # en retard, toujours ouverte
    ):
        db.add(ImperiumMission(user_id=user.id, title="M", status=status, started_at=_at(DAY, 7), ended_at=ended,
                               deadline_at=deadline))
    db.commit()


def test_day_metrics_per_domain(db) -> None:
    user = _user(db)
    _fixtures(db, user)
    metrics = rollups.compute_day(db, user=user, day=DAY)
    assert metrics["finance"] == {"income_cents": 16000, "expense_cents": 4000, "net_cents": 12000,
                                  "transaction_count": 4, "reversal_count": 1, "pressure_score": 55}
    assert metrics["rides"] == {
        "sessions_ended": 1, "revenue_cents": 12000, "expense_cents": 2000, "worked_minutes": 240,
        "net_per_hour_cents": 2500, "drop_zones": 3,
        "top_zones": [{"zone": "Gare de Lyon", "count": 2}, {"zone": "Orly", "count": 1}],
    }
    assert metrics["missions"] == {"started": 5, "completed": 2, "failed": 1, "cancelled": 1, "completed_late": 1,
                                   "avg_deadline_drift_min": 60, "overdue_open_at_day_end": 1}
    empty = rollups.compute_day(db, user=user, day=DAY - timedelta(days=3))
    assert empty["rides"]["net_per_hour_cents"] is None and empty["finance"]["pressure_score"] is None


def test_late_entry_recomputes_its_own_day_and_upsert_never_doubles(db) -> None:
    user = _user(db)
    _fixtures(db, user)
    window_from = datetime.now(UTC)  # après les fixtures
    _tx(db, user, "expense", 500, day=DAY - timedelta(days=10))  # saisie maintenant pour un jour ancien
    db.commit()
    window_to = datetime.now(UTC) + timedelta(seconds=1)
    days = rollups.touched_days(db, user=user, window_from=window_from, window_to=window_to)
    assert DAY - timedelta(days=10) in days and window_to.astimezone(PARIS).date() in days
    assert DAY not in days  # rien de DAY n'a bougé dans la fenêtre
    now = datetime.now(UTC)
    rollups.rollup_days(db, user=user, days=[DAY], now=now)
    rollups.rollup_days(db, user=user, days=[DAY], now=now + timedelta(minutes=1))
    db.commit()
    rows = db.scalars(select(WrRollupDaily).where(WrRollupDaily.user_id == user.id)).all()
    assert sorted(row.domain for row in rows) == ["finance", "missions", "rides"]
    assert all(row.computed_at == now + timedelta(minutes=1) for row in rows)


def test_w1_runs_inside_the_factory_when_enabled(db, monkeypatch) -> None:
    user = _user(db)
    _fixtures(db, user)
    monkeypatch.setattr(factory, "get_parameter", lambda _db, code, default=None: ["w1_rollups"])
    now = _at(DAY, 23, 30)
    summary = factory.run_factory(db, user=user, trigger="manual", now=now)
    db.commit()
    assert summary["completed"] == ["w1_rollups"]
    run = db.scalar(select(WrWorkerRun).where(WrWorkerRun.worker == "w1_rollups"))
    assert run.detail["pulse"] == "stub" and DAY.isoformat() in run.detail["days"]
    finance = db.scalar(select(WrRollupDaily).where(WrRollupDaily.user_id == user.id, WrRollupDaily.local_date == DAY,
                                                    WrRollupDaily.domain == "finance"))
    assert finance.metrics["net_cents"] == 12000
