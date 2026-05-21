from datetime import date
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.routes import ai, internal
from app.core import internal_webhooks
from app.core.config import Settings
from app.models.imperium import ImperiumWeeklyReviewFinalReport, ImperiumWeeklyReviewSession
from app.services.ai.providers.qwen import QwenClient, QwenProviderError, generate_wr_summary_with_qwen


def _settings(**overrides) -> Settings:
    values = {
        "jwt_secret_key": "secure-jwt-secret-for-qwen-suite-long",
        "internal_webhook_secret": "secure-internal-secret-for-qwen-suite-long",
    }
    values.update(overrides)
    return Settings(**values)


def _session() -> ImperiumWeeklyReviewSession:
    return ImperiumWeeklyReviewSession(
        id=uuid4(),
        user_id=uuid4(),
        week_start=date(2026, 4, 27),
        week_end=date(2026, 5, 3),
        status="preparing_initial_summary",
    )


def test_qwen_config_missing_does_not_break_startup_validation() -> None:
    settings = _settings()

    settings.validate_for_startup()

    assert settings.qwen_enabled is False
    assert settings.qwen_dry_run is True
    assert settings.qwen_base_url is None


def test_dry_run_classify_task_returns_valid_routing_decision_without_network() -> None:
    def forbidden_network(*_args, **_kwargs):
        raise AssertionError("dry-run must not call network")

    client = QwenClient(settings=_settings(), http_post=forbidden_network)

    decision = client.classify_task(
        task_type="imperium.daily_plan_assist",
        input_payload={"goal": "organize day"},
    )

    assert decision.task_type == "imperium.daily_plan_assist"
    assert 0 <= decision.difficulty_score <= 200
    assert decision.recommended_model in {"qwen2.5:7b-instruct", "strong_model_required_by_policy"}
    assert "dry_run" in decision.risk_flags


def test_dry_run_score_task_returns_score_between_zero_and_two_hundred() -> None:
    client = QwenClient(settings=_settings())

    score = client.score_task(task_type="vector.zone_recommendation", input_payload={"zone": "Paris"})

    assert 0 <= score <= 200


def test_dry_run_weekly_summary_returns_contract_result_type_without_network() -> None:
    def forbidden_network(*_args, **_kwargs):
        raise AssertionError("dry-run must not call network")

    client = QwenClient(settings=_settings(), http_post=forbidden_network)

    summary = client.generate_weekly_summary(input_payload={"week_start": "2026-04-27"})

    assert summary.result_type == "weekly_report.summary"
    assert summary.confidence > 0
    assert "dry_run_no_network" in summary.warnings


def test_real_adapter_invalid_json_raises_provider_error() -> None:
    client = QwenClient(
        settings=_settings(
            qwen_enabled=True,
            qwen_dry_run=False,
            qwen_base_url="http://qwen.local",
        ),
        http_post=lambda *_args, **_kwargs: {"response": "not-json"},
    )

    with pytest.raises(QwenProviderError, match="invalid JSON"):
        client.call(prompt="return json", mode="route")


def test_real_adapter_http_error_raises_provider_error() -> None:
    def broken_http(*_args, **_kwargs):
        raise TimeoutError("timeout")

    client = QwenClient(
        settings=_settings(
            qwen_enabled=True,
            qwen_dry_run=False,
            qwen_base_url="http://qwen.local",
        ),
        http_post=broken_http,
    )

    with pytest.raises(QwenProviderError, match="provider call failed"):
        client.call(prompt="return json", mode="route")


def test_wr_qwen_helper_returns_proposal_without_canonical_final_report() -> None:
    session = _session()
    client = QwenClient(settings=_settings())

    summary = generate_wr_summary_with_qwen(
        session=session,
        input_payload={"signals": []},
        qwen_client=client,
    )

    assert summary.result_type == "weekly_report.summary"
    assert session.status == "preparing_initial_summary"
    assert not isinstance(summary, ImperiumWeeklyReviewFinalReport)


def test_qwen_smoke_endpoint_is_jwt_protected() -> None:
    app = FastAPI()
    app.include_router(ai.router, prefix="/ai")
    client = TestClient(app)

    response = client.post(
        "/ai/qwen/smoke",
        json={"task_type": "weekly_report.summary", "input_payload": {}, "mode": "weekly_summary"},
    )

    assert response.status_code == 401


def _signed_internal_headers(secret: str, body: bytes, *, idempotency_key: str) -> dict[str, str]:
    timestamp = int(datetime.now(UTC).timestamp())
    return {
        "Content-Type": "application/json",
        "X-Timestamp": str(timestamp),
        "X-Signature": internal_webhooks.sign_internal_webhook_body(
            secret=secret,
            timestamp=timestamp,
            body=body,
        ),
        "Idempotency-Key": idempotency_key,
    }


def test_internal_qwen_smoke_hmac_returns_weekly_summary_without_db_write(monkeypatch) -> None:
    secret = "secure-internal-secret-for-qwen-bridge-long"
    body = (
        b'{"task_type":"weekly_report.summary","mode":"weekly_summary",'
        b'"input_payload":{"week_start":"2026-04-27"}}'
    )
    monkeypatch.setattr(
        internal_webhooks,
        "get_settings",
        lambda: type(
            "SettingsStub",
            (),
            {
                "internal_webhook_secret": secret,
                "webhook_timestamp_tolerance_seconds": 60,
            },
        )(),
    )

    app = FastAPI()
    app.include_router(internal.router, prefix="/internal")
    client = TestClient(app)

    response = client.post(
        "/internal/ai/qwen/smoke",
        content=body,
        headers=_signed_internal_headers(secret, body, idempotency_key="qwen-smoke-1"),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["result_type"] == "weekly_report.summary"
    assert "dry_run_no_network" in data["warnings"]


def test_internal_qwen_smoke_rejects_invalid_hmac(monkeypatch) -> None:
    secret = "secure-internal-secret-for-qwen-bridge-long"
    monkeypatch.setattr(
        internal_webhooks,
        "get_settings",
        lambda: type(
            "SettingsStub",
            (),
            {
                "internal_webhook_secret": secret,
                "webhook_timestamp_tolerance_seconds": 60,
            },
        )(),
    )

    app = FastAPI()
    app.include_router(internal.router, prefix="/internal")
    client = TestClient(app)

    response = client.post(
        "/internal/ai/qwen/smoke",
        json={"task_type": "weekly_report.summary", "mode": "weekly_summary", "input_payload": {}},
        headers={
            "X-Timestamp": str(int(datetime.now(UTC).timestamp())),
            "X-Signature": "bad",
            "Idempotency-Key": "qwen-smoke-bad-signature",
        },
    )

    assert response.status_code == 401


def test_internal_qwen_smoke_rejects_invalid_task_type(monkeypatch) -> None:
    secret = "secure-internal-secret-for-qwen-bridge-long"
    body = b'{"task_type":"imperium.daily_plan_assist","mode":"route","input_payload":{}}'
    monkeypatch.setattr(
        internal_webhooks,
        "get_settings",
        lambda: type(
            "SettingsStub",
            (),
            {
                "internal_webhook_secret": secret,
                "webhook_timestamp_tolerance_seconds": 60,
            },
        )(),
    )

    app = FastAPI()
    app.include_router(internal.router, prefix="/internal")
    client = TestClient(app)

    response = client.post(
        "/internal/ai/qwen/smoke",
        content=body,
        headers=_signed_internal_headers(secret, body, idempotency_key="qwen-smoke-invalid-task"),
    )

    assert response.status_code == 422
