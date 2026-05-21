from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.v1.routes import internal
from app.core import internal_webhooks
from app.models.ai import AIResult, AIResultValidation, AITask
from app.schemas.ai import AIResultCallback, AIResultValidationCreate, AITaskCreate
from app.services.ai import tasks


class FakeDb:
    def __init__(self) -> None:
        self.objects = {}
        self.added = []
        self.committed = False

    def add(self, obj) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()
        now = datetime.now(UTC)
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if hasattr(obj, "updated_at") and getattr(obj, "updated_at", None) is None:
            obj.updated_at = now
        self.added.append(obj)
        self.objects[(type(obj), obj.id)] = obj

    def get(self, model, object_id):
        return self.objects.get((model, object_id))

    def scalar(self, _query):
        return None

    def commit(self) -> None:
        self.committed = True

    def refresh(self, _obj) -> None:
        return None


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4())


def _task(user_id) -> AITask:
    return AITask(
        id=uuid4(),
        user_id=user_id,
        task_type="weekly_review_analysis",
        status="queued",
        source_module="imperium",
        input_payload={"week_start": "2026-04-27"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _callback_payload(summary: str = "draft") -> AIResultCallback:
    return AIResultCallback(
        result_type="weekly_report.summary",
        result_payload={"summary": summary},
        model_used="qwen-router-future",
        provider="future",
        raw_payload={"raw": summary},
    )


def test_create_ai_task(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    monkeypatch.setattr(tasks, "_get_existing_task_by_idempotency", lambda *args, **kwargs: None)

    task, duplicate = tasks.create_ai_task(
        db,
        current_user=current_user,
        payload=AITaskCreate(
            task_type="weekly_review_analysis",
            source_module="imperium",
            input_payload={"week_start": "2026-04-27"},
        ),
        idempotency_key="task-key-1",
    )

    assert duplicate is False
    assert task.status == "queued"
    assert task.user_id == current_user.id
    assert task.idempotency_key == "task-key-1"
    assert db.committed is True


def test_receive_ai_result_is_idempotent_and_marks_pending_validation(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    task = _task(current_user.id)
    db.objects[(AITask, task.id)] = task

    def existing_result(*_args, **kwargs):
        for item in db.added:
            if isinstance(item, AIResult) and item.idempotency_key == kwargs["idempotency_key"]:
                return item
        return None

    monkeypatch.setattr(tasks, "_get_existing_result_by_idempotency", existing_result)

    result, duplicate = tasks.receive_ai_result(
        db,
        task_id=task.id,
        payload=_callback_payload(),
        idempotency_key="result-key-1",
    )
    replayed_result, replay_duplicate = tasks.receive_ai_result(
        db,
        task_id=task.id,
        payload=_callback_payload(),
        idempotency_key="result-key-1",
    )

    assert duplicate is False
    assert replay_duplicate is True
    assert replayed_result.id == result.id
    assert task.status == "result_received"
    assert result.status == "pending_validation"
    assert len([item for item in db.added if isinstance(item, AIResult)]) == 1


def test_internal_ai_result_callback_uses_hmac_without_plaintext_secret(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    task = _task(current_user.id)
    db.objects[(AITask, task.id)] = task
    monkeypatch.setattr(tasks, "_get_existing_result_by_idempotency", lambda *args, **kwargs: None)

    secret = "strong-internal-webhook-secret-for-tests"
    timestamp = int(datetime.now(UTC).timestamp())
    body = (
        b'{"result_type":"weekly_report.summary",'
        b'"result_payload":{"summary":"draft"},'
        b'"model_used":"qwen-router-future",'
        b'"provider":"future"}'
    )
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

    app = FastAPI()
    app.include_router(internal.router, prefix="/internal")
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    response = client.post(
        f"/internal/ai/tasks/{task.id}/result",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Timestamp": str(timestamp),
            "X-Signature": signature,
            "Idempotency-Key": "callback-key-1",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["task_id"] == str(task.id)
    assert data["result_status"] == "pending_validation"
    assert data["idempotency_key"] == "callback-key-1"


def test_internal_ai_result_callback_rejects_invalid_result_type(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    task = _task(current_user.id)
    db.objects[(AITask, task.id)] = task

    secret = "strong-internal-webhook-secret-for-tests"
    timestamp = int(datetime.now(UTC).timestamp())
    body = b'{"result_type":"unknown.result","result_payload":{"summary":"draft"}}'
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

    app = FastAPI()
    app.include_router(internal.router, prefix="/internal")
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    response = client.post(
        f"/internal/ai/tasks/{task.id}/result",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Timestamp": str(timestamp),
            "X-Signature": signature,
            "Idempotency-Key": "callback-key-invalid-type",
        },
    )

    assert response.status_code == 422
    assert task.status == "queued"
    assert not any(isinstance(item, AIResult) for item in db.added)


def test_receive_ai_result_same_idempotency_key_different_payload_conflicts(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    task = _task(current_user.id)
    db.objects[(AITask, task.id)] = task
    existing = AIResult(
        id=uuid4(),
        task_id=task.id,
        user_id=current_user.id,
        result_type="weekly_report.summary",
        status="pending_validation",
        result_payload={"summary": "draft"},
        raw_payload={"raw": "draft"},
        model_used="qwen-router-future",
        provider="future",
        idempotency_key="result-key-1",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    monkeypatch.setattr(tasks, "_get_existing_result_by_idempotency", lambda *args, **kwargs: existing)

    with pytest.raises(tasks.AIIdempotencyConflictError):
        tasks.receive_ai_result(
            db,
            task_id=task.id,
            payload=_callback_payload("different"),
            idempotency_key="result-key-1",
        )


def test_mark_ai_task_running_reports_transition_and_rejects_terminal_status() -> None:
    db = FakeDb()
    current_user = _user()
    task = _task(current_user.id)
    db.objects[(AITask, task.id)] = task

    running_task, transitioned = tasks.mark_ai_task_running(db, current_user=current_user, task_id=task.id)
    assert running_task.status == "running"
    assert transitioned is True

    same_task, transitioned_again = tasks.mark_ai_task_running(db, current_user=current_user, task_id=task.id)
    assert same_task.status == "running"
    assert transitioned_again is False

    task.status = "result_received"
    with pytest.raises(tasks.AIStateConflictError):
        tasks.mark_ai_task_running(db, current_user=current_user, task_id=task.id)


def test_validate_ai_result_creates_validation_without_canonical_side_effects() -> None:
    db = FakeDb()
    current_user = _user()
    task = _task(current_user.id)
    result = AIResult(
        id=uuid4(),
        task_id=task.id,
        user_id=current_user.id,
        result_type="weekly_report.summary",
        status="pending_validation",
        result_payload={"summary": "draft"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.objects[(AITask, task.id)] = task
    db.objects[(AIResult, result.id)] = result

    validation = tasks.validate_ai_result(
        db,
        current_user=current_user,
        result_id=result.id,
        payload=AIResultValidationCreate(
            validation_status="accepted",
            validated_payload={"summary": "accepted draft"},
            user_note="Looks good.",
        ),
    )

    assert isinstance(validation, AIResultValidation)
    assert result.status == "accepted"
    assert task.status == "validated"
    assert all(isinstance(item, AIResultValidation) for item in db.added)


def test_validate_ai_result_rejects_repeated_terminal_status() -> None:
    db = FakeDb()
    current_user = _user()
    task = _task(current_user.id)
    result = AIResult(
        id=uuid4(),
        task_id=task.id,
        user_id=current_user.id,
        result_type="weekly_report.summary",
        status="accepted",
        result_payload={"summary": "draft"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.objects[(AITask, task.id)] = task
    db.objects[(AIResult, result.id)] = result

    with pytest.raises(tasks.AIValidationError, match="terminal validation state"):
        tasks.validate_ai_result(
            db,
            current_user=current_user,
            result_id=result.id,
            payload=AIResultValidationCreate(validation_status="accepted"),
        )


def test_reject_ai_result_updates_status() -> None:
    db = FakeDb()
    current_user = _user()
    task = _task(current_user.id)
    result = AIResult(
        id=uuid4(),
        task_id=task.id,
        user_id=current_user.id,
        result_type="weekly_report.summary",
        status="pending_validation",
        result_payload={"summary": "draft"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.objects[(AITask, task.id)] = task
    db.objects[(AIResult, result.id)] = result

    validation = tasks.reject_ai_result(
        db,
        current_user=current_user,
        result_id=result.id,
        payload=AIResultValidationCreate(validation_status="rejected", user_note="Not useful."),
    )

    assert validation.validation_status == "rejected"
    assert result.status == "rejected"
    assert task.status == "rejected"


def test_reject_ai_result_rejects_repeated_terminal_status() -> None:
    db = FakeDb()
    current_user = _user()
    task = _task(current_user.id)
    result = AIResult(
        id=uuid4(),
        task_id=task.id,
        user_id=current_user.id,
        result_type="weekly_report.summary",
        status="rejected",
        result_payload={"summary": "draft"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.objects[(AITask, task.id)] = task
    db.objects[(AIResult, result.id)] = result

    with pytest.raises(tasks.AIValidationError, match="terminal validation state"):
        tasks.reject_ai_result(
            db,
            current_user=current_user,
            result_id=result.id,
            payload=AIResultValidationCreate(validation_status="rejected"),
        )

