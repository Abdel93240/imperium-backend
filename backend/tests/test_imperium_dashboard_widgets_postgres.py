"""PostgreSQL : widgets du tableau de bord Imperium — prochaine prière et pression (doc 59 §12.2)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("imperium dashboard widgets DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, func, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_dashboard  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.vault import PressureSnapshot  # noqa: E402
from app.schemas.vault import ImperiumVaultTransactionCreate  # noqa: E402
from app.services.imperium import vault_transactions  # noqa: E402
from app.services.imperium.dashboard_widgets import dashboard_widgets  # noqa: E402


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
        {"id": str(user_id), "email": f"dashw-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_dashboard.router, prefix="/api/imperium")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def test_widgets_show_next_prayer_and_pressure_without_writing(db) -> None:
    user = _user(db)
    vault_transactions.create_vault_transaction(
        db, current_user=user,
        payload=ImperiumVaultTransactionCreate(transaction_type="income", amount_cents=50000, timezone="Europe/Paris",
                                               occurred_at=datetime.now(UTC) - timedelta(minutes=5), category="vtc"),
        idempotency_key=uuid4().hex, request_method="POST", request_path="/t",
    )
    events_before = db.scalar(select(func.count()).select_from(Event).where(Event.user_id == user.id))
    body = _client(db, user).get("/api/imperium/dashboard/widgets").json()
    prayer = body["next_prayer"]
    assert prayer["prayer_name"] in {"fajr", "dhuhr", "asr", "maghrib", "isha"}
    assert 0 < prayer["countdown_seconds"] <= 24 * 3600
    assert prayer["source"] in {"mawaqit", "calculated"}
    pressure = body["pressure"]
    assert 0 <= pressure["score"] <= 100
    assert pressure["label"] in {"safe", "stable", "attention", "pressure", "critical"}
    assert float(pressure["daily_targets"]["minimum"]) >= 0
    # Lecture seule : ni instantané de pression ni événement écrits par le tableau de bord.
    assert db.scalar(select(func.count()).select_from(PressureSnapshot).where(PressureSnapshot.user_id == user.id)) == 0
    assert db.scalar(select(func.count()).select_from(Event).where(Event.user_id == user.id)) == events_before


def test_next_prayer_rolls_over_after_isha(db) -> None:
    user = _user(db)
    late = datetime(2026, 10, 18, 22, 30, tzinfo=UTC)  # après l'isha à Paris
    widgets = dashboard_widgets(db, current_user=user, now=late)
    assert widgets.next_prayer.prayer_name == "fajr"
    assert widgets.next_prayer.adhan_at.date().isoformat() == "2026-10-19"
