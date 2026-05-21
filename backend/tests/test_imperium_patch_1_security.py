from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import UniqueConstraint

from app.core import internal_webhooks
from app.core.config import Settings
from app.models.auth import AuthEvent, User
from app.models.event import Event
from app.schemas.auth import AuthLoginRequest
from app.services.auth.v1 import login_user


class FakeRequest:
    def __init__(self, body: bytes) -> None:
        self._body = body

    async def body(self) -> bytes:
        return self._body


class FakeAuthDb:
    def __init__(self, *, scalar_result=None, scalar_exc: Exception | None = None) -> None:
        self.scalar_result = scalar_result
        self.scalar_exc = scalar_exc
        self.added = []
        self.rolled_back = False
        self.committed = False

    def scalar(self, _query):
        if self.scalar_exc is not None:
            raise self.scalar_exc
        return self.scalar_result

    def add(self, obj) -> None:
        self.added.append(obj)

    def rollback(self) -> None:
        self.rolled_back = True

    def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_internal_webhook_accepts_valid_hmac_without_plaintext_secret_header(monkeypatch) -> None:
    secret = "strong-internal-webhook-secret-for-tests"
    timestamp = int(datetime.now(UTC).timestamp())
    body = b'{"status":"ok"}'
    signature = internal_webhooks.sign_internal_webhook_body(
        secret=secret,
        timestamp=timestamp,
        body=body,
    )
    monkeypatch.setattr(
        internal_webhooks,
        "get_settings",
        lambda: SimpleNamespace(
            internal_webhook_secret=secret,
            webhook_timestamp_tolerance_seconds=60,
        ),
    )

    context = await internal_webhooks.verify_internal_webhook(
        FakeRequest(body),
        x_signature=signature,
        x_timestamp=str(timestamp),
        idempotency_key="internal-smoke-key",
    )

    assert context.idempotency_key == "internal-smoke-key"
    assert context.timestamp == timestamp


@pytest.mark.asyncio
async def test_internal_webhook_rejects_missing_or_invalid_signature(monkeypatch) -> None:
    secret = "strong-internal-webhook-secret-for-tests"
    timestamp = int(datetime.now(UTC).timestamp())
    body = b'{"status":"ok"}'
    monkeypatch.setattr(
        internal_webhooks,
        "get_settings",
        lambda: SimpleNamespace(
            internal_webhook_secret=secret,
            webhook_timestamp_tolerance_seconds=60,
        ),
    )

    with pytest.raises(HTTPException) as missing_signature:
        await internal_webhooks.verify_internal_webhook(
            FakeRequest(body),
            x_signature=None,
            x_timestamp=str(timestamp),
            idempotency_key="internal-smoke-key",
        )
    assert missing_signature.value.status_code == 401

    with pytest.raises(HTTPException) as invalid_signature:
        await internal_webhooks.verify_internal_webhook(
            FakeRequest(body),
            x_signature="bad-signature",
            x_timestamp=str(timestamp),
            idempotency_key="internal-smoke-key",
        )
    assert invalid_signature.value.status_code == 401


@pytest.mark.asyncio
async def test_internal_webhook_rejects_stale_timestamp(monkeypatch) -> None:
    secret = "strong-internal-webhook-secret-for-tests"
    timestamp = int((datetime.now(UTC) - timedelta(seconds=600)).timestamp())
    body = b'{"status":"ok"}'
    signature = internal_webhooks.sign_internal_webhook_body(
        secret=secret,
        timestamp=timestamp,
        body=body,
    )
    monkeypatch.setattr(
        internal_webhooks,
        "get_settings",
        lambda: SimpleNamespace(
            internal_webhook_secret=secret,
            webhook_timestamp_tolerance_seconds=60,
        ),
    )

    with pytest.raises(HTTPException) as stale_timestamp:
        await internal_webhooks.verify_internal_webhook(
            FakeRequest(body),
            x_signature=signature,
            x_timestamp=str(timestamp),
            idempotency_key="internal-stale-key",
        )

    assert stale_timestamp.value.status_code == 401
    assert stale_timestamp.value.detail == "Stale webhook timestamp."


def test_startup_rejects_placeholder_like_jwt_secret() -> None:
    settings = Settings(
        jwt_secret_key="local-dev-jwt-secret-replace-before-production",
        internal_webhook_secret="strong-internal-webhook-secret-for-tests",
    )

    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        settings.validate_for_startup()


def test_auth_internal_exception_path_sanitizes_reason_and_avoids_unbound_local_error() -> None:
    db = FakeAuthDb(scalar_exc=RuntimeError("raw database driver exception details"))
    request = AuthLoginRequest(
        email="user@example.com",
        password="wrong-password",
        device_label="Laptop",
    )

    with pytest.raises(RuntimeError, match="raw database driver exception details"):
        login_user(db, request, ip_address="127.0.0.1", user_agent="pytest")

    auth_event = next(item for item in db.added if isinstance(item, AuthEvent))
    assert auth_event.reason == "internal_error"
    assert "raw database driver exception details" not in auth_event.reason
    assert db.rolled_back is True
    assert db.committed is True


def test_auth_failure_reason_never_stores_raw_exception_string() -> None:
    user = User(
        id=uuid4(),
        email="user@example.com",
        password_hash=None,
        master_secret_hash=None,
    )
    db = FakeAuthDb(scalar_result=user)
    request = AuthLoginRequest(
        email="user@example.com",
        password="wrong-password",
        device_label="Laptop",
    )

    with pytest.raises(ValueError):
        login_user(db, request, ip_address="127.0.0.1", user_agent="pytest")

    auth_event = next(item for item in db.added if isinstance(item, AuthEvent))
    assert auth_event.reason == "invalid_credentials"
    assert auth_event.reason != "Invalid login credentials."


def test_event_id_unique_constraint_is_scoped_by_user_id() -> None:
    unique_constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in Event.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert unique_constraints["events_user_event_id_unique"] == ("user_id", "event_id")
    assert "events_event_id_unique" not in unique_constraints


# ---- Audit Patch 1 additions -----------------------------------------------


def test_ai_task_user_id_is_not_optional_in_orm() -> None:
    from app.models.ai import AITask

    assert AITask.__table__.c.user_id.nullable is False


def test_ai_result_user_id_is_not_optional_in_orm() -> None:
    from app.models.ai import AIResult

    assert AIResult.__table__.c.user_id.nullable is False


def test_ai_result_validation_user_id_is_not_optional_in_orm() -> None:
    from app.models.ai import AIResultValidation

    assert AIResultValidation.__table__.c.user_id.nullable is False


_VALID_SECRET = "x" * 40
_VALID_SECRET_ALT = "y" * 40


def test_startup_rejects_missing_canonical_user_id_in_production() -> None:
    settings = Settings(
        environment="production",
        jwt_secret_key=_VALID_SECRET,
        internal_webhook_secret=_VALID_SECRET_ALT,
        imperium_canonical_user_id=None,
    )
    with pytest.raises(RuntimeError, match="IMPERIUM_CANONICAL_USER_ID"):
        settings.validate_for_startup()


def test_startup_allows_missing_canonical_user_id_in_local() -> None:
    settings = Settings(
        environment="local",
        jwt_secret_key=_VALID_SECRET,
        internal_webhook_secret=_VALID_SECRET_ALT,
        imperium_canonical_user_id=None,
    )
    settings.validate_for_startup()  # must not raise


def test_startup_allows_missing_canonical_user_id_in_test() -> None:
    settings = Settings(
        environment="test",
        jwt_secret_key=_VALID_SECRET,
        internal_webhook_secret=_VALID_SECRET_ALT,
        imperium_canonical_user_id=None,
    )
    settings.validate_for_startup()  # must not raise


def test_startup_rejects_placeholder_n8n_secret_when_configured_in_production() -> None:
    settings = Settings(
        environment="production",
        jwt_secret_key=_VALID_SECRET,
        internal_webhook_secret=_VALID_SECRET_ALT,
        imperium_canonical_user_id=uuid4(),
        n8n_webhook_secret="local-dev-changeme-placeholder-too-short-or-not",
    )
    with pytest.raises(RuntimeError, match="N8N_WEBHOOK_SECRET"):
        settings.validate_for_startup()


def test_startup_rejects_placeholder_n8n_secret_when_configured_in_local() -> None:
    settings = Settings(
        environment="local",
        jwt_secret_key=_VALID_SECRET,
        internal_webhook_secret=_VALID_SECRET_ALT,
        imperium_canonical_user_id=None,
        n8n_webhook_secret="local-dev-changeme-placeholder-too-short-or-not",
    )
    with pytest.raises(RuntimeError, match="N8N_WEBHOOK_SECRET"):
        settings.validate_for_startup()


def test_ai_result_public_schema_excludes_raw_payload() -> None:
    from app.schemas.ai import AIResultRead

    assert "raw_payload" not in AIResultRead.model_fields


def test_ai_result_internal_schema_includes_raw_payload() -> None:
    from app.schemas.ai import AIResultInternalRead

    assert "raw_payload" in AIResultInternalRead.model_fields


def test_weekly_review_message_create_rejects_qwen_role() -> None:
    from pydantic import ValidationError

    from app.schemas.weekly_review import WeeklyReviewMessageCreate

    with pytest.raises(ValidationError):
        WeeklyReviewMessageCreate(role="qwen", content="x")


def test_weekly_review_message_create_rejects_opus_role() -> None:
    from pydantic import ValidationError

    from app.schemas.weekly_review import WeeklyReviewMessageCreate

    with pytest.raises(ValidationError):
        WeeklyReviewMessageCreate(role="opus", content="x")


def test_weekly_review_message_create_accepts_user_role() -> None:
    from app.schemas.weekly_review import WeeklyReviewMessageCreate

    msg = WeeklyReviewMessageCreate(role="user", content="hello")
    assert msg.role == "user"


def test_weekly_review_message_create_rejects_assistant_message_types() -> None:
    from pydantic import ValidationError

    from app.schemas.weekly_review import WeeklyReviewMessageCreate

    for message_type in ("initial_summary", "assistant_followup", "draft", "final_report", "system_note"):
        with pytest.raises(ValidationError):
            WeeklyReviewMessageCreate(role="user", message_type=message_type, content="x")
