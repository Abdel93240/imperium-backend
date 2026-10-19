"""PostgreSQL : W4 anomalies sur les rollups et dépôt au docket par W5 (spec WR §4 W4-W5)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("wr anomalies DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, delete, select, text, update  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models import ai  # noqa: E402,F401 - FK de la session WR vers ai_tasks
from app.models.auth import User  # noqa: E402
from app.models.toolbox import SignalDefinition, SignalValue  # noqa: E402
from app.models.wr import WrDocketItem, WrRollupDaily, WrWorkerCursor, WrWorkerRun  # noqa: E402
from app.services.wr import anomalies, factory  # noqa: E402

DAY = date(2026, 10, 14)
SIGNAL = "wr.finance.expense"


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


def _reset(session: Session) -> None:
    session.execute(delete(SignalValue).where(SignalValue.signal_code.like("wr.%")))
    session.execute(update(SignalDefinition).where(SignalDefinition.domain == "wr").values(active=False))
    session.execute(delete(WrWorkerRun))
    session.execute(delete(WrWorkerCursor))
    session.commit()


@pytest.fixture()
def db(engine):
    with Session(engine) as session:
        _reset(session)
        session.execute(update(SignalDefinition).where(SignalDefinition.code == SIGNAL).values(active=True))
        session.commit()
        yield session
        session.rollback()
        _reset(session)


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"w4-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _history(db, user, *, last_expense: int, days: int = 28, computed_at: datetime | None = None) -> None:
    computed_at = computed_at or datetime.now(UTC)
    for offset in range(days, 0, -1):
        day = DAY - timedelta(days=offset)
        db.add(WrRollupDaily(user_id=user.id, local_date=day, domain="finance", computed_at=computed_at,
                             metrics={"expense_cents": 5000 + (offset % 2) * 1000, "income_cents": 0}))
    db.add(WrRollupDaily(user_id=user.id, local_date=DAY, domain="finance", computed_at=computed_at,
                         metrics={"expense_cents": last_expense, "income_cents": 0}))
    db.commit()


def test_signals_are_seeded_inactive(db) -> None:
    rows = db.scalars(select(SignalDefinition).where(SignalDefinition.domain == "wr")).all()
    assert len(rows) == 8
    assert [row.code for row in rows if row.active] == [SIGNAL]  # activé par ce test seulement
    expense = next(row for row in rows if row.code == SIGNAL)
    assert expense.source == "wr_rollups_daily:finance.expense_cents" and expense.bands["direction"] == "high"


def test_only_active_signals_are_evaluated_and_rewritten(db) -> None:
    user = _user(db)
    _history(db, user, last_expense=20000)
    written = anomalies.evaluate_days(db, user=user, days=[DAY])
    anomalies.evaluate_days(db, user=user, days=[DAY])  # recalcul : remplace, ne double pas
    db.commit()
    rows = db.scalars(select(SignalValue).where(SignalValue.signal_code.like("wr.%"))).all()
    assert len(written) == 1 and len(rows) == 1
    row = rows[0]
    assert (row.signal_code, row.band, row.flags) == (SIGNAL, "red", {"flag": True, "unexplained": True})
    assert row.detail["baseline"] == 5500 and row.detail["user_id"] == str(user.id)
    assert anomalies.evaluate_days(db, user=user, days=[DAY - timedelta(days=20)]) == []  # historique trop court


def test_factory_files_orange_and_red_anomalies_once(db, monkeypatch) -> None:
    user = _user(db)
    now = datetime(2026, 10, 14, 21, 30, tzinfo=UTC)
    _history(db, user, last_expense=20000, computed_at=now - timedelta(minutes=5))
    real = factory.get_parameter
    monkeypatch.setattr(factory, "get_parameter", lambda _db, code, default=None: (
        ["w4_anomalies", "w5_docket"] if code == "wr.factory_workers_enabled" else real(_db, code, default=default)))
    summary = factory.run_factory(db, user=user, trigger="manual", now=now)
    factory.run_factory(db, user=user, trigger="manual", now=now + timedelta(hours=1))
    db.commit()
    assert summary["completed"] == ["w4_anomalies", "w5_docket"]
    items = db.scalars(select(WrDocketItem).where(WrDocketItem.user_id == user.id)).all()
    assert len(items) == 1
    item = items[0]
    assert (item.item_type, item.domain, item.severity, item.impact_estimate, item.source_worker) == (
        "anomaly", "vault", "elevated", 4, "w4")
    assert item.evidence_refs["local_date"] == DAY.isoformat() and item.payload["unexplained"] is True


def test_yellow_stays_a_signal(db, monkeypatch) -> None:
    user = _user(db)
    now = datetime(2026, 10, 14, 21, 30, tzinfo=UTC)
    _history(db, user, last_expense=7800, computed_at=now - timedelta(minutes=5))  # z = 2,3 (échelle plancher 1000)
    real = factory.get_parameter
    monkeypatch.setattr(factory, "get_parameter", lambda _db, code, default=None: (
        ["w4_anomalies", "w5_docket"] if code == "wr.factory_workers_enabled" else real(_db, code, default=default)))
    factory.run_factory(db, user=user, trigger="manual", now=now)
    db.commit()
    assert db.scalar(select(SignalValue.band).where(SignalValue.signal_code == SIGNAL,
                                                    SignalValue.measured_at == anomalies.measured_at(DAY))) == "yellow"
    assert db.scalar(select(WrDocketItem).where(WrDocketItem.user_id == user.id)) is None
