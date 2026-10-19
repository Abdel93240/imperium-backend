"""PostgreSQL : vues d'analyse et seuils d'alerte du journal des appels IA (doc 43 §17.4, §17.6)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("ai call alerts DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, delete, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import ai_logs  # noqa: E402
from app.models.ai import AICallLog  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.toolbox import Notification  # noqa: E402
from app.services.ai import call_alerts  # noqa: E402
from app.services.runner.engine import RunContext, Window  # noqa: E402

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
VIEWS = ("ai_hallucination_tracker", "ai_error_analysis", "ai_latency_profile", "ai_6month_trend",
         "ai_fallback_effectiveness", "ai_vs_estimates")


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    with Session(engine) as session:
        session.execute(delete(AICallLog))
        session.execute(delete(Notification).where(Notification.ref_type == "ai_call_alert"))
        session.commit()
        yield session
        session.rollback()
        session.execute(delete(AICallLog))
        session.execute(delete(Notification).where(Notification.ref_type == "ai_call_alert"))
        session.commit()


def _call(db, *, at: datetime = NOW - timedelta(minutes=10), **fields) -> None:
    values = {"app_name": "imperium", "task_type": "t", "model_used": "m", "model_tier": "local",
              "cost_eur": Decimal("0"), "success": True}
    values.update(fields)
    db.add(AICallLog(called_at=at, **values))
    db.commit()


def _codes(db) -> set[str]:
    return {alert.code for alert in call_alerts.evaluate(db, now=NOW)}


def test_quiet_journal_raises_nothing(db) -> None:
    for _ in range(30):
        _call(db, duration_ms=500)
    assert _codes(db) == set()


def test_spend_and_single_call_alerts(db) -> None:
    _call(db, model_tier="cloud_premium", cost_eur=Decimal("0.60"))  # appel seul > 0,50 €
    _call(db, model_tier="cloud_premium", cost_eur=Decimal("1.00"))  # jour > 1,50 €
    _call(db, at=NOW - timedelta(days=3), model_tier="cloud_standard", cost_eur=Decimal("6.00"))  # 7 jours > 7 €
    assert _codes(db) == {"daily_spend", "weekly_spend", "single_call_cost"}
    daily = next(alert for alert in call_alerts.evaluate(db, now=NOW) if alert.code == "daily_spend")
    assert (daily.value, daily.threshold) == (pytest.approx(1.6), 1.5)


def test_error_rate_needs_a_minimum_sample(db) -> None:
    for index in range(10):
        _call(db, success=index > 1, error_code=None if index > 1 else "timeout")
    assert "error_rate" not in _codes(db)  # 20 % mais 10 appels seulement
    for _ in range(10):
        _call(db)
    assert "error_rate" in _codes(db)  # 2 sur 20 = 10 % > 5 %


def test_hallucination_latency_and_fallback_alerts(db) -> None:
    for index in range(12):
        _call(db, task_type="vault_category", was_validated=index >= 2)  # 2/12 ≈ 16,7 % > 15 %
    for _ in range(10):
        _call(db, task_type="ocr.recognize", duration_ms=40_000)
    for _ in range(4):
        _call(db, at=NOW - timedelta(minutes=20), fallback_used=True, original_model="primary")
    alerts = {alert.code: alert for alert in call_alerts.evaluate(db, now=NOW)}
    assert {"hallucination_rate", "p90_latency", "fallbacks_last_hour"} <= set(alerts)
    assert "vault_category" in alerts["hallucination_rate"].message_fr
    assert "ocr.recognize" in alerts["p90_latency"].message_fr


def test_job_notifies_once_per_day(db, monkeypatch) -> None:
    _call(db, model_tier="cloud_premium", cost_eur=Decimal("2.00"))
    ctx = RunContext(db=db, job=None, run_id=uuid4(), trigger="manual", trigger_ref=None)
    call_alerts.ai_call_alerts_job(ctx, Window(from_ts=None, to_ts=NOW))
    call_alerts.ai_call_alerts_job(ctx, Window(from_ts=None, to_ts=NOW + timedelta(minutes=60)))
    notes = db.scalars(select(Notification).where(Notification.ref_type == "ai_call_alert")).all()
    assert sorted(note.domain for note in notes) == ["system", "system"]  # jour + appel seul, sans doublon
    assert all(note.severity == "normal" for note in notes)
    assert ctx.items_out == 0 and ctx.cursor_ts == NOW + timedelta(minutes=60)


def test_views_exist_and_alerts_route(db) -> None:
    for view in VIEWS:
        db.execute(text(f"SELECT * FROM {view} LIMIT 1"))  # nosec B608 - noms de vues fixes du test
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"alerts-{user_id}@example.test"})
    db.commit()
    user = db.get(User, user_id)
    _call(db, at=datetime.now(UTC) - timedelta(minutes=5), model_tier="cloud_premium", cost_eur=Decimal("0.70"))
    app = FastAPI()
    app.include_router(ai_logs.router, prefix="/api/ai")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    body = TestClient(app).get("/api/ai/call-logs/alerts").json()
    assert [alert["code"] for alert in body["alerts"]] == ["single_call_cost"]
    assert db.scalar(select(Notification).where(Notification.ref_type == "ai_call_alert")) is None  # lecture seule
