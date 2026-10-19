"""PostgreSQL : journal central des appels IA et grille de prix (doc 43 §17, doc 78 F2-14)."""
from __future__ import annotations

import io
import json
from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("ai call logs DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, delete, select, text  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import ai_logs  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.models.ai import AICallLog, AIModelPricing  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.services.ai import call_log, ocr  # noqa: E402
from app.services.ai.providers.qwen import QwenClient, QwenProviderError  # noqa: E402


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine, monkeypatch):
    monkeypatch.setattr(call_log, "_session_factory", sessionmaker(bind=engine))
    with Session(engine) as session:
        session.execute(delete(AICallLog))
        session.commit()
        yield session
        session.rollback()
        session.execute(delete(AICallLog))
        session.execute(delete(AIModelPricing))
        session.commit()


def _settings(**overrides) -> Settings:
    return Settings(jwt_secret_key="secure-jwt-secret-for-call-logs-long",
                    internal_webhook_secret="secure-internal-secret-for-call-logs-long", **overrides)


def _logs(db) -> list[AICallLog]:
    db.expire_all()
    return list(db.scalars(select(AICallLog).order_by(AICallLog.called_at)))


def test_local_call_costs_nothing_and_cloud_cost_comes_from_the_grid(db) -> None:
    call_log.record(app_name="vault", task_type="vault_category", model_used="local-model", model_tier="local",
                    input_tokens=100, output_tokens=20, duration_ms=12)
    db.add(AIModelPricing(model_slug="cloud-model", input_cost_per_1m=Decimal("3"), output_cost_per_1m=Decimal("15")))
    db.commit()
    call_log.record(app_name="imperium", task_type="wr.plan", model_used="cloud-model", model_tier="cloud_standard",
                    input_tokens=1_000_000, output_tokens=100_000)
    call_log.record(app_name="imperium", task_type="wr.plan", model_used="unpriced", model_tier="cloud_premium",
                    input_tokens=10, output_tokens=10)
    local, cloud, unpriced = _logs(db)
    assert (local.cost_eur, local.total_tokens, local.success) == (Decimal("0"), 120, True)
    assert cloud.cost_eur == Decimal("4.500000")  # trigger doc 43 §17.3
    assert unpriced.cost_eur is None  # pas de prix connu : coût inconnu, pas zéro


def test_recording_never_breaks_the_caller(db, monkeypatch) -> None:
    def broken():
        raise RuntimeError("database down")

    monkeypatch.setattr(call_log, "_session_factory", broken)
    call_log.record(app_name="imperium", task_type="x", model_used="m", model_tier="local")  # ne lève pas
    with pytest.raises(ValueError):
        call_log.record(app_name="spotify", task_type="x", model_used="m", model_tier="local")


def test_local_executor_calls_are_logged_with_tokens_and_failures(db) -> None:
    settings = _settings(qwen_enabled=True, qwen_dry_run=False, qwen_base_url="http://local.test")
    ok = QwenClient(settings=settings, http_post=lambda *_a: {
        "response": json.dumps({"category": "carburant"}), "prompt_eval_count": 50, "eval_count": 7,
    })
    assert ok.call(prompt="p", mode="vault_category") == {"category": "carburant"}

    def boom(*_a):
        raise TimeoutError("slow")

    with pytest.raises(QwenProviderError):
        QwenClient(settings=settings, http_post=boom).call(prompt="p", mode="replan_revision")
    first, second = _logs(db)
    assert (first.app_name, first.task_type, first.model_tier, first.input_tokens, first.output_tokens) == (
        "vault", "vault_category", "local", 50, 7)
    assert first.model_used == ok.model_id and first.duration_ms is not None
    assert (second.app_name, second.success, second.error_code) == ("imperium", False, "provider_error")
    # Le mode dry-run n'appelle rien : rien n'est journalisé.
    QwenClient(settings=_settings(qwen_enabled=False)).call(prompt="p", mode="vault_category")
    assert len(_logs(db)) == 2


def test_ocr_and_vision_calls_are_logged(db, monkeypatch) -> None:
    settings = _settings(ocr_enabled=True, ocr_base_url="http://ocr.test")
    monkeypatch.setattr(ocr.urllib.request, "urlopen",
                        lambda *_a, **_k: io.BytesIO(json.dumps({"text": "ticket", "pages": 1}).encode()))
    ocr.recognize(b"x", filename="t.pdf", content_type="application/pdf", settings=settings, app_name="vault")
    ocr.analyze_image(b"x", task="pulse.meal_photo_macros", prompt="p", content_type="image/jpeg", settings=settings)
    recognized, vision = _logs(db)
    assert (recognized.app_name, recognized.task_type, recognized.model_tier) == ("vault", "ocr.recognize", "local")
    assert (vision.app_name, vision.task_type) == ("pulse", "vision.pulse.meal_photo_macros")
    assert recognized.model_used  # identifiant du rôle ocr_service (ou le rôle lui-même à défaut)


def test_call_log_routes(db) -> None:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"calls-{user_id}@example.test"})
    db.commit()
    user = db.get(User, user_id)
    call_log.record(app_name="vault", task_type="vault_category", model_used="local-model", model_tier="local")
    call_log.record(app_name="imperium", task_type="wr.plan", model_used="cloud", model_tier="cloud_premium",
                    success=False, error_code="timeout")
    app = FastAPI()
    app.include_router(ai_logs.router, prefix="/api/ai")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    calls = client.get("/api/ai/call-logs", params={"limit": 10}).json()["calls"]
    assert [row["task_type"] for row in calls] == ["wr.plan", "vault_category"]
    assert calls[0]["error_code"] == "timeout"
    days = client.get("/api/ai/call-logs/daily", params={"days": 7}).json()["days"]
    assert days[0]["day"] == datetime.now(ZoneInfo("Europe/Paris")).date().isoformat()  # jour de Paris
    assert (days[0]["total_calls"], days[0]["local_calls"], days[0]["premium_calls"], days[0]["errors"]) == (2, 1, 1, 1)
