import hmac
import json
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium, internal
from app.core import internal_webhooks
from app.core.config import Settings
from app.models.ai import AIMemory, AIResult, AITask
from app.models.auth import User
from app.models.idempotency import IdempotencyKey
from app.models.imperium import (
    ImperiumMemoryCandidateDecision,
    ImperiumWeeklyReviewFinalReport,
    ImperiumWeeklyReviewMessage,
    ImperiumWeeklyReviewSession,
)
from app.schemas.weekly_review import (
    WeeklyReviewAnswerRequest,
    WeeklyReviewAttachAIResultRequest,
    WeeklyReviewCancelRequest,
    WeeklyReviewChatConfirmRequest,
    WeeklyReviewDraftCreate,
    WeeklyReviewDraftRejectRequest,
    WeeklyReviewFinalApproveRequest,
    WeeklyReviewMemoryCandidateApproveRequest,
    WeeklyReviewMemoryCandidateEditRequest,
    WeeklyReviewMemoryCandidateRejectRequest,
    WeeklyReviewMemoryCommitRequest,
    WeeklyReviewMemoryCommitDryRunRequest,
    WeeklyReviewMessageRead,
)
from app.schemas.ai import AIResultCallback
from app.services.imperium import weekly_review_conversation as wr
from app.services.imperium import wr_bridge as wr_bridge_module
from app.services.integrations import n8n_client


class FakeDb:
    def __init__(self) -> None:
        self.added = []
        self.objects = {}
        self.scalar_results = []
        self.scalars_results = []
        self.committed = False
        self.rolled_back = False

    def add(self, obj) -> None:
        self._prepare(obj)
        self.added.append(obj)
        self.objects[(type(obj), obj.id)] = obj

    def flush(self) -> None:
        for obj in self.added:
            self._prepare(obj)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def refresh(self, obj) -> None:
        self._prepare(obj)

    def get(self, model, object_id):
        return self.objects.get((model, object_id))

    def scalar(self, _query):
        if self.scalar_results:
            return self.scalar_results.pop(0)
        return None

    def scalars(self, _query):
        if self.scalars_results:
            return self.scalars_results.pop(0)
        return []

    def _prepare(self, obj) -> None:
        now = datetime.now(UTC)
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()
        if hasattr(obj, "created_at") and getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if hasattr(obj, "updated_at") and getattr(obj, "updated_at", None) is None:
            obj.updated_at = now


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4())


def _session(user_id, *, status: str = "ready") -> ImperiumWeeklyReviewSession:
    now = datetime.now(UTC)
    return ImperiumWeeklyReviewSession(
        id=uuid4(),
        user_id=user_id,
        week_start=date(2026, 4, 27),
        week_end=date(2026, 5, 3),
        status=status,
        created_at=now,
        updated_at=now,
    )


def _message(
    session: ImperiumWeeklyReviewSession,
    *,
    created_at: datetime,
    content: str,
) -> ImperiumWeeklyReviewMessage:
    return ImperiumWeeklyReviewMessage(
        id=uuid4(),
        session_id=session.id,
        user_id=session.user_id,
        role="user",
        message_type="user_answer",
        content=content,
        payload=None,
        created_at=created_at,
    )


def _ai_result(user_id, task_id=None, *, result_type: str = "weekly_report.summary") -> AIResult:
    now = datetime.now(UTC)
    return AIResult(
        id=uuid4(),
        task_id=task_id or uuid4(),
        user_id=user_id,
        result_type=result_type,
        status="pending_validation",
        result_payload={"summary": "draft"},
        model_used="future-qwen",
        provider="qwen",
        created_at=now,
        updated_at=now,
    )


def _ai_task(user_id) -> AITask:
    now = datetime.now(UTC)
    return AITask(
        id=uuid4(),
        user_id=user_id,
        task_type="weekly_report.interactive.start",
        status="queued",
        source_module="imperium",
        input_payload={"week_start": "2026-04-27"},
        created_at=now,
        updated_at=now,
    )


def _final_report(
    session: ImperiumWeeklyReviewSession,
    *,
    status: str = "draft",
    summary: str = "draft",
    markdown: str = "# Draft",
    created_at: datetime | None = None,
    source_ai_result_id=None,
) -> ImperiumWeeklyReviewFinalReport:
    now = created_at or datetime.now(UTC)
    return ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=session.user_id,
        week_start=session.week_start,
        week_end=session.week_end,
        status=status,
        report_payload={"summary": summary},
        report_markdown=markdown,
        source_ai_result_id=source_ai_result_id,
        approved_at=now if status in {"approved", "stored"} else None,
        stored_at=now if status == "stored" else None,
        created_at=now,
        updated_at=now,
    )


def _idempotency_from_added(db: FakeDb, key: str) -> IdempotencyKey | None:
    for item in db.added:
        if isinstance(item, IdempotencyKey) and item.idempotency_key == key:
            return item
    return None


def test_get_or_create_weekly_review_session_requires_monday(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    monkeypatch.setattr(wr, "_get_session_by_week", lambda *args, **kwargs: None)

    session = wr.get_or_create_weekly_review_session(
        db,
        current_user=current_user,
        week_start=date(2026, 4, 27),
    )

    assert session.user_id == current_user.id
    assert session.week_end == date(2026, 5, 3)
    with pytest.raises(wr.InvalidWeekStartError):
        wr.get_or_create_weekly_review_session(db, current_user=current_user, week_start=date(2026, 4, 28))


def test_launch_creates_session_ai_task_and_replays_idempotently(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    monkeypatch.setattr(wr, "_get_session_by_week", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        wr,
        "_get_existing_idempotency",
        lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key),
    )

    first, duplicate = wr.launch_weekly_review_session(
        db,
        current_user=current_user,
        week_start=date(2026, 4, 27),
        idempotency_key="wr-launch-1",
        request_method="POST",
        request_path="/api/imperium/weekly-review/launch",
    )
    replay, replay_duplicate = wr.launch_weekly_review_session(
        db,
        current_user=current_user,
        week_start=date(2026, 4, 27),
        idempotency_key="wr-launch-1",
        request_method="POST",
        request_path="/api/imperium/weekly-review/launch",
    )

    assert duplicate is False
    assert replay_duplicate is True
    assert replay.id == first.id
    assert first.status == "preparing_initial_summary"
    ai_task = next(item for item in db.added if isinstance(item, AITask))
    assert ai_task.prepared_payload == {
        "task_id": str(ai_task.id),
        "session_id": str(first.id),
        "task_type": "weekly_report.interactive.start",
        "week_start": "2026-04-27",
        "week_end": "2026-05-03",
        "callback_url": f"/api/internal/ai/tasks/{ai_task.id}/result",
        "wr_attach_url": f"/api/internal/weekly-review/{first.id}/attach-ai-result",
    }


def test_launch_bridge_disabled_does_not_run_bridge(monkeypatch) -> None:
    # Passe 0: the n8n webhook became the in-process wr_bridge, gated by
    # wr_bridge_enabled (default False keeps the queued-task behavior).
    db = FakeDb()
    current_user = _user()
    monkeypatch.setattr(wr, "_get_session_by_week", lambda *args, **kwargs: None)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        wr,
        "get_settings",
        lambda: Settings(
            jwt_secret_key="strong-jwt-secret-for-tests-that-is-long",
            internal_webhook_secret="strong-internal-secret-for-tests-long",
            wr_bridge_enabled=False,
        ),
    )
    monkeypatch.setattr(
        wr_bridge_module,
        "run_wr_interactive_start",
        lambda *args, **kwargs: pytest.fail("disabled bridge must not run"),
    )

    result, duplicate = wr.launch_weekly_review_session(
        db,
        current_user=current_user,
        week_start=date(2026, 4, 27),
        idempotency_key="wr-launch-dry-run",
        request_method="POST",
        request_path="/api/imperium/weekly-review/launch",
    )

    assert duplicate is False
    assert result.status == "preparing_initial_summary"


def test_launch_bridge_enabled_runs_bridge_once_with_prepared_payload(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    calls = []
    monkeypatch.setattr(wr, "_get_session_by_week", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        wr,
        "_get_existing_idempotency",
        lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key),
    )
    monkeypatch.setattr(
        wr,
        "get_settings",
        lambda: Settings(
            jwt_secret_key="strong-jwt-secret-for-tests-that-is-long",
            internal_webhook_secret="strong-internal-secret-for-tests-long",
            wr_bridge_enabled=True,
        ),
    )
    monkeypatch.setattr(
        wr_bridge_module,
        "run_wr_interactive_start",
        lambda _db, *, ai_task: calls.append(ai_task),
    )

    first, duplicate = wr.launch_weekly_review_session(
        db,
        current_user=current_user,
        week_start=date(2026, 4, 27),
        idempotency_key="wr-launch-n8n",
        request_method="POST",
        request_path="/api/imperium/weekly-review/launch",
    )
    replay, replay_duplicate = wr.launch_weekly_review_session(
        db,
        current_user=current_user,
        week_start=date(2026, 4, 27),
        idempotency_key="wr-launch-n8n",
        request_method="POST",
        request_path="/api/imperium/weekly-review/launch",
    )

    assert duplicate is False
    assert replay_duplicate is True
    assert replay.id == first.id
    assert len(calls) == 1
    ai_task = next(item for item in db.added if isinstance(item, AITask))
    assert calls[0] is ai_task
    # Same payload shape the n8n export validated (equivalence, fixtures).
    payload = ai_task.prepared_payload
    assert payload["task_type"] == "weekly_report.interactive.start"
    assert payload["callback_url"] == f"/api/internal/ai/tasks/{ai_task.id}/result"
    assert payload["wr_attach_url"].endswith("/attach-ai-result")


def test_launch_bridge_invalid_payload_records_error_without_breaking(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    monkeypatch.setattr(wr, "_get_session_by_week", lambda *args, **kwargs: None)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        wr,
        "get_settings",
        lambda: Settings(
            jwt_secret_key="strong-jwt-secret-for-tests-that-is-long",
            internal_webhook_secret="strong-internal-secret-for-tests-long",
            wr_bridge_enabled=True,
        ),
    )

    def invalid_payload(_db, *, ai_task):
        raise wr_bridge_module.WRBridgePayloadError("Missing required WR payload field: task_id")

    monkeypatch.setattr(wr_bridge_module, "run_wr_interactive_start", invalid_payload)

    result, duplicate = wr.launch_weekly_review_session(
        db,
        current_user=current_user,
        week_start=date(2026, 4, 27),
        idempotency_key="wr-launch-no-base-url",
        request_method="POST",
        request_path="/api/imperium/weekly-review/launch",
    )

    ai_task = next(item for item in db.added if isinstance(item, AITask))
    assert duplicate is False
    assert result.status == "preparing_initial_summary"
    assert ai_task.error_code == "wr_bridge_payload_invalid"
    assert "task_id" in ai_task.error_message


def test_launch_bridge_failure_keeps_session_and_task_without_duplicates(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    monkeypatch.setattr(wr, "_get_session_by_week", lambda *args, **kwargs: None)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        wr,
        "get_settings",
        lambda: Settings(
            jwt_secret_key="strong-jwt-secret-for-tests-that-is-long",
            internal_webhook_secret="strong-internal-secret-for-tests-long",
            wr_bridge_enabled=True,
        ),
    )

    def failing_bridge(_db, *, ai_task):
        raise RuntimeError("bridge exploded")

    monkeypatch.setattr(wr_bridge_module, "run_wr_interactive_start", failing_bridge)

    result, duplicate = wr.launch_weekly_review_session(
        db,
        current_user=current_user,
        week_start=date(2026, 4, 27),
        idempotency_key="wr-launch-n8n-failure",
        request_method="POST",
        request_path="/api/imperium/weekly-review/launch",
    )

    tasks = [item for item in db.added if isinstance(item, AITask)]
    sessions = [item for item in db.added if isinstance(item, ImperiumWeeklyReviewSession)]
    assert duplicate is False
    assert result.status == "preparing_initial_summary"
    assert len(tasks) == 1
    assert len(sessions) == 1
    assert tasks[0].error_code == "wr_bridge_failed"
    assert tasks[0].error_message == "bridge exploded"


def test_launch_bridge_is_in_process_and_never_touches_network(monkeypatch) -> None:
    # The ported bridge is a direct call chain: no webhook, no HMAC, no socket.
    import urllib.request

    db = FakeDb()
    current_user = _user()
    monkeypatch.setattr(wr, "_get_session_by_week", lambda *args, **kwargs: None)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        wr,
        "get_settings",
        lambda: Settings(
            jwt_secret_key="strong-jwt-secret-for-tests-that-is-long",
            internal_webhook_secret="strong-internal-secret-for-tests-long",
            wr_bridge_enabled=True,
        ),
    )
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *args, **kwargs: pytest.fail("the WR bridge must never open a socket"),
    )
    seen = []
    monkeypatch.setattr(
        wr_bridge_module, "run_wr_interactive_start", lambda _db, *, ai_task: seen.append(ai_task)
    )

    result, duplicate = wr.launch_weekly_review_session(
        db,
        current_user=current_user,
        week_start=date(2026, 4, 27),
        idempotency_key="wr-launch-n8n-missing-secret",
        request_method="POST",
        request_path="/api/imperium/weekly-review/launch",
    )

    assert duplicate is False
    assert result.status == "preparing_initial_summary"
    assert len(seen) == 1


def test_launch_with_different_key_for_existing_week_returns_existing(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    existing_session = _session(current_user.id, status="preparing_initial_summary")
    monkeypatch.setattr(wr, "_get_session_by_week", lambda *args, **kwargs: existing_session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    result, duplicate = wr.launch_weekly_review_session(
        db,
        current_user=current_user,
        week_start=existing_session.week_start,
        idempotency_key="wr-launch-2",
        request_method="POST",
        request_path="/api/imperium/weekly-review/launch",
    )

    assert duplicate is False
    assert result.id == existing_session.id


def test_user_message_is_stored_in_backend_without_n8n(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="waiting_for_user_answer")
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    result, duplicate = wr.add_user_message(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewAnswerRequest(content="My answer", payload={"signal": "ok"}),
        idempotency_key="wr-answer-1",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/answer",
    )

    assert duplicate is False
    assert result.role == "user"
    assert session.status == "integrating_answers"
    assert any(isinstance(item, ImperiumWeeklyReviewMessage) for item in db.added)
    assert not any(isinstance(item, AITask) for item in db.added)


def test_chat_message_creates_user_message_and_assistant_followup_without_draft(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="initial_summary_ready")
    session.initial_ai_result_id = uuid4()
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(
        wr,
        "_get_existing_idempotency",
        lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key),
    )

    first, duplicate = wr.add_weekly_review_chat_message(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewAnswerRequest(content="J'ai eu un blocage budget.", payload={"origin": "test"}),
        idempotency_key="wr-chat-message-1",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/chat/messages",
    )
    replay, replay_duplicate = wr.add_weekly_review_chat_message(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewAnswerRequest(content="J'ai eu un blocage budget.", payload={"origin": "test"}),
        idempotency_key="wr-chat-message-1",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/chat/messages",
    )

    messages = [item for item in db.added if isinstance(item, ImperiumWeeklyReviewMessage)]
    assert duplicate is False
    assert replay_duplicate is True
    assert replay.id == first.id
    assert session.status == "conversation_active"
    assert [message.message_type for message in messages] == ["chat_message", "assistant_followup"]
    assert messages[1].role == "qwen"
    assert messages[1].content.endswith(wr.WR_FINAL_CONFIRMATION_PROMPT)
    assert not any(isinstance(item, ImperiumWeeklyReviewFinalReport) for item in db.added)
    assert not any(isinstance(item, AITask) for item in db.added)


def test_chat_message_rejects_draft_ready_until_request_changes(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    with pytest.raises(wr.WeeklyReviewStateConflictError, match="Request changes"):
        wr.add_weekly_review_chat_message(
            db,
            session_id=session.id,
            current_user=current_user,
            payload=WeeklyReviewAnswerRequest(content="I forgot one thing."),
            idempotency_key="wr-chat-draft-ready",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/{session.id}/chat/messages",
        )


def test_confirm_no_more_input_rejects_without_user_input(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="conversation_active")
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)
    db.scalars_results = [[]]

    with pytest.raises(wr.WeeklyReviewStateConflictError, match="without user-provided input"):
        wr.confirm_weekly_review_no_more_input(
            db,
            session_id=session.id,
            current_user=current_user,
            payload=WeeklyReviewChatConfirmRequest(),
            idempotency_key="wr-chat-confirm-no-input",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/{session.id}/chat/confirm-no-more-input",
        )


def test_confirm_no_more_input_rejects_when_draft_ready_with_new_key(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    with pytest.raises(wr.WeeklyReviewStateConflictError, match="already has a draft"):
        wr.confirm_weekly_review_no_more_input(
            db,
            session_id=session.id,
            current_user=current_user,
            payload=WeeklyReviewChatConfirmRequest(content="No more."),
            idempotency_key="wr-chat-confirm-draft-ready",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/{session.id}/chat/confirm-no-more-input",
        )


def test_confirm_no_more_input_creates_final_draft_candidate_idempotently(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="conversation_active")
    session.initial_ai_result_id = uuid4()
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(
        wr,
        "_get_existing_idempotency",
        lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key),
    )
    db.scalars_results = [[], []]

    first, duplicate = wr.confirm_weekly_review_no_more_input(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewChatConfirmRequest(content="Non, tu peux préparer le brouillon.", payload={"done": True}),
        idempotency_key="wr-chat-confirm-1",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/chat/confirm-no-more-input",
    )
    replay, replay_duplicate = wr.confirm_weekly_review_no_more_input(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewChatConfirmRequest(content="Non, tu peux préparer le brouillon.", payload={"done": True}),
        idempotency_key="wr-chat-confirm-1",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/chat/confirm-no-more-input",
    )

    reports = [item for item in db.added if isinstance(item, ImperiumWeeklyReviewFinalReport)]
    messages = [item for item in db.added if isinstance(item, ImperiumWeeklyReviewMessage)]
    tasks = [item for item in db.added if isinstance(item, AITask)]
    results = [item for item in db.added if isinstance(item, AIResult)]
    assert duplicate is False
    assert replay_duplicate is True
    assert replay.id == first.id
    assert first.status == "draft_ready"
    assert session.status == "draft_ready"
    assert len(tasks) == 1
    assert len(results) == 1
    assert len(reports) == 1
    assert messages[-1].content is not None
    assert messages[-1].content.startswith("# Weekly Review")
    assert reports[0].status == "draft"
    assert reports[0].approved_at is None
    assert reports[0].stored_at is None
    assert [message.message_type for message in messages] == ["chat_message", "final_report_draft"]
    assert not any("Memory" in type(item).__name__ for item in db.added)


def test_confirm_after_request_changes_creates_second_draft_history(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    first_report = _final_report(session, status="draft", source_ai_result_id=uuid4())
    session.initial_ai_result_id = uuid4()
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)
    db.scalar_results = [first_report]

    wr.request_draft_changes(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewAnswerRequest(content="Ajoute la partie énergie."),
        idempotency_key="wr-chat-request-changes",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/draft/request-changes",
    )
    db.scalars_results = [[first_report]]
    result, duplicate = wr.confirm_weekly_review_no_more_input(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewChatConfirmRequest(content="Rien d'autre."),
        idempotency_key="wr-chat-confirm-revised",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/chat/confirm-no-more-input",
    )

    reports = [item for item in db.added if isinstance(item, ImperiumWeeklyReviewFinalReport)]
    assert duplicate is False
    assert result.status == "draft_ready"
    assert first_report.status == "superseded"
    assert len(reports) == 1
    assert reports[0].status == "draft"
    assert reports[0].source_ai_result_id is not None


def test_closed_session_rejects_chat_and_confirm(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    with pytest.raises(wr.WeeklyReviewStateConflictError):
        wr.add_weekly_review_chat_message(
            db,
            session_id=session.id,
            current_user=current_user,
            payload=WeeklyReviewAnswerRequest(content="Too late"),
            idempotency_key="wr-chat-closed",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/{session.id}/chat/messages",
        )
    with pytest.raises(wr.WeeklyReviewStateConflictError):
        wr.confirm_weekly_review_no_more_input(
            db,
            session_id=session.id,
            current_user=current_user,
            payload=WeeklyReviewChatConfirmRequest(),
            idempotency_key="wr-chat-confirm-closed",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/{session.id}/chat/confirm-no-more-input",
        )


def test_answer_flow_creates_integration_ai_task_with_prepared_payload(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="waiting_for_user_answer")
    session.initial_ai_result_id = uuid4()
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    result, duplicate = wr.add_user_message(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewAnswerRequest(content="My answer", payload={"signal": "ok"}),
        idempotency_key="wr-answer-integrate-1",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/answer",
        create_integration_task=True,
        trigger_type="user_message",
    )

    messages = [item for item in db.added if isinstance(item, ImperiumWeeklyReviewMessage)]
    tasks = [item for item in db.added if isinstance(item, AITask)]
    assert duplicate is False
    assert result.id == messages[0].id
    assert session.status == "integrating_answers"
    assert len(messages) == 1
    assert len(tasks) == 1
    ai_task = tasks[0]
    assert ai_task.task_type == "weekly_report.answers.integrate"
    assert ai_task.source_module == "imperium"
    assert session.current_ai_task_id == ai_task.id
    expected_payload = {
        "task_id": str(ai_task.id),
        "session_id": str(session.id),
        "task_type": "weekly_report.answers.integrate",
        "source": "backend_wr_answer",
        "trigger_type": "user_message",
        "source_ref_type": "weekly_review_session",
        "source_ref_id": str(session.id),
        "week_start": "2026-04-27",
        "week_end": "2026-05-03",
        "user_message_id": str(result.id),
        "user_answer": "My answer",
        "latest_user_answer_message_id": str(result.id),
        "latest_initial_ai_result_id": str(session.initial_ai_result_id),
        "callback_url": f"/api/internal/ai/tasks/{ai_task.id}/result",
        "wr_attach_url": f"/api/internal/weekly-review/{session.id}/attach-ai-result",
    }
    assert ai_task.input_payload == expected_payload
    assert ai_task.prepared_payload == expected_payload
    assert not any(isinstance(item, ImperiumWeeklyReviewFinalReport) for item in db.added)
    assert not any("Memory" in type(item).__name__ for item in db.added)


def test_answer_flow_preserves_existing_current_ai_task_pointer(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="waiting_for_user_answer")
    launch_task = _ai_task(current_user.id)
    session.current_ai_task_id = launch_task.id
    session.initial_ai_result_id = uuid4()
    db.objects[(AITask, launch_task.id)] = launch_task
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(
        wr,
        "_get_existing_idempotency",
        lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key),
    )

    first, duplicate = wr.add_user_message(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewAnswerRequest(content="My answer", payload={"signal": "ok"}),
        idempotency_key="wr-answer-integrate-existing-task",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/answer",
        create_integration_task=True,
        trigger_type="user_message",
    )
    replay, replay_duplicate = wr.add_user_message(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewAnswerRequest(content="My answer", payload={"signal": "ok"}),
        idempotency_key="wr-answer-integrate-existing-task",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/answer",
        create_integration_task=True,
        trigger_type="user_message",
    )

    messages = [item for item in db.added if isinstance(item, ImperiumWeeklyReviewMessage)]
    tasks = [item for item in db.added if isinstance(item, AITask)]
    assert duplicate is False
    assert replay_duplicate is True
    assert replay.id == first.id
    assert len(messages) == 1
    assert len(tasks) == 1
    answer_task = tasks[0]
    assert answer_task.task_type == "weekly_report.answers.integrate"
    assert session.current_ai_task_id == launch_task.id
    assert answer_task.id != launch_task.id
    assert answer_task.prepared_payload["task_id"] == str(answer_task.id)
    assert answer_task.prepared_payload["latest_user_answer_message_id"] == str(messages[0].id)
    assert answer_task.prepared_payload["latest_initial_ai_result_id"] == str(session.initial_ai_result_id)
    assert answer_task.prepared_payload["callback_url"] == f"/api/internal/ai/tasks/{answer_task.id}/result"


def test_answer_flow_idempotency_replay_does_not_duplicate_message_or_task(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="waiting_for_user_answer")
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(
        wr,
        "_get_existing_idempotency",
        lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key),
    )

    first, duplicate = wr.add_user_message(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewAnswerRequest(content="My answer", payload={"signal": "ok"}),
        idempotency_key="wr-answer-integrate-replay",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/answer",
        create_integration_task=True,
        trigger_type="user_message",
    )
    replay, replay_duplicate = wr.add_user_message(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewAnswerRequest(content="My answer", payload={"signal": "ok"}),
        idempotency_key="wr-answer-integrate-replay",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/answer",
        create_integration_task=True,
        trigger_type="user_message",
    )

    assert duplicate is False
    assert replay_duplicate is True
    assert replay.id == first.id
    assert len([item for item in db.added if isinstance(item, ImperiumWeeklyReviewMessage)]) == 1
    assert len([item for item in db.added if isinstance(item, AITask)]) == 1


def test_answer_integration_bridge_disabled_does_not_run_bridge(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="waiting_for_user_answer")
    calls = []
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        wr,
        "get_settings",
        lambda: Settings(
            jwt_secret_key="strong-jwt-secret-for-tests-that-is-long",
            internal_webhook_secret="strong-internal-secret-for-tests-long",
            wr_bridge_enabled=False,
        ),
    )
    monkeypatch.setattr(
        wr_bridge_module, "run_wr_answers_integrate", lambda _db, *, ai_task: calls.append(ai_task)
    )

    wr.add_user_message(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewAnswerRequest(content="My answer", payload={"signal": "ok"}),
        idempotency_key="wr-answer-dry-run",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/answer",
        create_integration_task=True,
        trigger_type="user_message",
    )

    assert len([item for item in db.added if isinstance(item, ImperiumWeeklyReviewMessage)]) == 1
    assert len([item for item in db.added if isinstance(item, AITask)]) == 1
    assert calls == []


def test_answer_integration_bridge_enabled_runs_once_with_export_payload_shape(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="waiting_for_user_answer")
    calls = []
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        wr,
        "get_settings",
        lambda: Settings(
            jwt_secret_key="strong-jwt-secret-for-tests-that-is-long",
            internal_webhook_secret="strong-internal-secret-for-tests-long",
            wr_bridge_enabled=True,
        ),
    )
    monkeypatch.setattr(
        wr_bridge_module, "run_wr_answers_integrate", lambda _db, *, ai_task: calls.append(ai_task)
    )

    result, duplicate = wr.add_user_message(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewAnswerRequest(content="My answer", payload={"signal": "ok"}),
        idempotency_key="wr-answer-n8n-enabled",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/answer",
        create_integration_task=True,
        trigger_type="user_message",
    )

    ai_task = next(item for item in db.added if isinstance(item, AITask))
    assert duplicate is False
    assert len(calls) == 1
    assert calls[0] is ai_task
    # Field-for-field the shape the n8n export validated (equivalence lock).
    payload = ai_task.prepared_payload
    assert payload["task_id"] == str(ai_task.id)
    assert payload["session_id"] == str(session.id)
    assert payload["task_type"] == "weekly_report.answers.integrate"
    assert payload["callback_url"] == f"/api/internal/ai/tasks/{ai_task.id}/result"
    assert payload["wr_attach_url"] == f"/api/internal/weekly-review/{session.id}/attach-ai-result"
    assert payload["user_message_id"] == str(result.id)
    assert payload["user_answer"] == "My answer"
    assert "raw_payload" not in payload


def test_answer_integration_replay_does_not_rerun_bridge(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="waiting_for_user_answer")
    calls = []
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(
        wr,
        "_get_existing_idempotency",
        lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key),
    )
    monkeypatch.setattr(
        wr,
        "get_settings",
        lambda: Settings(
            jwt_secret_key="strong-jwt-secret-for-tests-that-is-long",
            internal_webhook_secret="strong-internal-secret-for-tests-long",
            wr_bridge_enabled=True,
        ),
    )
    monkeypatch.setattr(
        wr_bridge_module, "run_wr_answers_integrate", lambda _db, *, ai_task: calls.append(ai_task)
    )

    first, duplicate = wr.add_user_message(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewAnswerRequest(content="My answer", payload={"signal": "ok"}),
        idempotency_key="wr-answer-n8n-replay",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/answer",
        create_integration_task=True,
        trigger_type="user_message",
    )
    replay, replay_duplicate = wr.add_user_message(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewAnswerRequest(content="My answer", payload={"signal": "ok"}),
        idempotency_key="wr-answer-n8n-replay",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/answer",
        create_integration_task=True,
        trigger_type="user_message",
    )

    assert duplicate is False
    assert replay_duplicate is True
    assert replay.id == first.id
    assert len([item for item in db.added if isinstance(item, ImperiumWeeklyReviewMessage)]) == 1
    assert len([item for item in db.added if isinstance(item, AITask)]) == 1
    assert len(calls) == 1


def test_answer_integration_bridge_failure_records_error_without_failing_answer(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="waiting_for_user_answer")
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        wr,
        "get_settings",
        lambda: Settings(
            jwt_secret_key="strong-jwt-secret-for-tests-that-is-long",
            internal_webhook_secret="strong-internal-secret-for-tests-long",
            wr_bridge_enabled=True,
        ),
    )

    def failing_bridge(_db, *, ai_task):
        raise RuntimeError("bridge unavailable")

    monkeypatch.setattr(wr_bridge_module, "run_wr_answers_integrate", failing_bridge)

    result, duplicate = wr.add_user_message(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewAnswerRequest(content="My answer", payload={"signal": "ok"}),
        idempotency_key="wr-answer-n8n-failure",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/answer",
        create_integration_task=True,
        trigger_type="user_message",
    )

    ai_task = next(item for item in db.added if isinstance(item, AITask))
    assert duplicate is False
    assert result.content == "My answer"
    assert ai_task.error_code == "wr_bridge_failed"
    assert ai_task.error_message == "bridge unavailable"
    assert len([item for item in db.added if isinstance(item, ImperiumWeeklyReviewMessage)]) == 1


def test_answer_integration_invalid_payload_records_error_without_failing_answer(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="waiting_for_user_answer")
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        wr,
        "get_settings",
        lambda: Settings(
            jwt_secret_key="strong-jwt-secret-for-tests-that-is-long",
            internal_webhook_secret="strong-internal-secret-for-tests-long",
            wr_bridge_enabled=True,
        ),
    )

    def invalid_payload(_db, *, ai_task):
        raise wr_bridge_module.WRBridgePayloadError("Unsupported task_type for WR bridge: nope")

    monkeypatch.setattr(wr_bridge_module, "run_wr_answers_integrate", invalid_payload)

    result, duplicate = wr.add_user_message(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewAnswerRequest(content="My answer", payload={"signal": "ok"}),
        idempotency_key="wr-answer-n8n-missing-config",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/answer",
        create_integration_task=True,
        trigger_type="user_message",
    )

    ai_task = next(item for item in db.added if isinstance(item, AITask))
    assert duplicate is False
    assert result.content == "My answer"
    assert ai_task.error_code == "wr_bridge_payload_invalid"
    assert "Unsupported task_type" in ai_task.error_message
    assert len([item for item in db.added if isinstance(item, ImperiumWeeklyReviewMessage)]) == 1


def test_answer_flow_same_key_different_payload_conflicts(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="waiting_for_user_answer")
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(
        wr,
        "_get_existing_idempotency",
        lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key),
    )

    wr.add_user_message(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewAnswerRequest(content="My answer", payload={"signal": "ok"}),
        idempotency_key="wr-answer-integrate-conflict",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/answer",
        create_integration_task=True,
        trigger_type="user_message",
    )

    with pytest.raises(wr.WeeklyReviewIdempotencyConflictError, match="different payload"):
        wr.add_user_message(
            db,
            session_id=session.id,
            current_user=current_user,
            payload=WeeklyReviewAnswerRequest(content="Different answer", payload={"signal": "changed"}),
            idempotency_key="wr-answer-integrate-conflict",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/{session.id}/answer",
            create_integration_task=True,
            trigger_type="user_message",
        )

    assert len([item for item in db.added if isinstance(item, ImperiumWeeklyReviewMessage)]) == 1
    assert len([item for item in db.added if isinstance(item, AITask)]) == 1


def test_answer_endpoint_refuses_other_user_session() -> None:
    db = FakeDb()
    current_user = _user()
    other_session = _session(uuid4(), status="waiting_for_user_answer")
    db.objects[(ImperiumWeeklyReviewSession, other_session.id)] = other_session

    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current_user
    client = TestClient(app)

    response = client.post(
        f"/imperium/weekly-review/{other_session.id}/answer",
        json={"content": "This is not mine."},
        headers={"Idempotency-Key": "wr-answer-other-user"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Weekly review session not found."
    assert not any(isinstance(item, ImperiumWeeklyReviewMessage) for item in db.added)
    assert not any(isinstance(item, AITask) for item in db.added)


def test_public_weekly_review_messages_endpoint_rejects_assistant_roles_and_types() -> None:
    db = FakeDb()
    current_user = _user()
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current_user
    client = TestClient(app)
    session_id = uuid4()

    role_response = client.post(
        f"/imperium/weekly-review/{session_id}/messages",
        json={"role": "qwen", "content": "fake assistant"},
        headers={"Idempotency-Key": "wr-public-message-role"},
    )
    type_response = client.post(
        f"/imperium/weekly-review/{session_id}/messages",
        json={"role": "user", "message_type": "initial_summary", "content": "fake summary"},
        headers={"Idempotency-Key": "wr-public-message-type"},
    )

    assert role_response.status_code == 422
    assert type_response.status_code == 422
    assert not any(isinstance(item, ImperiumWeeklyReviewMessage) for item in db.added)


def test_attach_ai_result_updates_session_without_final_report(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="preparing_initial_summary")
    ai_result = _ai_result(current_user.id)
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AIResult, ai_result.id)] = ai_result
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    result, duplicate = wr.attach_ai_result_to_session(
        db,
        session_id=session.id,
        payload=WeeklyReviewAttachAIResultRequest(ai_result_id=ai_result.id),
        idempotency_key="wr-attach-1",
        request_method="POST",
        request_path=f"/api/internal/weekly-review/{session.id}/attach-ai-result",
    )

    assert duplicate is False
    assert result.status == "initial_summary_ready"
    assert session.initial_ai_result_id == ai_result.id
    assert not any(isinstance(item, ImperiumWeeklyReviewFinalReport) for item in db.added)


def test_attach_ai_result_is_idempotent_for_existing_initial_summary(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="initial_summary_ready")
    ai_result = _ai_result(current_user.id)
    session.initial_ai_result_id = ai_result.id
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AIResult, ai_result.id)] = ai_result
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    result, duplicate = wr.attach_ai_result_to_session(
        db,
        session_id=session.id,
        payload=WeeklyReviewAttachAIResultRequest(ai_result_id=ai_result.id),
        idempotency_key="wr-attach-same-summary",
        request_method="POST",
        request_path=f"/api/internal/weekly-review/{session.id}/attach-ai-result",
    )

    assert duplicate is False
    assert result.initial_ai_result_id == ai_result.id
    assert result.status == "initial_summary_ready"
    assert not any(isinstance(item, ImperiumWeeklyReviewMessage) for item in db.added)


def test_attach_ai_result_refuses_replacing_existing_initial_summary(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="initial_summary_ready")
    first_result_id = uuid4()
    second_result = _ai_result(current_user.id)
    session.initial_ai_result_id = first_result_id
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AIResult, second_result.id)] = second_result
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    with pytest.raises(wr.WeeklyReviewAIResultConflictError, match="initial summary is already attached"):
        wr.attach_ai_result_to_session(
            db,
            session_id=session.id,
            payload=WeeklyReviewAttachAIResultRequest(ai_result_id=second_result.id),
            idempotency_key="wr-attach-replace-summary",
            request_method="POST",
            request_path=f"/api/internal/weekly-review/{session.id}/attach-ai-result",
        )

    assert session.initial_ai_result_id == first_result_id
    assert not any(isinstance(item, ImperiumWeeklyReviewMessage) for item in db.added)


def test_attach_weekly_report_draft_creates_draft_candidate(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="integrating_answers")
    ai_result = _ai_result(current_user.id, result_type="weekly_report.draft")
    ai_result.result_payload = {
        "report_payload": {"summary": "Draft candidate"},
        "report_markdown": "# Draft candidate",
        "memory_candidates": [{"candidate": "later"}],
    }
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AIResult, ai_result.id)] = ai_result
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    result, duplicate = wr.attach_ai_result_to_session(
        db,
        session_id=session.id,
        payload=WeeklyReviewAttachAIResultRequest(ai_result_id=ai_result.id),
        idempotency_key="wr-attach-draft-candidate",
        request_method="POST",
        request_path=f"/api/internal/weekly-review/{session.id}/attach-ai-result",
    )

    reports = [item for item in db.added if isinstance(item, ImperiumWeeklyReviewFinalReport)]
    messages = [item for item in db.added if isinstance(item, ImperiumWeeklyReviewMessage)]
    assert duplicate is False
    assert result.status == "draft_ready"
    assert len(reports) == 1
    assert reports[0].status == "draft"
    assert reports[0].source_ai_result_id == ai_result.id
    assert reports[0].report_payload == {"summary": "Draft candidate"}
    assert reports[0].report_markdown == "# Draft candidate"
    assert reports[0].memory_candidates == [{"candidate": "later"}]
    assert reports[0].approved_at is None
    assert reports[0].stored_at is None
    assert len(messages) == 1
    assert messages[0].message_type == "draft"
    assert messages[0].ai_result_id == ai_result.id
    assert session.final_ai_result_id is None
    assert not any("Memory" in type(item).__name__ for item in db.added)


def test_attach_weekly_report_final_creates_unapproved_final_candidate(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="integrating_answers")
    ai_result = _ai_result(current_user.id, result_type="weekly_report.final")
    ai_result.result_payload = {
        "summary": "Final candidate",
        "markdown": "# Final candidate",
    }
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AIResult, ai_result.id)] = ai_result
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    result, duplicate = wr.attach_ai_result_to_session(
        db,
        session_id=session.id,
        payload=WeeklyReviewAttachAIResultRequest(ai_result_id=ai_result.id),
        idempotency_key="wr-attach-final-candidate",
        request_method="POST",
        request_path=f"/api/internal/weekly-review/{session.id}/attach-ai-result",
    )

    report = next(item for item in db.added if isinstance(item, ImperiumWeeklyReviewFinalReport))
    message = next(item for item in db.added if isinstance(item, ImperiumWeeklyReviewMessage))
    assert duplicate is False
    assert result.status == "final_ready"
    assert session.final_ai_result_id == ai_result.id
    assert report.status == "draft"
    assert report.approved_at is None
    assert report.stored_at is None
    assert message.message_type == "final_report"
    assert message.content == "# Final candidate"


def test_reattach_same_final_result_is_safe_without_duplicate_message(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="integrating_answers")
    ai_result = _ai_result(current_user.id, result_type="weekly_report.final")
    ai_result.result_payload = {"report_markdown": "# Final candidate"}
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AIResult, ai_result.id)] = ai_result
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    wr.attach_ai_result_to_session(
        db,
        session_id=session.id,
        payload=WeeklyReviewAttachAIResultRequest(ai_result_id=ai_result.id),
        idempotency_key="wr-attach-final-first",
        request_method="POST",
        request_path=f"/api/internal/weekly-review/{session.id}/attach-ai-result",
    )
    report = next(item for item in db.added if isinstance(item, ImperiumWeeklyReviewFinalReport))
    db.scalars_results = [[report]]
    result, duplicate = wr.attach_ai_result_to_session(
        db,
        session_id=session.id,
        payload=WeeklyReviewAttachAIResultRequest(ai_result_id=ai_result.id),
        idempotency_key="wr-attach-final-second",
        request_method="POST",
        request_path=f"/api/internal/weekly-review/{session.id}/attach-ai-result",
    )

    assert duplicate is False
    assert result.status == "final_ready"
    assert len([item for item in db.added if isinstance(item, ImperiumWeeklyReviewFinalReport)]) == 1
    assert len([item for item in db.added if isinstance(item, ImperiumWeeklyReviewMessage)]) == 1


def test_attach_different_final_candidate_conflicts(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="final_ready")
    existing_report = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="draft",
        report_payload={"summary": "existing"},
        report_markdown="# Existing",
        source_ai_result_id=uuid4(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    new_result = _ai_result(current_user.id, result_type="weekly_report.final")
    new_result.result_payload = {"report_markdown": "# Replacement"}
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AIResult, new_result.id)] = new_result
    db.scalars_results = [[existing_report]]
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    with pytest.raises(wr.WeeklyReviewAIResultConflictError, match="final candidate is already attached"):
        wr.attach_ai_result_to_session(
            db,
            session_id=session.id,
            payload=WeeklyReviewAttachAIResultRequest(ai_result_id=new_result.id),
            idempotency_key="wr-attach-final-replacement",
            request_method="POST",
            request_path=f"/api/internal/weekly-review/{session.id}/attach-ai-result",
        )

    assert not any(isinstance(item, ImperiumWeeklyReviewMessage) for item in db.added)
    assert not any(isinstance(item, ImperiumWeeklyReviewFinalReport) for item in db.added)


def test_attach_revised_draft_after_reject_creates_second_candidate_row(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="integrating_answers")
    first_result = _ai_result(current_user.id, result_type="weekly_report.draft")
    first_result.result_payload = {"report_markdown": "# Draft 1"}
    second_result = _ai_result(current_user.id, result_type="weekly_report.draft")
    second_result.result_payload = {"report_markdown": "# Draft 2"}
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AIResult, first_result.id)] = first_result
    db.objects[(AIResult, second_result.id)] = second_result
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    wr.attach_ai_result_to_session(
        db,
        session_id=session.id,
        payload=WeeklyReviewAttachAIResultRequest(ai_result_id=first_result.id),
        idempotency_key="wr-attach-draft-1",
        request_method="POST",
        request_path=f"/api/internal/weekly-review/{session.id}/attach-ai-result",
    )
    first_report = next(item for item in db.added if isinstance(item, ImperiumWeeklyReviewFinalReport))
    db.scalar_results = [first_report]
    wr.reject_latest_draft_report(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewDraftRejectRequest(reason="Revise"),
        idempotency_key="wr-reject-draft-1",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/draft/reject",
    )
    db.scalars_results = [[first_report]]
    result, duplicate = wr.attach_ai_result_to_session(
        db,
        session_id=session.id,
        payload=WeeklyReviewAttachAIResultRequest(ai_result_id=second_result.id),
        idempotency_key="wr-attach-draft-2",
        request_method="POST",
        request_path=f"/api/internal/weekly-review/{session.id}/attach-ai-result",
    )

    reports = [item for item in db.added if isinstance(item, ImperiumWeeklyReviewFinalReport)]
    second_report = reports[-1]
    assert duplicate is False
    assert result.status == "draft_ready"
    assert session.status == "draft_ready"
    assert len(reports) == 2
    assert first_report.status == "superseded"
    assert second_report.status == "draft"
    assert second_report.source_ai_result_id == second_result.id
    assert second_report.approved_at is None
    assert second_report.stored_at is None
    assert not any("Memory" in type(item).__name__ for item in db.added)


def test_attach_revised_draft_conflicts_when_active_draft_exists(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    first_result = _ai_result(current_user.id, result_type="weekly_report.draft")
    second_result = _ai_result(current_user.id, result_type="weekly_report.draft")
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AIResult, first_result.id)] = first_result
    db.objects[(AIResult, second_result.id)] = second_result
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    wr.attach_ai_result_to_session(
        db,
        session_id=session.id,
        payload=WeeklyReviewAttachAIResultRequest(ai_result_id=first_result.id),
        idempotency_key="wr-attach-active-draft-1",
        request_method="POST",
        request_path=f"/api/internal/weekly-review/{session.id}/attach-ai-result",
    )
    first_report = next(item for item in db.added if isinstance(item, ImperiumWeeklyReviewFinalReport))
    db.scalars_results = [[first_report]]

    with pytest.raises(wr.WeeklyReviewAIResultConflictError, match="final candidate is already attached"):
        wr.attach_ai_result_to_session(
            db,
            session_id=session.id,
            payload=WeeklyReviewAttachAIResultRequest(ai_result_id=second_result.id),
            idempotency_key="wr-attach-active-draft-2",
            request_method="POST",
            request_path=f"/api/internal/weekly-review/{session.id}/attach-ai-result",
        )

    assert len([item for item in db.added if isinstance(item, ImperiumWeeklyReviewFinalReport)]) == 1


def test_attach_same_draft_is_idempotent(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="integrating_answers")
    first_result = _ai_result(current_user.id, result_type="weekly_report.draft")
    second_result = _ai_result(current_user.id, result_type="weekly_report.draft")
    second_result.result_payload = {"report_markdown": "# Draft 2"}
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AIResult, first_result.id)] = first_result
    db.objects[(AIResult, second_result.id)] = second_result
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    wr.attach_ai_result_to_session(
        db,
        session_id=session.id,
        payload=WeeklyReviewAttachAIResultRequest(ai_result_id=first_result.id),
        idempotency_key="wr-idempotent-draft-1",
        request_method="POST",
        request_path=f"/api/internal/weekly-review/{session.id}/attach-ai-result",
    )
    first_report = next(item for item in db.added if isinstance(item, ImperiumWeeklyReviewFinalReport))
    db.scalar_results = [first_report]
    wr.reject_latest_draft_report(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewDraftRejectRequest(reason="Revise"),
        idempotency_key="wr-idempotent-draft-reject",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/draft/reject",
    )
    db.scalars_results = [[first_report]]
    wr.attach_ai_result_to_session(
        db,
        session_id=session.id,
        payload=WeeklyReviewAttachAIResultRequest(ai_result_id=second_result.id),
        idempotency_key="wr-idempotent-draft-2",
        request_method="POST",
        request_path=f"/api/internal/weekly-review/{session.id}/attach-ai-result",
    )
    second_report = [item for item in db.added if isinstance(item, ImperiumWeeklyReviewFinalReport)][-1]
    db.scalars_results = [[second_report, first_report]]
    wr.attach_ai_result_to_session(
        db,
        session_id=session.id,
        payload=WeeklyReviewAttachAIResultRequest(ai_result_id=second_result.id),
        idempotency_key="wr-idempotent-draft-2-again",
        request_method="POST",
        request_path=f"/api/internal/weekly-review/{session.id}/attach-ai-result",
    )

    assert len([item for item in db.added if isinstance(item, ImperiumWeeklyReviewFinalReport)]) == 2
    assert len([item for item in db.added if isinstance(item, ImperiumWeeklyReviewMessage)]) == 3


def test_attach_revised_draft_after_multiple_rejections_creates_history(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="integrating_answers")
    results = [_ai_result(current_user.id, result_type="weekly_report.draft") for _ in range(3)]
    for index, ai_result in enumerate(results, start=1):
        ai_result.result_payload = {"report_markdown": f"# Draft {index}"}
        db.objects[(AIResult, ai_result.id)] = ai_result
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    wr.attach_ai_result_to_session(
        db,
        session_id=session.id,
        payload=WeeklyReviewAttachAIResultRequest(ai_result_id=results[0].id),
        idempotency_key="wr-history-draft-1",
        request_method="POST",
        request_path=f"/api/internal/weekly-review/{session.id}/attach-ai-result",
    )
    first_report = [item for item in db.added if isinstance(item, ImperiumWeeklyReviewFinalReport)][-1]
    db.scalar_results = [first_report]
    wr.reject_latest_draft_report(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewDraftRejectRequest(reason="Revise 1"),
        idempotency_key="wr-history-reject-1",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/draft/reject",
    )
    db.scalars_results = [[first_report]]
    wr.attach_ai_result_to_session(
        db,
        session_id=session.id,
        payload=WeeklyReviewAttachAIResultRequest(ai_result_id=results[1].id),
        idempotency_key="wr-history-draft-2",
        request_method="POST",
        request_path=f"/api/internal/weekly-review/{session.id}/attach-ai-result",
    )
    second_report = [item for item in db.added if isinstance(item, ImperiumWeeklyReviewFinalReport)][-1]
    db.scalar_results = [second_report]
    wr.reject_latest_draft_report(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewDraftRejectRequest(reason="Revise 2"),
        idempotency_key="wr-history-reject-2",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/draft/reject",
    )
    db.scalars_results = [[second_report, first_report]]
    wr.attach_ai_result_to_session(
        db,
        session_id=session.id,
        payload=WeeklyReviewAttachAIResultRequest(ai_result_id=results[2].id),
        idempotency_key="wr-history-draft-3",
        request_method="POST",
        request_path=f"/api/internal/weekly-review/{session.id}/attach-ai-result",
    )

    reports = [item for item in db.added if isinstance(item, ImperiumWeeklyReviewFinalReport)]
    assert len(reports) == 3
    assert [report.status for report in reports].count("superseded") == 2
    assert reports[-1].status == "draft"
    assert reports[-1].source_ai_result_id == results[2].id


def test_attach_final_candidate_requires_explicit_approve(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="integrating_answers")
    ai_result = _ai_result(current_user.id, result_type="weekly_report.final")
    ai_result.result_payload = {"report_markdown": "# Final candidate"}
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AIResult, ai_result.id)] = ai_result
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    wr.attach_ai_result_to_session(
        db,
        session_id=session.id,
        payload=WeeklyReviewAttachAIResultRequest(ai_result_id=ai_result.id),
        idempotency_key="wr-attach-final-before-approve",
        request_method="POST",
        request_path=f"/api/internal/weekly-review/{session.id}/attach-ai-result",
    )
    report = next(item for item in db.added if isinstance(item, ImperiumWeeklyReviewFinalReport))

    assert report.status == "draft"
    assert session.status == "final_ready"

    approved, _duplicate = wr.approve_final_report(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewFinalApproveRequest(final_report_id=report.id),
        idempotency_key="wr-approve-attached-final",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/approve",
    )

    assert approved.status == "approved"
    assert session.status == "approved"


def test_get_conversation_empty_launched_session_returns_valid_shape() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="launched")
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session

    result = wr.get_weekly_review_conversation(db, current_user=current_user, session_id=session.id)

    assert result.session.id == session.id
    assert result.messages == []
    assert result.current_ai_task is None
    assert result.initial_ai_result is None
    assert result.final_ai_result is None
    assert result.final_reports == []
    assert result.latest_final_report is None
    assert result.flags.has_initial_summary is False
    assert result.flags.has_final_draft is False
    assert result.flags.can_approve is False
    assert result.final_report_candidates == []
    assert result.ui_state == "preparing_initial_summary"
    assert result.allowed_actions == []


def test_get_conversation_default_messages_limit_returns_at_most_200() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="initial_summary_ready")
    start = datetime(2026, 4, 28, 8, 0, tzinfo=UTC)
    messages = [
        _message(session, created_at=start + timedelta(minutes=index), content=f"Message {index}")
        for index in range(250)
    ]
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.scalars_results = [messages, []]

    result = wr.get_weekly_review_conversation(db, current_user=current_user, session_id=session.id)

    assert len(result.messages) == 200
    assert [message.content for message in result.messages[:2]] == ["Message 50", "Message 51"]
    assert result.messages[-1].content == "Message 249"


def test_get_conversation_custom_messages_limit_and_before_filter() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="initial_summary_ready")
    start = datetime(2026, 4, 28, 8, 0, tzinfo=UTC)
    messages = [
        _message(session, created_at=start + timedelta(minutes=index), content=f"Message {index}")
        for index in range(10)
    ]
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.scalars_results = [messages, []]

    result = wr.get_weekly_review_conversation(
        db,
        current_user=current_user,
        session_id=session.id,
        messages_limit=3,
        messages_before=start + timedelta(minutes=8),
    )

    assert [message.content for message in result.messages] == ["Message 5", "Message 6", "Message 7"]


def test_get_conversation_with_initial_summary_returns_message_and_ai_result_ordered() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="initial_summary_ready")
    ai_task = _ai_task(current_user.id)
    ai_result = _ai_result(current_user.id, task_id=ai_task.id)
    older = ImperiumWeeklyReviewMessage(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        role="qwen",
        message_type="initial_summary",
        content=None,
        payload={"summary": "First"},
        ai_result_id=ai_result.id,
        created_at=datetime(2026, 4, 28, 8, 0, tzinfo=UTC),
    )
    newer = ImperiumWeeklyReviewMessage(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        role="user",
        message_type="user_answer",
        content="Answer",
        payload=None,
        created_at=datetime(2026, 4, 28, 9, 0, tzinfo=UTC),
    )
    session.current_ai_task_id = ai_task.id
    session.initial_ai_result_id = ai_result.id
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AITask, ai_task.id)] = ai_task
    db.objects[(AIResult, ai_result.id)] = ai_result
    db.scalars_results = [[older, newer], []]

    result = wr.get_weekly_review_conversation(db, current_user=current_user, session_id=session.id)

    assert result.current_ai_task is not None
    assert result.initial_ai_result is not None
    assert result.initial_ai_result.id == ai_result.id
    assert [message.id for message in result.messages] == [older.id, newer.id]
    assert result.flags.has_initial_summary is True
    assert result.flags.can_answer is True
    assert result.flags.can_send_message is True
    assert result.flags.can_confirm_no_more_input is True
    assert result.ui_state == "conversation_active"
    assert result.allowed_actions == ["send_message", "confirm_no_more_input"]
    assert [item.type for item in result.chat_timeline] == ["initial_summary", "user_message"]
    assert result.visible_ai_state is not None
    assert result.visible_ai_state.current_step == "collecting_user_context"
    assert result.primary_action is not None
    assert result.primary_action.action == "send_message"
    assert {action.action for action in result.secondary_actions} == {"confirm_no_more_input"}


def test_get_conversation_trims_initial_ai_result_raw_payload() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="initial_summary_ready")
    ai_task = _ai_task(current_user.id)
    ai_result = _ai_result(current_user.id, task_id=ai_task.id)
    ai_result.raw_payload = {"secret_prompt": "DO_NOT_EXPOSE"}
    session.current_ai_task_id = ai_task.id
    session.initial_ai_result_id = ai_result.id
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AITask, ai_task.id)] = ai_task
    db.objects[(AIResult, ai_result.id)] = ai_result
    db.scalars_results = [[], []]

    result = wr.get_weekly_review_conversation(db, current_user=current_user, session_id=session.id)
    response_json = result.model_dump_json()

    assert result.initial_ai_result is not None
    assert "raw_payload" not in result.initial_ai_result.model_dump()
    assert '"raw_payload":' not in response_json
    assert "DO_NOT_EXPOSE" not in response_json


def test_get_conversation_includes_final_draft_and_flags() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="final_ready")
    report = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="draft",
        report_payload={"summary": "final draft"},
        report_markdown="# Final draft",
        memory_candidates=[],
        created_at=datetime(2026, 4, 29, 8, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 29, 8, 0, tzinfo=UTC),
    )
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.scalars_results = [[], [report]]

    result = wr.get_weekly_review_conversation(db, current_user=current_user, session_id=session.id)

    assert len(result.final_reports) == 1
    assert result.latest_final_report is not None
    assert result.latest_final_report.id == report.id
    assert result.flags.has_final_draft is True
    assert result.flags.can_request_revision is True
    assert result.flags.can_approve is True
    assert len(result.final_report_candidates) == 1
    assert result.ui_state == "draft_ready"
    assert result.allowed_actions == ["approve_draft", "request_changes"]
    assert result.draft_review_state is not None
    assert result.draft_review_state.has_draft is True
    assert result.draft_review_state.active_draft_id == report.id
    assert result.primary_action is not None
    assert result.primary_action.action == "approve_draft"
    assert {action.action for action in result.secondary_actions} == {"request_changes", "reject_draft"}


def test_draft_ready_read_model_uses_active_draft_for_actions() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    report = _final_report(session, status="draft", summary="Ready draft", markdown="# Ready draft")
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.scalars_results = [[], [report]]

    result = wr.get_weekly_review_conversation(db, current_user=current_user, session_id=session.id)

    assert result.ui_state == "draft_ready"
    assert result.draft_review_state is not None
    assert result.draft_review_state.has_draft is True
    assert result.draft_review_state.active_draft_id == report.id
    assert result.draft_review_state.active_draft_status == "draft"
    assert result.draft_review_state.can_approve is True
    assert result.draft_review_state.can_request_changes is True
    assert result.draft_review_state.can_store is False
    assert result.primary_action is not None
    assert result.primary_action.action == "approve_draft"
    enabled_actions = {action.action for action in [result.primary_action, *result.secondary_actions] if action.enabled}
    assert "request_changes" in enabled_actions
    assert "send_message" not in enabled_actions
    assert "confirm_no_more_input" not in enabled_actions


@pytest.mark.parametrize(
    ("session_status", "expected_ui_state", "expected_allowed_actions"),
    [
        ("integrating_answers", "preparing_initial_summary", []),
        ("waiting_for_user_answer", "conversation_active", ["send_message", "confirm_no_more_input"]),
        ("approved", "approved", []),
        ("failed", "failed", []),
    ],
)
def test_get_conversation_ui_state_and_allowed_actions(
    session_status: str,
    expected_ui_state: str,
    expected_allowed_actions: list[str],
) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status=session_status)
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.scalars_results = [[], []]

    result = wr.get_weekly_review_conversation(db, current_user=current_user, session_id=session.id)

    assert result.ui_state == expected_ui_state
    assert result.allowed_actions == expected_allowed_actions


def test_get_conversation_allowed_actions_after_approve_and_store() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="approved")
    report = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="approved",
        report_payload={"summary": "approved"},
        report_markdown="# Approved",
        approved_at=datetime.now(UTC),
        stored_at=None,
        created_at=datetime(2026, 4, 29, 9, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 29, 9, 0, tzinfo=UTC),
    )
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.scalars_results = [[], [report]]

    approved = wr.get_weekly_review_conversation(db, current_user=current_user, session_id=session.id)

    assert approved.ui_state == "approved"
    assert approved.allowed_actions == ["store_final_report", "request_changes"]
    assert approved.visible_ai_state is not None
    assert approved.visible_ai_state.current_step == "ready_to_store"
    assert approved.primary_action is not None
    assert approved.primary_action.action == "store_final_report"
    assert {action.action for action in approved.secondary_actions} == {"request_changes"}
    assert approved.draft_review_state is not None
    assert approved.draft_review_state.has_draft is True
    assert approved.draft_review_state.active_draft_id == report.id
    assert approved.draft_review_state.active_draft_status == "approved"
    assert approved.draft_review_state.can_store is True
    assert approved.flags.can_store is True
    assert approved.flags.can_approve is False

    session.status = "stored"
    report.status = "stored"
    report.stored_at = datetime.now(UTC)
    db.scalars_results = [[], [report]]

    stored = wr.get_weekly_review_conversation(db, current_user=current_user, session_id=session.id)

    assert stored.ui_state == "stored"
    assert stored.allowed_actions == []
    assert stored.primary_action is None
    assert stored.secondary_actions == []
    assert stored.visible_ai_state is not None
    assert stored.visible_ai_state.current_step == "closed"
    assert stored.draft_review_state is not None
    assert stored.draft_review_state.has_draft is True
    assert stored.draft_review_state.active_draft_id is None
    assert stored.draft_review_state.latest_draft_summary == "approved"
    assert stored.draft_review_state.can_approve is False
    assert stored.draft_review_state.can_request_changes is False
    assert stored.draft_review_state.can_store is False
    assert stored.flags.can_store is False
    assert stored.flags.is_closed is True


def test_conversation_active_read_model_has_chat_actions_only() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="conversation_active")
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.scalars_results = [[], []]

    result = wr.get_weekly_review_conversation(db, current_user=current_user, session_id=session.id)

    assert result.ui_state == "conversation_active"
    assert result.allowed_actions == ["send_message", "confirm_no_more_input"]
    assert result.primary_action is not None
    assert result.primary_action.action == "send_message"
    assert {action.action for action in result.secondary_actions} == {"confirm_no_more_input"}
    assert result.flags.can_send_message is True
    assert result.flags.can_confirm_no_more_input is True
    assert result.flags.can_approve is False
    assert result.flags.can_store is False


def test_get_conversation_final_reports_limit_defaults_to_5_and_customizes() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="final_ready")
    start = datetime(2026, 4, 29, 8, 0, tzinfo=UTC)
    reports = [
        ImperiumWeeklyReviewFinalReport(
            id=uuid4(),
            session_id=session.id,
            user_id=current_user.id,
            week_start=session.week_start,
            week_end=session.week_end,
            status="draft",
            report_payload={"summary": f"draft {index}"},
            report_markdown=f"# Draft {index}",
            memory_candidates=[],
            created_at=start + timedelta(minutes=index),
            updated_at=start + timedelta(minutes=index),
        )
        for index in range(8)
    ]
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.scalars_results = [[], reports]

    default_result = wr.get_weekly_review_conversation(db, current_user=current_user, session_id=session.id)

    assert len(default_result.final_reports) == 5
    assert [report.report_payload["summary"] for report in default_result.final_reports] == [
        "draft 7",
        "draft 6",
        "draft 5",
        "draft 4",
        "draft 3",
    ]

    db.scalars_results = [[], reports]
    custom_result = wr.get_weekly_review_conversation(
        db,
        current_user=current_user,
        session_id=session.id,
        final_reports_limit=2,
    )

    assert [report.report_payload["summary"] for report in custom_result.final_reports] == ["draft 7", "draft 6"]


def test_conversation_final_report_candidates_returns_history_newest_first() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    older = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="superseded",
        report_payload={"summary": "old"},
        report_markdown="# Old",
        created_at=datetime(2026, 4, 29, 8, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 29, 8, 0, tzinfo=UTC),
    )
    newer = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="draft",
        report_payload={"summary": "new"},
        report_markdown="# New",
        created_at=datetime(2026, 4, 29, 9, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 29, 9, 0, tzinfo=UTC),
    )
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.scalars_results = [[], [older, newer]]

    result = wr.get_weekly_review_conversation(db, current_user=current_user, session_id=session.id)

    assert [candidate.status for candidate in result.final_report_candidates] == ["draft", "superseded"]
    assert [candidate.report_payload["summary"] for candidate in result.final_report_candidates] == ["new", "old"]
    assert result.allowed_actions == ["approve_draft", "request_changes"]


def test_allowed_actions_empty_when_no_active_draft() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    superseded = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="superseded",
        report_payload={"summary": "old"},
        report_markdown="# Old",
        created_at=datetime(2026, 4, 29, 9, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 29, 9, 0, tzinfo=UTC),
    )
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.scalars_results = [[], [superseded]]

    result = wr.get_weekly_review_conversation(db, current_user=current_user, session_id=session.id)

    assert result.ui_state != "draft_ready"
    assert result.ui_state == "preparing_initial_summary"
    assert result.allowed_actions == []
    assert result.flags.can_approve is False
    assert result.draft_review_state is not None
    assert result.draft_review_state.has_draft is False
    assert result.draft_review_state.active_draft_id is None
    assert result.draft_review_state.can_request_changes is False


def test_get_conversation_trims_final_ai_result_raw_payload() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="final_ready")
    final_ai_result = _ai_result(current_user.id, result_type="weekly_report.final")
    final_ai_result.raw_payload = {"secret_prompt": "DO_NOT_EXPOSE"}
    session.final_ai_result_id = final_ai_result.id
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AIResult, final_ai_result.id)] = final_ai_result
    db.scalars_results = [[], []]

    result = wr.get_weekly_review_conversation(db, current_user=current_user, session_id=session.id)
    response_json = result.model_dump_json()

    assert result.final_ai_result is not None
    assert "raw_payload" not in result.final_ai_result.model_dump()
    assert '"raw_payload":' not in response_json
    assert "DO_NOT_EXPOSE" not in response_json


def test_conversation_endpoint_requires_auth() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.get(f"/imperium/weekly-review/{uuid4()}/conversation")

    assert response.status_code == 401


def test_conversation_endpoint_refuses_other_user_session() -> None:
    db = FakeDb()
    current_user = _user()
    other_session = _session(uuid4(), status="launched")
    db.objects[(ImperiumWeeklyReviewSession, other_session.id)] = other_session

    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current_user
    client = TestClient(app)

    response = client.get(f"/imperium/weekly-review/{other_session.id}/conversation")

    assert response.status_code == 404
    assert response.json()["detail"] == "Weekly review session not found."


def test_conversation_endpoint_rejects_messages_limit_above_500() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="launched")
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session

    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current_user
    client = TestClient(app)

    response = client.get(f"/imperium/weekly-review/{session.id}/conversation?messages_limit=501")

    assert response.status_code == 422


def test_current_weekly_review_endpoint_requires_auth() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.get("/imperium/weekly-review/current")

    assert response.status_code == 401


def test_get_current_weekly_review_returns_null_when_missing() -> None:
    db = FakeDb()
    current_user = _user()

    result = wr.get_current_weekly_review(db, current_user=current_user)

    assert result.session is None
    assert result.conversation is None


def test_get_current_weekly_review_returns_latest_session() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="initial_summary_ready")
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.scalar_results = [session]
    db.scalars_results = [[], []]

    result = wr.get_current_weekly_review(db, current_user=current_user)

    assert result.session is not None
    assert result.session.id == session.id
    assert result.conversation is not None
    assert result.conversation.session.id == session.id


def test_get_current_weekly_review_returns_requested_week_start() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="waiting_for_user_answer")
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.scalar_results = [session]
    db.scalars_results = [[], []]

    result = wr.get_current_weekly_review(db, current_user=current_user, week_start=session.week_start)

    assert result.session is not None
    assert result.session.week_start == session.week_start
    assert result.conversation is not None
    assert result.conversation.ui_state == "conversation_active"


def test_get_current_weekly_review_refuses_other_user_session() -> None:
    db = FakeDb()
    current_user = _user()
    other_session = _session(uuid4(), status="initial_summary_ready")
    db.scalar_results = [other_session]

    result = wr.get_current_weekly_review(db, current_user=current_user)

    assert result.session is None
    assert result.conversation is None


def test_history_endpoint_requires_auth() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.get("/imperium/weekly-review/history")

    assert response.status_code == 401


def test_history_endpoint_returns_only_current_user_sessions_and_counts() -> None:
    db = FakeDb()
    current_user = _user()
    current_session = _session(current_user.id, status="stored")
    current_session.initial_ai_result_id = uuid4()
    other_session = _session(uuid4(), status="stored")
    stored_report = _final_report(current_session, status="stored", summary="Stored")
    superseded_report = _final_report(
        current_session,
        status="superseded",
        summary="Old",
        created_at=datetime(2026, 4, 29, 8, 0, tzinfo=UTC),
    )
    db.scalars_results = [[current_session, other_session], [stored_report, superseded_report]]

    result = wr.get_weekly_review_history(db, current_user=current_user)
    response_json = result.model_dump_json()

    assert result.count == 1
    assert result.items[0].session_id == current_session.id
    assert result.items[0].latest_final_report is not None
    assert result.items[0].latest_final_report.status == "stored"
    assert result.items[0].has_initial_summary is True
    assert result.items[0].has_active_or_stored_report is True
    assert result.items[0].has_stored_report is True
    assert result.items[0].has_superseded_reports is True
    assert result.items[0].final_reports_count == 2
    assert result.items[0].active_reports_count == 0
    assert result.items[0].stored_reports_count == 1
    assert result.items[0].superseded_reports_count == 1
    assert '"raw_payload":' not in response_json


def test_history_endpoint_supports_limit_offset_and_stored_only() -> None:
    db = FakeDb()
    current_user = _user()
    draft_session = _session(current_user.id, status="draft_ready")
    stored_session = _session(current_user.id, status="stored")
    draft_report = _final_report(draft_session, status="draft", summary="Draft")
    stored_report = _final_report(stored_session, status="stored", summary="Stored")
    db.scalars_results = [[draft_session, stored_session], [draft_report], [stored_report]]

    result = wr.get_weekly_review_history(
        db,
        current_user=current_user,
        limit=1,
        offset=3,
        stored_only=True,
    )

    assert result.limit == 1
    assert result.offset == 3
    assert result.count == 1
    assert result.has_more is True
    assert result.items[0].session_id == stored_session.id


def test_history_item_counts_draft_only() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    draft_report = _final_report(session, status="draft", summary="Draft")
    db.scalars_results = [[session], [draft_report]]

    result = wr.get_weekly_review_history(db, current_user=current_user)

    assert result.count == 1
    item = result.items[0]
    assert item.final_reports_count == 1
    assert item.active_reports_count == 1
    assert item.stored_reports_count == 0
    assert item.superseded_reports_count == 0
    assert item.has_active_or_stored_report is True
    assert item.has_stored_report is False
    assert item.has_superseded_reports is False


def test_final_report_endpoint_requires_auth() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.get(f"/imperium/weekly-review/{uuid4()}/final-report")

    assert response.status_code == 401


def test_final_report_endpoint_returns_404_for_foreign_session() -> None:
    db = FakeDb()
    current_user = _user()
    other_session = _session(uuid4(), status="stored")
    db.objects[(ImperiumWeeklyReviewSession, other_session.id)] = other_session
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current_user
    client = TestClient(app)

    response = client.get(f"/imperium/weekly-review/{other_session.id}/final-report")

    assert response.status_code == 404


def test_final_report_endpoint_returns_latest_report_by_status_priority() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    superseded = _final_report(session, status="superseded", summary="Old", created_at=datetime(2026, 4, 29, 12, 0, tzinfo=UTC))
    draft = _final_report(session, status="draft", summary="Draft", created_at=datetime(2026, 4, 29, 13, 0, tzinfo=UTC))
    approved = _final_report(session, status="approved", summary="Approved", created_at=datetime(2026, 4, 29, 14, 0, tzinfo=UTC))
    stored = _final_report(session, status="stored", summary="Stored", created_at=datetime(2026, 4, 29, 10, 0, tzinfo=UTC))
    stored.report_payload["raw_payload"] = {"secret_prompt": "DO_NOT_EXPOSE"}
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.scalars_results = [[superseded, draft, approved, stored]]

    result = wr.get_weekly_review_final_report(db, current_user=current_user, session_id=session.id)
    response_json = result.model_dump_json()

    assert result.id == stored.id
    assert result.status == "stored"
    assert "raw_payload" not in result.report_payload
    assert "DO_NOT_EXPOSE" not in response_json


def test_final_report_endpoint_returns_404_if_no_report_exists() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="initial_summary_ready")
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.scalars_results = [[]]

    with pytest.raises(wr.WeeklyReviewFinalReportNotFoundError):
        wr.get_weekly_review_final_report(db, current_user=current_user, session_id=session.id)


def test_final_report_markdown_endpoint_requires_auth() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.get(f"/imperium/weekly-review/{uuid4()}/final-report/markdown")

    assert response.status_code == 401


def test_final_report_markdown_endpoint_returns_404_for_foreign_session() -> None:
    db = FakeDb()
    current_user = _user()
    other_session = _session(uuid4(), status="stored")
    db.objects[(ImperiumWeeklyReviewSession, other_session.id)] = other_session
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current_user
    client = TestClient(app)

    response = client.get(f"/imperium/weekly-review/{other_session.id}/final-report/markdown")

    assert response.status_code == 404


def test_final_report_markdown_endpoint_returns_stored_report_markdown() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    report = _final_report(session, status="stored", markdown="# Stored WR\n\nDone.")
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.scalars_results = [[report]]
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current_user
    client = TestClient(app)

    response = client.get(f"/imperium/weekly-review/{session.id}/final-report/markdown")

    assert response.status_code == 200
    assert response.text == "# Stored WR\n\nDone."
    assert response.headers["content-type"].startswith("text/markdown")


def test_final_report_markdown_generates_fallback_from_payload_without_raw_payload() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="approved")
    report = _final_report(session, status="approved", markdown=" ")
    report.report_payload = {
        "title": "Weekly Truth",
        "summary": "Hard but useful.",
        "sections": [{"title": "Execution", "content": "Three wins."}],
        "questions_answered": [{"question": "What blocked you?", "answer": "Fatigue"}],
        "raw_payload": {"secret_prompt": "DO_NOT_EXPOSE"},
    }
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.scalars_results = [[report]]

    markdown = wr.get_weekly_review_final_report_markdown(db, current_user=current_user, session_id=session.id)

    assert "# Weekly Truth" in markdown
    assert "Hard but useful." in markdown
    assert "### Execution" in markdown
    assert "What blocked you?" in markdown
    assert "raw_payload" not in markdown
    assert "DO_NOT_EXPOSE" not in markdown


def test_memory_candidates_endpoint_requires_auth() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.get(f"/imperium/weekly-review/{uuid4()}/memory-candidates")

    assert response.status_code == 401


def test_memory_candidates_foreign_session_and_report_return_404() -> None:
    db = FakeDb()
    current_user = _user()
    other_session = _session(uuid4(), status="stored")
    other_report = _final_report(other_session, status="stored")
    db.objects[(ImperiumWeeklyReviewSession, other_session.id)] = other_session
    db.objects[(ImperiumWeeklyReviewFinalReport, other_report.id)] = other_report
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current_user
    client = TestClient(app)

    session_response = client.get(f"/imperium/weekly-review/{other_session.id}/memory-candidates")
    report_response = client.get(f"/imperium/weekly-review/final-reports/{other_report.id}/memory-candidates")

    assert session_response.status_code == 404
    assert report_response.status_code == 404


def test_stored_report_memory_candidates_are_read_only_and_deterministic() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    session_updated_at = datetime(2026, 4, 30, 9, 0, tzinfo=UTC)
    report_updated_at = datetime(2026, 4, 30, 9, 1, tzinfo=UTC)
    session.updated_at = session_updated_at
    report = _final_report(session, status="stored", summary="Stored")
    report.updated_at = report_updated_at
    report.report_payload = {
        "summary": "Stored summary",
        "memory_candidates": [
            {
                "kind": "blocker",
                "title": "Fatigue blocked execution",
                "content": "Fatigue repeatedly reduced evening execution.",
                "confidence": 0.8,
                "source": "stored_wr",
                "proposed_memory_scope": "operating_pattern",
                "raw_payload": {"secret_prompt": "DO_NOT_EXPOSE"},
            }
        ],
        "raw_payload": {"provider_trace": "DO_NOT_EXPOSE"},
    }
    report.memory_candidates = [
        {
            "kind": "weekly_commitment",
            "title": "Protect sleep",
            "content": "Move bedtime earlier next week.",
            "confidence": 80,
        }
    ]
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.scalars_results = [[report], [], [report], []]

    first = wr.get_weekly_review_memory_candidates(db, current_user=current_user, session_id=session.id)
    second = wr.get_weekly_review_memory_candidates(db, current_user=current_user, session_id=session.id)
    response_json = first.model_dump_json()

    assert first.report_id == report.id
    assert first.session_id == session.id
    assert first.report_status == "stored"
    assert first.storage_enabled is False
    assert first.note == "Memory candidates are proposals only. Nothing has been written to memory."
    assert first.count == 2
    assert [candidate.id for candidate in first.candidates] == [candidate.id for candidate in second.candidates]
    assert first.candidates[0].kind == "blocker"
    assert first.candidates[1].confidence == 0.8
    assert session.updated_at == session_updated_at
    assert report.updated_at == report_updated_at
    assert db.committed is False
    assert "raw_payload" not in response_json
    assert "DO_NOT_EXPOSE" not in response_json
    assert not any("Memory" in type(item).__name__ for item in db.added)


def test_memory_candidates_by_report_id_endpoint_works_without_raw_payload() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    report = _final_report(session, status="stored", summary="Stored")
    report.report_payload = {
        "summary": "Stored summary",
        "memory_candidates": [
            {
                "kind": "achievement",
                "title": "Completed hard week",
                "content": "The week ended with the final report stored.",
                "raw_payload": {"secret": "DO_NOT_EXPOSE"},
            }
        ],
    }
    db.objects[(ImperiumWeeklyReviewFinalReport, report.id)] = report
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current_user
    client = TestClient(app)

    response = client.get(f"/imperium/weekly-review/final-reports/{report.id}/memory-candidates")

    assert response.status_code == 200
    body = response.json()
    assert body["report_id"] == str(report.id)
    assert body["storage_enabled"] is False
    assert body["candidates"][0]["kind"] == "achievement"
    assert "raw_payload" not in response.text
    assert "DO_NOT_EXPOSE" not in response.text


def test_session_memory_candidates_selection_prefers_stored_report() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    superseded = _final_report(session, status="superseded", summary="Old", created_at=datetime(2026, 4, 29, 8, 0, tzinfo=UTC))
    draft = _final_report(session, status="draft", summary="Draft", created_at=datetime(2026, 4, 29, 9, 0, tzinfo=UTC))
    approved = _final_report(session, status="approved", summary="Approved", created_at=datetime(2026, 4, 29, 10, 0, tzinfo=UTC))
    stored = _final_report(session, status="stored", summary="Stored", created_at=datetime(2026, 4, 29, 7, 0, tzinfo=UTC))
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.scalars_results = [[draft, approved, superseded, stored], []]

    result = wr.get_weekly_review_memory_candidates(db, current_user=current_user, session_id=session.id)

    assert result.report_id == stored.id
    assert result.report_status == "stored"


def test_memory_candidates_fallback_from_payload_when_no_candidates_exist() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    report = _final_report(session, status="stored")
    report.report_payload = {
        "title": "Stored WR",
        "summary": "The week had a clear fatigue pattern.",
        "sections": [{"title": "Execution", "content": "Completed the main project milestone."}],
        "questions_answered": [{"question": "What blocked you?", "answer": "Fatigue blocked deep work."}],
    }
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.scalars_results = [[report], []]

    result = wr.get_weekly_review_memory_candidates(db, current_user=current_user, session_id=session.id)

    assert result.count >= 3
    kinds = {candidate.kind for candidate in result.candidates}
    assert "operational_signal" in kinds
    assert "achievement" in kinds
    assert "blocker" in kinds


def test_malformed_memory_candidates_are_ignored_or_normalized() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    report = _final_report(session, status="stored")
    report.memory_candidates = [
        "not-a-dict",
        {"kind": "unknown", "title": "No content"},
        {
            "kind": "unknown",
            "title": "Useful signal",
            "content": "A stable operational signal.",
            "score": 80,
            "proposed_memory_scope": "bad-scope",
        },
    ]
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.scalars_results = [[report], []]

    result = wr.get_weekly_review_memory_candidates(db, current_user=current_user, session_id=session.id)

    assert result.count == 2
    assert result.candidates[0].kind == "operational_signal"
    assert result.candidates[0].content == "No content"
    assert result.candidates[1].confidence == 0.8
    assert result.candidates[1].proposed_memory_scope == "weekly_review"


def test_memory_candidates_preview_uses_stored_reports_and_route_validation() -> None:
    db = FakeDb()
    current_user = _user()
    stored_session = _session(current_user.id, status="stored")
    draft_session = _session(current_user.id, status="draft_ready")
    foreign_session = _session(uuid4(), status="stored")
    stored = _final_report(stored_session, status="stored", summary="Stored", created_at=datetime(2026, 4, 30, 9, 0, tzinfo=UTC))
    draft = _final_report(draft_session, status="draft", summary="Draft")
    foreign = _final_report(foreign_session, status="stored", summary="Foreign")
    db.scalars_results = [[draft, foreign, stored], []]

    result = wr.get_weekly_review_memory_candidates_preview(db, current_user=current_user, limit=1)

    assert result.limit == 1
    assert result.count == 1
    assert result.items[0].report_id == stored.id
    assert result.items[0].report_status == "stored"

    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: FakeDb()
    app.dependency_overrides[get_current_user] = lambda: current_user
    client = TestClient(app)

    response = client.get("/imperium/weekly-review/memory-candidates/preview?limit=101")

    assert response.status_code == 422


def _memory_decision_lookup(db: FakeDb):
    def lookup(_db, *, user_id, report_id, candidate_id):
        return next(
            (
                item
                for item in db.added
                if isinstance(item, ImperiumMemoryCandidateDecision)
                and item.user_id == user_id
                and item.report_id == report_id
                and item.candidate_id == candidate_id
            ),
            None,
        )

    return lookup


def _memory_decision(
    current_user,
    report: ImperiumWeeklyReviewFinalReport,
    candidate: dict,
    *,
    decision: str = "approved",
    edited_candidate: dict | None = None,
    created_at: datetime | None = None,
) -> ImperiumMemoryCandidateDecision:
    now = created_at or datetime.now(UTC)
    return ImperiumMemoryCandidateDecision(
        id=uuid4(),
        user_id=current_user.id,
        report_id=report.id,
        session_id=report.session_id,
        candidate_id=candidate["id"],
        decision=decision,
        source="weekly_review",
        original_candidate=wr._json_safe(candidate),
        edited_candidate=wr._json_safe(edited_candidate) if edited_candidate else None,
        created_at=now,
        updated_at=now,
    )


def test_approve_memory_candidate_creates_one_decision_and_replays(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    report = _final_report(session, status="stored")
    report.memory_candidates = [{"kind": "blocker", "title": "Fatigue", "content": "Fatigue blocked deep work."}]
    candidate_id = wr._build_weekly_review_memory_candidates(report, session)[0]["id"]
    db.objects[(ImperiumWeeklyReviewFinalReport, report.id)] = report
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key))
    monkeypatch.setattr(wr, "_get_memory_candidate_decision", _memory_decision_lookup(db))

    first, duplicate = wr.approve_weekly_review_memory_candidate(
        db,
        current_user=current_user,
        report_id=report.id,
        candidate_id=candidate_id,
        payload=WeeklyReviewMemoryCandidateApproveRequest(reason="Useful"),
        idempotency_key="wr-memory-approve",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/final-reports/{report.id}/memory-candidates/{candidate_id}/approve",
    )
    replay, replay_duplicate = wr.approve_weekly_review_memory_candidate(
        db,
        current_user=current_user,
        report_id=report.id,
        candidate_id=candidate_id,
        payload=WeeklyReviewMemoryCandidateApproveRequest(reason="Useful"),
        idempotency_key="wr-memory-approve",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/final-reports/{report.id}/memory-candidates/{candidate_id}/approve",
    )

    decisions = [item for item in db.added if isinstance(item, ImperiumMemoryCandidateDecision)]
    assert duplicate is False
    assert replay_duplicate is True
    assert replay.id == first.id
    assert len(decisions) == 1
    assert decisions[0].decision == "approved"
    assert decisions[0].original_candidate["id"] == candidate_id
    assert not any("Memory" in type(item).__name__ and not isinstance(item, ImperiumMemoryCandidateDecision) for item in db.added)


def test_memory_candidate_same_key_different_body_conflicts(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    report = _final_report(session, status="stored")
    report.memory_candidates = [{"kind": "blocker", "title": "Fatigue", "content": "Fatigue blocked deep work."}]
    candidate_id = wr._build_weekly_review_memory_candidates(report, session)[0]["id"]
    db.objects[(ImperiumWeeklyReviewFinalReport, report.id)] = report
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key))
    monkeypatch.setattr(wr, "_get_memory_candidate_decision", _memory_decision_lookup(db))

    wr.approve_weekly_review_memory_candidate(
        db,
        current_user=current_user,
        report_id=report.id,
        candidate_id=candidate_id,
        payload=WeeklyReviewMemoryCandidateApproveRequest(reason="First"),
        idempotency_key="wr-memory-conflict",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/final-reports/{report.id}/memory-candidates/{candidate_id}/approve",
    )

    with pytest.raises(wr.WeeklyReviewIdempotencyConflictError, match="different payload"):
        wr.approve_weekly_review_memory_candidate(
            db,
            current_user=current_user,
            report_id=report.id,
            candidate_id=candidate_id,
            payload=WeeklyReviewMemoryCandidateApproveRequest(reason="Changed"),
            idempotency_key="wr-memory-conflict",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/final-reports/{report.id}/memory-candidates/{candidate_id}/approve",
        )


def test_memory_candidate_different_key_same_candidate_conflicts(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    report = _final_report(session, status="stored")
    report.memory_candidates = [{"kind": "achievement", "title": "Win", "content": "Completed the report."}]
    candidate_id = wr._build_weekly_review_memory_candidates(report, session)[0]["id"]
    db.objects[(ImperiumWeeklyReviewFinalReport, report.id)] = report
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key))
    monkeypatch.setattr(wr, "_get_memory_candidate_decision", _memory_decision_lookup(db))

    wr.approve_weekly_review_memory_candidate(
        db,
        current_user=current_user,
        report_id=report.id,
        candidate_id=candidate_id,
        payload=WeeklyReviewMemoryCandidateApproveRequest(),
        idempotency_key="wr-memory-first-key",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/final-reports/{report.id}/memory-candidates/{candidate_id}/approve",
    )

    with pytest.raises(wr.WeeklyReviewStateConflictError, match="already been decided"):
        wr.reject_weekly_review_memory_candidate(
            db,
            current_user=current_user,
            report_id=report.id,
            candidate_id=candidate_id,
            payload=WeeklyReviewMemoryCandidateRejectRequest(reason="No"),
            idempotency_key="wr-memory-second-key",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/final-reports/{report.id}/memory-candidates/{candidate_id}/reject",
        )


def test_reject_and_edit_memory_candidate_decisions(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="approved")
    rejected_report = _final_report(session, status="approved")
    rejected_report.memory_candidates = [{"kind": "risk", "title": "Risk", "content": "Overload risk."}]
    edited_report = _final_report(session, status="approved")
    edited_report.memory_candidates = [{"kind": "operational_signal", "title": "Signal", "content": "Evening work is fragile."}]
    rejected_id = wr._build_weekly_review_memory_candidates(rejected_report, session)[0]["id"]
    edited_id = wr._build_weekly_review_memory_candidates(edited_report, session)[0]["id"]
    db.objects[(ImperiumWeeklyReviewFinalReport, rejected_report.id)] = rejected_report
    db.objects[(ImperiumWeeklyReviewFinalReport, edited_report.id)] = edited_report
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)
    monkeypatch.setattr(wr, "_get_memory_candidate_decision", _memory_decision_lookup(db))

    rejected, _ = wr.reject_weekly_review_memory_candidate(
        db,
        current_user=current_user,
        report_id=rejected_report.id,
        candidate_id=rejected_id,
        payload=WeeklyReviewMemoryCandidateRejectRequest(reason="Not useful"),
        idempotency_key="wr-memory-reject",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/final-reports/{rejected_report.id}/memory-candidates/{rejected_id}/reject",
    )
    edited, _ = wr.edit_weekly_review_memory_candidate(
        db,
        current_user=current_user,
        report_id=edited_report.id,
        candidate_id=edited_id,
        payload=WeeklyReviewMemoryCandidateEditRequest(
            edited_title="Evening fragility",
            edited_content="Evening deep work is fragile when fatigue is high.",
            edited_kind="behavior_pattern",
            edited_confidence=0.9,
            reason="More precise",
        ),
        idempotency_key="wr-memory-edit",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/final-reports/{edited_report.id}/memory-candidates/{edited_id}/edit",
    )

    assert rejected.decision == "rejected"
    assert rejected.reason == "Not useful"
    assert edited.decision == "edited"
    assert edited.edited_candidate["title"] == "Evening fragility"
    assert edited.edited_candidate["content"] == "Evening deep work is fragile when fatigue is high."
    assert edited.edited_candidate["kind"] == "behavior_pattern"
    assert edited.edited_candidate["confidence"] == 0.9


def test_memory_candidate_edit_requires_non_empty_content() -> None:
    with pytest.raises(ValueError):
        WeeklyReviewMemoryCandidateEditRequest(edited_content="")


def test_memory_candidate_decision_rejects_foreign_and_draft_reports(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    foreign_session = _session(uuid4(), status="stored")
    foreign_report = _final_report(foreign_session, status="stored")
    draft_session = _session(current_user.id, status="draft_ready")
    draft_report = _final_report(draft_session, status="draft")
    draft_report.memory_candidates = [{"kind": "blocker", "title": "Draft", "content": "Draft only."}]
    candidate_id = wr._build_weekly_review_memory_candidates(draft_report, draft_session)[0]["id"]
    db.objects[(ImperiumWeeklyReviewFinalReport, foreign_report.id)] = foreign_report
    db.objects[(ImperiumWeeklyReviewFinalReport, draft_report.id)] = draft_report
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    with pytest.raises(wr.WeeklyReviewFinalReportNotFoundError):
        wr.approve_weekly_review_memory_candidate(
            db,
            current_user=current_user,
            report_id=foreign_report.id,
            candidate_id="candidate",
            payload=WeeklyReviewMemoryCandidateApproveRequest(),
            idempotency_key="wr-memory-foreign",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/final-reports/{foreign_report.id}/memory-candidates/candidate/approve",
        )

    with pytest.raises(wr.WeeklyReviewStateConflictError, match="approved or stored"):
        wr.approve_weekly_review_memory_candidate(
            db,
            current_user=current_user,
            report_id=draft_report.id,
            candidate_id=candidate_id,
            payload=WeeklyReviewMemoryCandidateApproveRequest(),
            idempotency_key="wr-memory-draft",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/final-reports/{draft_report.id}/memory-candidates/{candidate_id}/approve",
        )


def test_memory_candidate_decisions_index_is_user_scoped_paginated_and_sanitized() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    other_session = _session(uuid4(), status="stored")
    own_old = ImperiumMemoryCandidateDecision(
        id=uuid4(),
        user_id=current_user.id,
        report_id=uuid4(),
        session_id=session.id,
        candidate_id="old",
        decision="approved",
        source="weekly_review",
        original_candidate={"id": "old", "raw_payload": {"secret": "DO_NOT_EXPOSE"}},
        created_at=datetime(2026, 4, 29, 8, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 29, 8, 0, tzinfo=UTC),
    )
    own_new = ImperiumMemoryCandidateDecision(
        id=uuid4(),
        user_id=current_user.id,
        report_id=uuid4(),
        session_id=session.id,
        candidate_id="new",
        decision="edited",
        source="weekly_review",
        original_candidate={"id": "new"},
        edited_candidate={"content": "edited"},
        created_at=datetime(2026, 4, 29, 9, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 29, 9, 0, tzinfo=UTC),
    )
    foreign = ImperiumMemoryCandidateDecision(
        id=uuid4(),
        user_id=other_session.user_id,
        report_id=uuid4(),
        session_id=other_session.id,
        candidate_id="foreign",
        decision="approved",
        source="weekly_review",
        original_candidate={"id": "foreign"},
        created_at=datetime(2026, 4, 29, 10, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 29, 10, 0, tzinfo=UTC),
    )
    db.scalars_results = [[own_old, foreign, own_new]]

    result = wr.get_weekly_review_memory_candidate_decisions(db, current_user=current_user, limit=1)
    response_json = result.model_dump_json()

    assert result.count == 1
    assert result.has_more is True
    assert result.items[0].id == own_new.id
    assert "raw_payload" not in response_json
    assert "DO_NOT_EXPOSE" not in response_json


def test_memory_candidate_preview_merges_and_hides_rejected_by_default() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    report = _final_report(session, status="stored")
    report.memory_candidates = [
        {"kind": "blocker", "title": "Blocker", "content": "Fatigue blocked work."},
        {"kind": "achievement", "title": "Win", "content": "Completed report."},
    ]
    candidates = wr._build_weekly_review_memory_candidates(report, session)
    rejected_decision = ImperiumMemoryCandidateDecision(
        id=uuid4(),
        user_id=current_user.id,
        report_id=report.id,
        session_id=session.id,
        candidate_id=candidates[0]["id"],
        decision="rejected",
        source="weekly_review",
        original_candidate=candidates[0],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    approved_decision = ImperiumMemoryCandidateDecision(
        id=uuid4(),
        user_id=current_user.id,
        report_id=report.id,
        session_id=session.id,
        candidate_id=candidates[1]["id"],
        decision="approved",
        source="weekly_review",
        original_candidate=candidates[1],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.scalars_results = [[report], [rejected_decision, approved_decision]]

    hidden = wr.get_weekly_review_memory_candidates_preview(db, current_user=current_user, include_rejected=False)
    db.scalars_results = [[report], [rejected_decision, approved_decision]]
    shown = wr.get_weekly_review_memory_candidates_preview(db, current_user=current_user, include_rejected=True)

    assert hidden.items[0].count == 1
    assert hidden.items[0].total_candidates == 2
    assert hidden.items[0].rejected_hidden_count == 1
    assert hidden.items[0].candidates[0].decision_status == "approved"
    assert shown.items[0].count == 2
    assert {candidate.decision_status for candidate in shown.items[0].candidates} == {"approved", "rejected"}


def test_memory_commit_ready_index_returns_only_approved_and_edited_without_raw_payload() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    report = _final_report(session, status="stored")
    report.memory_candidates = [
        {"kind": "blocker", "title": "Blocker", "content": "Fatigue blocked work.", "raw_payload": {"secret": "DO_NOT_EXPOSE"}},
        {"kind": "achievement", "title": "Win", "content": "Completed report."},
        {"kind": "risk", "title": "Risk", "content": "Overload risk."},
    ]
    candidates = wr._build_weekly_review_memory_candidates(report, session)
    approved = _memory_decision(current_user, report, candidates[0], decision="approved", created_at=datetime(2026, 4, 29, 8, 0, tzinfo=UTC))
    edited_candidate = dict(candidates[1])
    edited_candidate.update({"title": "Edited win", "content": "Completed and stored the report.", "kind": "achievement"})
    edited = _memory_decision(
        current_user,
        report,
        candidates[1],
        decision="edited",
        edited_candidate=edited_candidate,
        created_at=datetime(2026, 4, 29, 9, 0, tzinfo=UTC),
    )
    rejected = _memory_decision(current_user, report, candidates[2], decision="rejected", created_at=datetime(2026, 4, 29, 10, 0, tzinfo=UTC))
    foreign = _memory_decision(_user(), report, candidates[0], decision="approved", created_at=datetime(2026, 4, 29, 11, 0, tzinfo=UTC))
    db.scalars_results = [[approved, rejected, foreign, edited]]

    result = wr.get_weekly_review_memory_commit_ready_candidates(db, current_user=current_user)
    response_json = result.model_dump_json()

    assert result.count == 2
    assert [item.decision for item in result.items] == ["edited", "approved"]
    assert result.items[0].title == "Edited win"
    assert result.items[0].effective_candidate == wr._json_safe(edited_candidate)
    assert result.items[1].readiness_status == "ready"
    assert result.storage_enabled is False
    assert "raw_payload" not in response_json
    assert "DO_NOT_EXPOSE" not in response_json


def test_report_scoped_memory_commit_ready_refuses_foreign_report_and_paginates() -> None:
    db = FakeDb()
    current_user = _user()
    own_session = _session(current_user.id, status="stored")
    own_report = _final_report(own_session, status="stored")
    own_report.memory_candidates = [{"kind": "weekly_commitment", "title": "Commit", "content": "Protect sleep."}]
    candidate = wr._build_weekly_review_memory_candidates(own_report, own_session)[0]
    decision = _memory_decision(current_user, own_report, candidate, decision="approved")
    foreign_session = _session(uuid4(), status="stored")
    foreign_report = _final_report(foreign_session, status="stored")
    db.objects[(ImperiumWeeklyReviewFinalReport, own_report.id)] = own_report
    db.objects[(ImperiumWeeklyReviewFinalReport, foreign_report.id)] = foreign_report
    db.scalars_results = [[decision]]

    result = wr.get_weekly_review_memory_commit_ready_candidates_by_report_id(
        db,
        current_user=current_user,
        report_id=own_report.id,
        limit=1,
    )

    assert result.count == 1
    assert result.items[0].report_id == own_report.id
    with pytest.raises(wr.WeeklyReviewFinalReportNotFoundError):
        wr.get_weekly_review_memory_commit_ready_candidates_by_report_id(
            db,
            current_user=current_user,
            report_id=foreign_report.id,
        )


def test_memory_commit_dry_run_counts_ready_and_blocked_without_storage(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    report = _final_report(session, status="stored")
    report.memory_candidates = [
        {"kind": "blocker", "title": "Blocker", "content": "Fatigue blocked work."},
        {"kind": "achievement", "title": "Win", "content": "Completed report."},
        {"kind": "risk", "title": "Risk", "content": "Overload risk."},
    ]
    candidates = wr._build_weekly_review_memory_candidates(report, session)
    approved = _memory_decision(current_user, report, candidates[0], decision="approved")
    edited_candidate = dict(candidates[1])
    edited_candidate["content"] = "Completed report and stored the outcome."
    edited = _memory_decision(current_user, report, candidates[1], decision="edited", edited_candidate=edited_candidate)
    rejected = _memory_decision(current_user, report, candidates[2], decision="rejected")
    malformed_candidate = dict(candidates[0])
    malformed_candidate["title"] = ""
    malformed = _memory_decision(current_user, report, malformed_candidate, decision="approved")
    foreign = _memory_decision(_user(), report, candidates[0], decision="approved")
    missing_id = uuid4()
    db.scalars_results = [[approved, edited, rejected, malformed, foreign]]
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key))

    result, duplicate = wr.dry_run_weekly_review_memory_commit(
        db,
        current_user=current_user,
        payload=WeeklyReviewMemoryCommitDryRunRequest(
            decision_ids=[approved.id, edited.id, rejected.id, malformed.id, foreign.id, missing_id],
            payload={"source": "test"},
        ),
        idempotency_key="wr-memory-commit-dry-run",
        request_method="POST",
        request_path="/api/imperium/weekly-review/memory-candidates/commit-dry-run",
    )
    replay, replay_duplicate = wr.dry_run_weekly_review_memory_commit(
        db,
        current_user=current_user,
        payload=WeeklyReviewMemoryCommitDryRunRequest(
            decision_ids=[approved.id, edited.id, rejected.id, malformed.id, foreign.id, missing_id],
            payload={"source": "test"},
        ),
        idempotency_key="wr-memory-commit-dry-run",
        request_method="POST",
        request_path="/api/imperium/weekly-review/memory-candidates/commit-dry-run",
    )
    response_json = result.model_dump_json()

    assert duplicate is False
    assert replay_duplicate is True
    assert replay.would_commit_count == result.would_commit_count
    assert result.requested_count == 6
    assert result.eligible_count == 3
    assert result.would_commit_count == 2
    assert result.blocked_count == 4
    assert result.storage_enabled is False
    assert result.note == "Dry run only. Nothing has been written to memory."
    assert {item.decision for item in result.candidates} == {"approved", "edited"}
    assert any("decision is rejected" in item["readiness_reasons"] for item in result.blocked)
    assert sum("decision not found" in item["readiness_reasons"] for item in result.blocked) == 2
    assert any("decision not found" in item["readiness_reasons"] for item in result.blocked)
    assert any("candidate missing non-empty title" in item["readiness_reasons"] for item in result.blocked)
    assert len([item for item in db.added if isinstance(item, IdempotencyKey)]) == 1
    assert not any("Memory" in type(item).__name__ and not isinstance(item, IdempotencyKey) for item in db.added)
    assert "raw_payload" not in response_json


def test_memory_commit_dry_run_same_key_different_payload_conflicts(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    report = _final_report(session, status="stored")
    report.memory_candidates = [{"kind": "blocker", "title": "Blocker", "content": "Fatigue blocked work."}]
    candidate = wr._build_weekly_review_memory_candidates(report, session)[0]
    decision = _memory_decision(current_user, report, candidate, decision="approved")
    db.scalars_results = [[decision]]
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key))

    wr.dry_run_weekly_review_memory_commit(
        db,
        current_user=current_user,
        payload=WeeklyReviewMemoryCommitDryRunRequest(decision_ids=[decision.id], payload={"source": "first"}),
        idempotency_key="wr-memory-commit-conflict",
        request_method="POST",
        request_path="/api/imperium/weekly-review/memory-candidates/commit-dry-run",
    )

    with pytest.raises(wr.WeeklyReviewIdempotencyConflictError, match="different payload"):
        wr.dry_run_weekly_review_memory_commit(
            db,
            current_user=current_user,
            payload=WeeklyReviewMemoryCommitDryRunRequest(decision_ids=[decision.id], payload={"source": "changed"}),
            idempotency_key="wr-memory-commit-conflict",
            request_method="POST",
            request_path="/api/imperium/weekly-review/memory-candidates/commit-dry-run",
        )


def test_memory_commit_is_blocked_until_embedding_service(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    report = _final_report(session, status="stored")
    report.memory_candidates = [
        {"kind": "blocker", "title": "Blocker", "content": "Fatigue blocked work.", "confidence": 0.7},
        {"kind": "achievement", "title": "Win", "content": "Completed report.", "confidence": 0.8},
    ]
    candidates = wr._build_weekly_review_memory_candidates(report, session)
    approved = _memory_decision(current_user, report, candidates[0], decision="approved")
    edited_candidate = dict(candidates[1])
    edited_candidate["title"] = "Edited win"
    edited_candidate["content"] = "Completed report and stored the outcome."
    edited = _memory_decision(current_user, report, candidates[1], decision="edited", edited_candidate=edited_candidate)
    db.scalars_results = [[approved, edited]]
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key))

    result, duplicate = wr.commit_weekly_review_memory_candidates(
        db,
        current_user=current_user,
        payload=WeeklyReviewMemoryCommitRequest(decision_ids=[approved.id, edited.id], payload={"source": "test"}),
        idempotency_key="wr-memory-commit",
        request_method="POST",
        request_path="/api/imperium/weekly-review/memory-candidates/commit",
    )

    assert duplicate is False
    assert result.requested_count == 2
    assert result.committed_count == 0
    assert result.already_committed_count == 0
    assert result.blocked_count == 2
    assert result.storage_enabled is False
    assert {item["reason"] for item in result.blocked} == {
        "weekly_review_memory_commit_waits_for_embedding_service"
    }
    assert not any(isinstance(item, AIMemory) for item in db.added)
    assert "raw_payload" not in result.model_dump_json()


def test_memory_commit_blocks_rejected_undecided_foreign_and_missing(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    report = _final_report(session, status="stored")
    report.memory_candidates = [{"kind": "blocker", "title": "Blocker", "content": "Fatigue blocked work."}]
    candidate = wr._build_weekly_review_memory_candidates(report, session)[0]
    rejected = _memory_decision(current_user, report, candidate, decision="rejected")
    undecided = _memory_decision(current_user, report, candidate, decision="pending")
    foreign = _memory_decision(_user(), report, candidate, decision="approved")
    missing_id = uuid4()
    db.scalars_results = [[rejected, undecided, foreign]]
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key))

    result, _ = wr.commit_weekly_review_memory_candidates(
        db,
        current_user=current_user,
        payload=WeeklyReviewMemoryCommitRequest(
            decision_ids=[rejected.id, undecided.id, foreign.id, missing_id],
            payload={"source": "test"},
        ),
        idempotency_key="wr-memory-commit-blocked",
        request_method="POST",
        request_path="/api/imperium/weekly-review/memory-candidates/commit",
    )

    assert result.committed_count == 0
    assert result.blocked_count == 4
    assert {item["reason"] for item in result.blocked} == {
        "weekly_review_memory_commit_waits_for_embedding_service"
    }
    assert not any(isinstance(item, AIMemory) for item in db.added)


def test_memory_commit_duplicate_source_returns_existing_memory(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    report = _final_report(session, status="stored")
    candidate = wr._build_weekly_review_memory_candidates(report, session)[0]
    decision = _memory_decision(current_user, report, candidate, decision="approved")
    db.scalars_results = [[decision]]
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key))

    result, _ = wr.commit_weekly_review_memory_candidates(
        db,
        current_user=current_user,
        payload=WeeklyReviewMemoryCommitRequest(decision_ids=[decision.id], payload={"source": "test"}),
        idempotency_key="wr-memory-commit-existing",
        request_method="POST",
        request_path="/api/imperium/weekly-review/memory-candidates/commit",
    )

    assert result.committed_count == 0
    assert result.already_committed_count == 0
    assert result.blocked_count == 1
    assert result.blocked[0]["reason"] == "weekly_review_memory_commit_waits_for_embedding_service"
    assert not any(isinstance(item, AIMemory) for item in db.added)


def test_memory_commit_idempotency_replay_and_payload_conflict(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    report = _final_report(session, status="stored")
    candidate = wr._build_weekly_review_memory_candidates(report, session)[0]
    decision = _memory_decision(current_user, report, candidate, decision="approved")
    db.scalars_results = [[decision]]
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key))

    first, duplicate = wr.commit_weekly_review_memory_candidates(
        db,
        current_user=current_user,
        payload=WeeklyReviewMemoryCommitRequest(decision_ids=[decision.id], payload={"source": "first"}),
        idempotency_key="wr-memory-commit-replay",
        request_method="POST",
        request_path="/api/imperium/weekly-review/memory-candidates/commit",
    )
    replay, replay_duplicate = wr.commit_weekly_review_memory_candidates(
        db,
        current_user=current_user,
        payload=WeeklyReviewMemoryCommitRequest(decision_ids=[decision.id], payload={"source": "first"}),
        idempotency_key="wr-memory-commit-replay",
        request_method="POST",
        request_path="/api/imperium/weekly-review/memory-candidates/commit",
    )

    assert duplicate is False
    assert replay_duplicate is True
    assert replay.committed_count == first.committed_count
    assert not any(isinstance(item, AIMemory) for item in db.added)
    with pytest.raises(wr.WeeklyReviewIdempotencyConflictError, match="different payload"):
        wr.commit_weekly_review_memory_candidates(
            db,
            current_user=current_user,
            payload=WeeklyReviewMemoryCommitRequest(decision_ids=[decision.id], payload={"source": "changed"}),
            idempotency_key="wr-memory-commit-replay",
            request_method="POST",
            request_path="/api/imperium/weekly-review/memory-candidates/commit",
        )


def test_memory_commit_ready_routes_require_auth_and_missing_idempotency() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    get_response = client.get("/imperium/weekly-review/memory-candidates/commit-ready")
    post_response = client.post(
        "/imperium/weekly-review/memory-candidates/commit-dry-run",
        json={"decision_ids": [str(uuid4())]},
    )
    commit_response = client.post(
        "/imperium/weekly-review/memory-candidates/commit",
        json={"decision_ids": [str(uuid4())]},
    )

    assert get_response.status_code == 401
    assert post_response.status_code == 401
    assert commit_response.status_code == 401

    current_user = _user()
    app.dependency_overrides[get_current_user] = lambda: current_user
    authed_client = TestClient(app)
    missing_key = authed_client.post(
        "/imperium/weekly-review/memory-candidates/commit-dry-run",
        json={"decision_ids": [str(uuid4())]},
    )
    missing_commit_key = authed_client.post(
        "/imperium/weekly-review/memory-candidates/commit",
        json={"decision_ids": [str(uuid4())]},
    )

    assert missing_key.status_code == 400
    assert missing_commit_key.status_code == 400


def test_final_report_by_id_endpoint_returns_own_report_without_raw_payload() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    report = _final_report(session, status="draft", summary="Draft")
    report.report_payload["raw_payload"] = {"secret_prompt": "DO_NOT_EXPOSE"}
    db.objects[(ImperiumWeeklyReviewFinalReport, report.id)] = report
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current_user
    client = TestClient(app)

    response = client.get(f"/imperium/weekly-review/final-reports/{report.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(report.id)
    assert "raw_payload" not in response.text
    assert "DO_NOT_EXPOSE" not in response.text


def test_final_report_by_id_foreign_and_missing_return_404() -> None:
    db = FakeDb()
    current_user = _user()
    other_session = _session(uuid4(), status="stored")
    other_report = _final_report(other_session, status="stored")
    db.objects[(ImperiumWeeklyReviewFinalReport, other_report.id)] = other_report
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current_user
    client = TestClient(app)

    foreign = client.get(f"/imperium/weekly-review/final-reports/{other_report.id}")
    missing = client.get(f"/imperium/weekly-review/final-reports/{uuid4()}")

    assert foreign.status_code == 404
    assert missing.status_code == 404


def test_final_report_by_id_works_for_superseded_report() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="initial_summary_ready")
    report = _final_report(session, status="superseded", summary="Old")
    db.objects[(ImperiumWeeklyReviewFinalReport, report.id)] = report

    result = wr.get_weekly_review_final_report_by_id(db, current_user=current_user, report_id=report.id)

    assert result.id == report.id
    assert result.status == "superseded"


def test_stored_final_reports_index_filters_orders_and_trims_payload() -> None:
    db = FakeDb()
    current_user = _user()
    stored_new_session = _session(current_user.id, status="stored")
    stored_old_session = _session(current_user.id, status="stored")
    draft_session = _session(current_user.id, status="draft_ready")
    foreign_session = _session(uuid4(), status="stored")
    stored_new = _final_report(stored_new_session, status="stored", summary="New", created_at=datetime(2026, 4, 30, 12, 0, tzinfo=UTC))
    stored_new.stored_at = datetime(2026, 4, 30, 13, 0, tzinfo=UTC)
    stored_new.report_payload = {"title": "New title", "summary": "New", "raw_payload": {"secret": "DO_NOT_EXPOSE"}}
    stored_old = _final_report(stored_old_session, status="stored", summary="Old", created_at=datetime(2026, 4, 29, 12, 0, tzinfo=UTC))
    stored_old.stored_at = datetime(2026, 4, 29, 13, 0, tzinfo=UTC)
    draft = _final_report(draft_session, status="draft", summary="Draft")
    foreign = _final_report(foreign_session, status="stored", summary="Foreign")
    db.scalars_results = [[stored_old, draft, foreign, stored_new]]

    result = wr.get_stored_weekly_review_final_reports(db, current_user=current_user, limit=1)
    response_json = result.model_dump_json()

    assert result.limit == 1
    assert result.count == 1
    assert result.has_more is True
    assert result.items[0].id == stored_new.id
    assert result.items[0].status == "stored"
    assert result.items[0].title == "New title"
    assert "raw_payload" not in response_json
    assert "DO_NOT_EXPOSE" not in response_json


def test_stored_final_reports_index_requires_auth_and_validates_limit() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    no_auth = client.get("/imperium/weekly-review/final-reports/stored")
    app.dependency_overrides[get_current_user] = lambda: _user()
    too_large = client.get("/imperium/weekly-review/final-reports/stored?limit=101")

    assert no_auth.status_code == 401
    assert too_large.status_code == 422


def test_debug_status_endpoint_requires_auth() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.get(f"/imperium/weekly-review/{uuid4()}/debug-status")

    assert response.status_code == 401


def test_debug_status_refuses_other_user_session() -> None:
    db = FakeDb()
    current_user = _user()
    other_session = _session(uuid4(), status="draft_ready")
    db.objects[(ImperiumWeeklyReviewSession, other_session.id)] = other_session

    with pytest.raises(wr.WeeklyReviewSessionNotFoundError):
        wr.get_weekly_review_debug_status(db, current_user=current_user, session_id=other_session.id)


def test_debug_status_includes_summaries_without_raw_payload_body() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    ai_task = _ai_task(current_user.id)
    ai_task.input_payload = {"session_id": str(session.id)}
    ai_result = _ai_result(current_user.id, task_id=ai_task.id, result_type="weekly_report.draft")
    ai_result.raw_payload = {"secret_prompt": "DO_NOT_EXPOSE", "provider_trace": {"hidden": True}}
    report = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="draft",
        report_payload={"summary": "draft"},
        report_markdown="# Draft",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    message = _message(session, created_at=datetime.now(UTC), content="Answer")
    session.current_ai_task_id = ai_task.id
    session.final_ai_result_id = ai_result.id
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AITask, ai_task.id)] = ai_task
    db.objects[(AIResult, ai_result.id)] = ai_result
    db.scalars_results = [[ai_task], [ai_result], [report], [message]]

    result = wr.get_weekly_review_debug_status(db, current_user=current_user, session_id=session.id)
    response_json = result.model_dump_json()

    assert result.current_ai_task is not None
    assert len(result.recent_ai_tasks) == 1
    assert len(result.recent_ai_results) == 1
    assert result.recent_ai_results[0].raw_payload_keys == ["provider_trace", "secret_prompt"]
    assert len(result.final_report_candidates) == 1
    assert len(result.recent_messages) == 1
    assert '"raw_payload":' not in response_json
    assert "DO_NOT_EXPOSE" not in response_json


def test_debug_status_route_sanitizes_provider_details_in_production(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    ai_task = _ai_task(current_user.id)
    ai_task.model_hint = "internal-model"
    ai_task.privacy_level = "high"
    ai_task.error_message = "internal provider trace"
    ai_result = _ai_result(current_user.id, task_id=ai_task.id, result_type="weekly_report.draft")
    debug_result = wr.WeeklyReviewDebugStatusRead(
        session=wr.WeeklyReviewSessionRead.model_validate(session),
        current_ai_task=wr.WeeklyReviewAITaskSummary.model_validate(ai_task),
        recent_ai_tasks=[wr.WeeklyReviewAITaskSummary.model_validate(ai_task)],
        recent_ai_results=[
            wr.WeeklyReviewAIResultDebugSummary(
                **wr.WeeklyReviewAIResultSummary.model_validate(ai_result).model_dump(),
                raw_payload_keys=["secret_prompt", "provider_trace"],
            )
        ],
    )
    monkeypatch.setattr(imperium, "get_settings", lambda: SimpleNamespace(environment="production"))
    monkeypatch.setattr(imperium, "get_weekly_review_debug_status", lambda *args, **kwargs: debug_result)
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current_user
    client = TestClient(app)

    response = client.get(f"/imperium/weekly-review/{session.id}/debug-status")
    body = response.json()

    assert response.status_code == 200
    assert body["current_ai_task"]["model_hint"] is None
    assert body["current_ai_task"]["privacy_level"] is None
    assert body["current_ai_task"]["error_message"] is None
    assert body["recent_ai_tasks"][0]["model_hint"] is None
    assert body["recent_ai_results"][0]["provider"] is None
    assert body["recent_ai_results"][0]["model_used"] is None
    assert body["recent_ai_results"][0]["result_payload"] == {}
    assert body["recent_ai_results"][0]["raw_payload_keys"] == []
    assert "secret_prompt" not in response.text
    assert "provider_trace" not in response.text
    assert "internal provider trace" not in response.text


def test_debug_status_route_keeps_provider_details_in_local(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    ai_result = _ai_result(current_user.id, result_type="weekly_report.draft")
    debug_result = wr.WeeklyReviewDebugStatusRead(
        session=wr.WeeklyReviewSessionRead.model_validate(session),
        recent_ai_results=[
            wr.WeeklyReviewAIResultDebugSummary(
                **wr.WeeklyReviewAIResultSummary.model_validate(ai_result).model_dump(),
                raw_payload_keys=["provider_trace"],
            )
        ],
    )
    monkeypatch.setattr(imperium, "get_settings", lambda: SimpleNamespace(environment="local"))
    monkeypatch.setattr(imperium, "get_weekly_review_debug_status", lambda *args, **kwargs: debug_result)
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current_user
    client = TestClient(app)

    response = client.get(f"/imperium/weekly-review/{session.id}/debug-status")
    body = response.json()

    assert response.status_code == 200
    assert body["recent_ai_results"][0]["provider"] == ai_result.provider
    assert body["recent_ai_results"][0]["model_used"] == ai_result.model_used
    assert body["recent_ai_results"][0]["raw_payload_keys"] == ["provider_trace"]


def test_debug_status_includes_operational_final_report_counts_and_latest_ids() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    answer_task = _ai_task(current_user.id)
    answer_task.task_type = "weekly_report.answers.integrate"
    answer_task.input_payload = {"session_id": str(session.id)}
    interactive_task = _ai_task(current_user.id)
    interactive_task.input_payload = {"session_id": str(session.id)}
    superseded = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="superseded",
        report_payload={"summary": "old"},
        report_markdown="# Old",
        created_at=datetime(2026, 4, 29, 8, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 29, 8, 0, tzinfo=UTC),
    )
    active = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="draft",
        report_payload={"summary": "new"},
        report_markdown="# New",
        created_at=datetime(2026, 4, 29, 9, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 29, 9, 0, tzinfo=UTC),
    )
    user_message = _message(session, created_at=datetime(2026, 4, 29, 11, 0, tzinfo=UTC), content="Answer")
    revision_message = ImperiumWeeklyReviewMessage(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        role="user",
        message_type="revision_request",
        content="Make it sharper",
        created_at=datetime(2026, 4, 29, 10, 0, tzinfo=UTC),
    )
    session.current_ai_task_id = interactive_task.id
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AITask, interactive_task.id)] = interactive_task
    db.scalars_results = [[answer_task, interactive_task], [], [active, superseded], [user_message, revision_message]]

    result = wr.get_weekly_review_debug_status(db, current_user=current_user, session_id=session.id)

    assert result.active_final_report_id == active.id
    assert result.active_final_report_status == "draft"
    assert result.active_final_report_count == 1
    assert result.active_reports_count == 1
    assert result.stored_reports_count == 0
    assert result.superseded_reports_count == 1
    assert result.latest_final_report_id == active.id
    assert result.latest_active_report_id == active.id
    assert result.latest_stored_report_id is None
    assert result.historical_final_report_count == 1
    assert result.latest_user_message_id == user_message.id
    assert result.latest_revision_request_id == revision_message.id
    assert result.latest_answer_integration_task_id == answer_task.id


def test_debug_status_tracks_stored_active_report_without_raw_payload() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    report = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="stored",
        report_payload={"summary": "stored"},
        report_markdown="# Stored",
        approved_at=datetime.now(UTC),
        stored_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.scalars_results = [[], [], [report], []]

    result = wr.get_weekly_review_debug_status(db, current_user=current_user, session_id=session.id)
    response_json = result.model_dump_json()

    assert result.active_final_report_id is None
    assert result.active_final_report_status is None
    assert result.active_final_report_count == 0
    assert result.active_reports_count == 0
    assert result.stored_reports_count == 1
    assert result.superseded_reports_count == 0
    assert result.latest_final_report_id == report.id
    assert result.latest_stored_report_id == report.id
    assert result.latest_active_report_id is None
    assert result.historical_final_report_count == 0
    assert '"raw_payload":' not in response_json


def test_debug_status_counts_stored_and_superseded_reports() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    superseded = _final_report(
        session,
        status="superseded",
        summary="Old",
        created_at=datetime(2026, 4, 29, 8, 0, tzinfo=UTC),
    )
    stored = _final_report(
        session,
        status="stored",
        summary="Stored",
        created_at=datetime(2026, 4, 30, 8, 0, tzinfo=UTC),
    )
    stored.stored_at = datetime(2026, 4, 30, 9, 0, tzinfo=UTC)
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.scalars_results = [[], [], [stored, superseded], []]

    result = wr.get_weekly_review_debug_status(db, current_user=current_user, session_id=session.id)
    response_json = result.model_dump_json()

    assert result.active_reports_count == 0
    assert result.stored_reports_count == 1
    assert result.superseded_reports_count == 1
    assert result.latest_final_report_id == stored.id
    assert result.latest_stored_report_id == stored.id
    assert result.latest_active_report_id is None
    assert '"raw_payload":' not in response_json


def test_attach_ai_result_rejects_closed_session() -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="approved")
    ai_result = _ai_result(current_user.id)
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AIResult, ai_result.id)] = ai_result

    with pytest.raises(wr.WeeklyReviewStateConflictError, match="Cannot attach AI result to a closed weekly review session."):
        wr.attach_initial_ai_result(db, session_id=session.id, ai_result_id=ai_result.id)

    assert session.status == "approved"
    assert not any(isinstance(item, ImperiumWeeklyReviewMessage) for item in db.added)


def test_final_draft_is_pending_until_approval(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    draft, _duplicate = wr.create_or_update_final_draft(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewDraftCreate(
            report_payload={"summary": "draft"},
            report_markdown="# Draft",
            memory_candidates=[{"candidate": "later"}],
        ),
        idempotency_key="wr-draft-1",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/final-draft",
    )
    report = db.get(ImperiumWeeklyReviewFinalReport, draft.id)

    approved, _duplicate = wr.approve_final_report(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewFinalApproveRequest(final_report_id=report.id),
        idempotency_key="wr-approve-1",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/approve",
    )

    assert draft.status == "draft"
    assert approved.status == "approved"
    assert session.status == "approved"
    assert report.memory_candidates == [{"candidate": "later"}]


def test_draft_approve_requires_draft_candidate(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    with pytest.raises(wr.WeeklyReviewFinalReportNotFoundError):
        wr.approve_latest_draft_report(
            db,
            session_id=session.id,
            current_user=current_user,
            idempotency_key="wr-draft-approve-missing",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/{session.id}/draft/approve",
        )


def test_draft_action_endpoint_requires_auth() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.post(
        f"/imperium/weekly-review/{uuid4()}/draft/approve",
        headers={"Idempotency-Key": "wr-draft-approve-no-auth"},
    )

    assert response.status_code == 401


def test_draft_approve_is_idempotent_and_does_not_store_memory(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    report = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="draft",
        report_payload={"summary": "draft"},
        report_markdown="# Draft",
        memory_candidates=[{"candidate": "later"}],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(
        wr,
        "_get_existing_idempotency",
        lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key),
    )
    db.scalar_results = [report]

    first, duplicate = wr.approve_latest_draft_report(
        db,
        session_id=session.id,
        current_user=current_user,
        idempotency_key="wr-draft-approve",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/draft/approve",
    )
    approved_at = report.approved_at
    replay, replay_duplicate = wr.approve_latest_draft_report(
        db,
        session_id=session.id,
        current_user=current_user,
        idempotency_key="wr-draft-approve",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/draft/approve",
    )

    assert duplicate is False
    assert replay_duplicate is True
    assert replay.id == first.id
    assert first.status == "approved"
    assert approved_at is not None
    assert report.approved_at == approved_at
    assert report.stored_at is None
    assert report.memory_candidates == [{"candidate": "later"}]
    assert session.status == "approved"
    assert not any("Memory" in type(item).__name__ for item in db.added)


@pytest.mark.parametrize("closed_status", ["stored", "cancelled", "failed"])
def test_draft_approve_refuses_closed_sessions(monkeypatch, closed_status: str) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status=closed_status)
    report = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="draft",
        report_payload={"summary": "draft"},
        report_markdown="# Draft",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)
    db.scalar_results = [report]

    with pytest.raises(wr.WeeklyReviewStateConflictError):
        wr.approve_latest_draft_report(
            db,
            session_id=session.id,
            current_user=current_user,
            idempotency_key=f"wr-draft-approve-{closed_status}",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/{session.id}/draft/approve",
        )


def test_draft_approve_refuses_superseded_draft(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    report = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="superseded",
        report_payload={"summary": "draft"},
        report_markdown="# Draft",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)
    db.scalar_results = [None]

    with pytest.raises(wr.WeeklyReviewFinalReportNotFoundError):
        wr.approve_latest_draft_report(
            db,
            session_id=session.id,
            current_user=current_user,
            idempotency_key="wr-draft-approve-superseded",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/{session.id}/draft/approve",
        )

    assert report.status == "superseded"


def test_approve_latest_draft_approves_active_latest_candidate_only(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    superseded = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="superseded",
        report_payload={"summary": "old"},
        report_markdown="# Old",
        created_at=datetime(2026, 4, 29, 8, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 29, 8, 0, tzinfo=UTC),
    )
    active = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="draft",
        report_payload={"summary": "new"},
        report_markdown="# New",
        created_at=datetime(2026, 4, 29, 9, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 29, 9, 0, tzinfo=UTC),
    )
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)
    db.scalar_results = [active]

    result, duplicate = wr.approve_latest_draft_report(
        db,
        session_id=session.id,
        current_user=current_user,
        idempotency_key="wr-approve-latest-active",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/draft/approve",
    )

    assert duplicate is False
    assert result.id == active.id
    assert active.status == "approved"
    assert superseded.status == "superseded"
    assert session.status == "approved"


def test_store_approved_draft_succeeds_and_is_idempotent(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="approved")
    report = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="approved",
        report_payload={"summary": "approved"},
        report_markdown="# Approved",
        approved_at=datetime(2026, 4, 30, 10, 0, tzinfo=UTC),
        stored_at=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(
        wr,
        "_get_existing_idempotency",
        lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key),
    )
    db.scalar_results = [report]

    first, duplicate = wr.store_approved_final_report(
        db,
        session_id=session.id,
        current_user=current_user,
        idempotency_key="wr-store-approved",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/draft/store",
    )
    stored_at = report.stored_at
    replay, replay_duplicate = wr.store_approved_final_report(
        db,
        session_id=session.id,
        current_user=current_user,
        idempotency_key="wr-store-approved",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/draft/store",
    )

    assert duplicate is False
    assert replay_duplicate is True
    assert replay.id == first.id
    assert first.status == "stored"
    assert stored_at is not None
    assert report.stored_at == stored_at
    assert session.status == "stored"
    assert session.completed_at is not None
    assert not any("Memory" in type(item).__name__ for item in db.added)
    assert not any(isinstance(item, AITask) for item in db.added)


def test_store_before_approval_is_rejected(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    report = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="draft",
        report_payload={"summary": "draft"},
        report_markdown="# Draft",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)
    db.scalar_results = [report]

    with pytest.raises(wr.WeeklyReviewStateConflictError, match="must be approved"):
        wr.store_approved_final_report(
            db,
            session_id=session.id,
            current_user=current_user,
            idempotency_key="wr-store-before-approval",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/{session.id}/draft/store",
        )


def test_store_already_stored_new_key_conflicts(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    report = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="stored",
        report_payload={"summary": "stored"},
        report_markdown="# Stored",
        approved_at=datetime.now(UTC),
        stored_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)
    db.scalar_results = [report]

    with pytest.raises(wr.WeeklyReviewStateConflictError, match="Cannot modify a closed weekly review session."):
        wr.store_approved_final_report(
            db,
            session_id=session.id,
            current_user=current_user,
            idempotency_key="wr-store-again",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/{session.id}/draft/store",
        )


@pytest.mark.parametrize("closed_status", ["cancelled", "failed"])
def test_store_refuses_cancelled_or_failed_sessions(monkeypatch, closed_status: str) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status=closed_status)
    report = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="approved",
        report_payload={"summary": "approved"},
        report_markdown="# Approved",
        approved_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)
    db.scalar_results = [report]

    with pytest.raises(wr.WeeklyReviewStateConflictError):
        wr.store_approved_final_report(
            db,
            session_id=session.id,
            current_user=current_user,
            idempotency_key=f"wr-store-{closed_status}",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/{session.id}/draft/store",
        )


def test_store_endpoint_requires_auth() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.post(
        f"/imperium/weekly-review/{uuid4()}/draft/store",
        headers={"Idempotency-Key": "wr-store-no-auth"},
    )

    assert response.status_code == 401


def test_store_refuses_other_user_session() -> None:
    db = FakeDb()
    current_user = _user()
    other_session = _session(uuid4(), status="approved")
    db.objects[(ImperiumWeeklyReviewSession, other_session.id)] = other_session

    with pytest.raises(wr.WeeklyReviewSessionNotFoundError):
        wr.store_approved_final_report(
            db,
            session_id=other_session.id,
            current_user=current_user,
            idempotency_key="wr-store-other-user",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/{other_session.id}/draft/store",
        )


def test_stored_session_rejects_reject_and_request_changes(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    with pytest.raises(wr.WeeklyReviewStateConflictError):
        wr.reject_latest_draft_report(
            db,
            session_id=session.id,
            current_user=current_user,
            payload=WeeklyReviewDraftRejectRequest(reason="No"),
            idempotency_key="wr-reject-stored",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/{session.id}/draft/reject",
        )

    with pytest.raises(wr.WeeklyReviewStateConflictError):
        wr.request_draft_changes(
            db,
            session_id=session.id,
            current_user=current_user,
            payload=WeeklyReviewAnswerRequest(content="Change it"),
            idempotency_key="wr-request-stored",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/{session.id}/draft/request-changes",
        )

    assert not any(isinstance(item, AITask) for item in db.added)


def test_stored_session_rejects_answer_approve_and_store_with_new_key(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    report = _final_report(session, status="stored")
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)
    db.scalar_results = [report, report]

    with pytest.raises(wr.WeeklyReviewStateConflictError, match="Cannot modify a closed weekly review session."):
        wr.add_user_message(
            db,
            session_id=session.id,
            current_user=current_user,
            payload=WeeklyReviewAnswerRequest(content="Too late"),
            idempotency_key="wr-answer-stored-new",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/{session.id}/answer",
            create_integration_task=True,
        )

    with pytest.raises(wr.WeeklyReviewStateConflictError, match="Cannot modify a closed weekly review session."):
        wr.approve_latest_draft_report(
            db,
            session_id=session.id,
            current_user=current_user,
            idempotency_key="wr-approve-stored-new",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/{session.id}/draft/approve",
        )

    with pytest.raises(wr.WeeklyReviewStateConflictError, match="Cannot modify a closed weekly review session."):
        wr.store_approved_final_report(
            db,
            session_id=session.id,
            current_user=current_user,
            idempotency_key="wr-store-stored-new",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/{session.id}/draft/store",
        )

    assert not any(isinstance(item, AITask) for item in db.added)
    assert not any(isinstance(item, ImperiumWeeklyReviewMessage) for item in db.added)


@pytest.mark.parametrize("closed_status", ["cancelled", "failed"])
def test_terminal_session_rejects_answer(monkeypatch, closed_status: str) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status=closed_status)
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    with pytest.raises(wr.WeeklyReviewStateConflictError, match="Cannot modify a closed weekly review session."):
        wr.add_user_message(
            db,
            session_id=session.id,
            current_user=current_user,
            payload=WeeklyReviewAnswerRequest(content="Closed"),
            idempotency_key=f"wr-answer-{closed_status}",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/{session.id}/answer",
        )


def test_draft_reject_is_idempotent_without_schema_migration(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    session.initial_ai_result_id = uuid4()
    report = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="draft",
        report_payload={"summary": "draft"},
        report_markdown="# Draft",
        memory_candidates=[],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(
        wr,
        "_get_existing_idempotency",
        lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key),
    )
    db.scalar_results = [report]

    first, duplicate = wr.reject_latest_draft_report(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewDraftRejectRequest(reason="Needs changes", payload={"tone": "shorter"}),
        idempotency_key="wr-draft-reject",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/draft/reject",
    )
    replay, replay_duplicate = wr.reject_latest_draft_report(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewDraftRejectRequest(reason="Needs changes", payload={"tone": "shorter"}),
        idempotency_key="wr-draft-reject",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/draft/reject",
    )

    assert duplicate is False
    assert replay_duplicate is True
    assert replay.id == first.id
    assert first.status == "superseded"
    assert report.report_payload["_rejection"]["reason"] == "Needs changes"
    assert session.status == "initial_summary_ready"
    assert len([item for item in db.added if isinstance(item, ImperiumWeeklyReviewMessage)]) == 1


def test_reject_preserves_existing_ai_results_and_messages(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    ai_result = _ai_result(current_user.id, result_type="weekly_report.draft")
    existing_message = ImperiumWeeklyReviewMessage(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        role="qwen",
        message_type="draft",
        content="# Draft",
        payload={"summary": "draft"},
        ai_result_id=ai_result.id,
        created_at=datetime.now(UTC),
    )
    report = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="draft",
        report_payload={"summary": "draft"},
        report_markdown="# Draft",
        source_ai_result_id=ai_result.id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.objects[(AIResult, ai_result.id)] = ai_result
    db.objects[(ImperiumWeeklyReviewMessage, existing_message.id)] = existing_message
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)
    db.scalar_results = [report]

    result, duplicate = wr.reject_latest_draft_report(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewDraftRejectRequest(reason="Try again"),
        idempotency_key="wr-reject-preserve",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/draft/reject",
    )

    assert duplicate is False
    assert result.status == "superseded"
    assert db.get(AIResult, ai_result.id) is ai_result
    assert db.get(ImperiumWeeklyReviewMessage, existing_message.id) is existing_message
    assert len([item for item in db.added if isinstance(item, ImperiumWeeklyReviewMessage)]) == 1


def test_request_draft_changes_supersedes_draft_and_returns_to_chat(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    report = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="draft",
        report_payload={"summary": "draft"},
        report_markdown="# Draft",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(
        wr,
        "_get_existing_idempotency",
        lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key),
    )
    db.scalar_results = [report]

    first, duplicate = wr.request_draft_changes(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewAnswerRequest(content="Change the focus", payload={"section": "money"}),
        idempotency_key="wr-draft-request-changes",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/draft/request-changes",
    )
    replay, replay_duplicate = wr.request_draft_changes(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewAnswerRequest(content="Change the focus", payload={"section": "money"}),
        idempotency_key="wr-draft-request-changes",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/draft/request-changes",
    )

    messages = [item for item in db.added if isinstance(item, ImperiumWeeklyReviewMessage)]
    tasks = [item for item in db.added if isinstance(item, AITask)]
    assert duplicate is False
    assert replay_duplicate is True
    assert replay.id == first.id
    assert len(messages) == 2
    assert messages[0].message_type == "revision_request"
    assert messages[1].message_type == "assistant_followup"
    assert messages[1].content.endswith(wr.WR_FINAL_CONFIRMATION_PROMPT)
    assert tasks == []
    assert report.status == "superseded"
    assert session.status == "conversation_active"


def test_request_draft_changes_same_key_different_payload_conflicts(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    report = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="draft",
        report_payload={"summary": "draft"},
        report_markdown="# Draft",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(
        wr,
        "_get_existing_idempotency",
        lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key),
    )
    db.scalar_results = [report]

    wr.request_draft_changes(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewAnswerRequest(content="First"),
        idempotency_key="wr-draft-request-conflict",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/draft/request-changes",
    )

    with pytest.raises(wr.WeeklyReviewIdempotencyConflictError, match="different payload"):
        wr.request_draft_changes(
            db,
            session_id=session.id,
            current_user=current_user,
            payload=WeeklyReviewAnswerRequest(content="Changed"),
            idempotency_key="wr-draft-request-conflict",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/{session.id}/draft/request-changes",
        )


def test_request_changes_can_attach_new_draft_after_previous_draft_superseded(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="draft_ready")
    first_report = ImperiumWeeklyReviewFinalReport(
        id=uuid4(),
        session_id=session.id,
        user_id=current_user.id,
        week_start=session.week_start,
        week_end=session.week_end,
        status="draft",
        report_payload={"summary": "first"},
        report_markdown="# First",
        source_ai_result_id=uuid4(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    second_result = _ai_result(current_user.id, result_type="weekly_report.draft")
    second_result.result_payload = {"report_markdown": "# Revised"}
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AIResult, second_result.id)] = second_result
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)
    db.scalar_results = [first_report]

    wr.request_draft_changes(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewAnswerRequest(content="Please revise"),
        idempotency_key="wr-request-attach-changes",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/draft/request-changes",
    )
    db.scalars_results = [[first_report]]
    result, duplicate = wr.attach_ai_result_to_session(
        db,
        session_id=session.id,
        payload=WeeklyReviewAttachAIResultRequest(ai_result_id=second_result.id),
        idempotency_key="wr-request-attach-new-draft",
        request_method="POST",
        request_path=f"/api/internal/weekly-review/{session.id}/attach-ai-result",
    )

    reports = [item for item in db.added if isinstance(item, ImperiumWeeklyReviewFinalReport)]
    assert duplicate is False
    assert result.status == "draft_ready"
    assert first_report.status == "superseded"
    assert len(reports) == 1
    assert reports[0].source_ai_result_id == second_result.id
    assert reports[0].status == "draft"


def test_request_draft_changes_rejects_closed_session(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="stored")
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    with pytest.raises(wr.WeeklyReviewStateConflictError):
        wr.request_draft_changes(
            db,
            session_id=session.id,
            current_user=current_user,
            payload=WeeklyReviewAnswerRequest(content="Change this"),
            idempotency_key="wr-draft-request-closed",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/{session.id}/draft/request-changes",
        )


def test_request_draft_changes_can_supersede_approved_report(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="approved")
    report = _final_report(session, status="approved")
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)
    db.scalar_results = [report]

    result, duplicate = wr.request_draft_changes(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewAnswerRequest(content="Change approved draft"),
        idempotency_key="wr-draft-request-approved",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/draft/request-changes",
    )

    assert duplicate is False
    assert result.message_type == "revision_request"
    assert report.status == "superseded"
    assert session.status == "conversation_active"


def test_final_draft_with_draft_ai_result_sets_draft_ready(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="integrating_answers")
    ai_result = _ai_result(current_user.id, result_type="weekly_report.draft")
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AIResult, ai_result.id)] = ai_result
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    draft, _duplicate = wr.create_or_update_final_draft(
        db,
        session_id=session.id,
        current_user=current_user,
        payload=WeeklyReviewDraftCreate(
            ai_result_id=ai_result.id,
            report_payload={"summary": "draft"},
            report_markdown="# Draft",
        ),
        idempotency_key="wr-draft-ai-result",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{session.id}/final-draft",
    )

    assert draft.status == "draft"
    assert draft.source_ai_result_id == ai_result.id
    assert session.status == "draft_ready"
    assert session.final_ai_result_id is None


def test_final_draft_endpoint_requires_auth() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.post(
        f"/imperium/weekly-review/{uuid4()}/final-draft",
        json={"report_payload": {"summary": "draft"}, "report_markdown": "# Draft"},
        headers={"Idempotency-Key": "wr-draft-no-auth"},
    )

    assert response.status_code == 401


def test_illegal_message_transition_and_cancel(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    approved_session = _session(current_user.id, status="approved")
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: approved_session)
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    with pytest.raises(wr.WeeklyReviewStateConflictError):
        wr.add_user_message(
            db,
            session_id=approved_session.id,
            current_user=current_user,
            payload=WeeklyReviewAnswerRequest(content="Too late"),
            idempotency_key="wr-answer-closed",
            request_method="POST",
            request_path=f"/api/imperium/weekly-review/{approved_session.id}/answer",
        )

    open_session = _session(current_user.id, status="launched")
    monkeypatch.setattr(wr, "_get_session_for_user", lambda *args, **kwargs: open_session)
    result, _duplicate = wr.cancel_weekly_review(
        db,
        session_id=open_session.id,
        current_user=current_user,
        payload=WeeklyReviewCancelRequest(reason="Not this week"),
        idempotency_key="wr-cancel-1",
        request_method="POST",
        request_path=f"/api/imperium/weekly-review/{open_session.id}/cancel",
    )

    assert result.status == "cancelled"


def test_mutating_endpoint_helper_requires_idempotency_key() -> None:
    with pytest.raises(HTTPException) as exc:
        imperium._require_idempotency_key(None)
    assert exc.value.status_code == 400


def test_internal_attach_ai_result_hmac_without_plaintext_secret(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="preparing_initial_summary")
    ai_result = _ai_result(current_user.id)
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AIResult, ai_result.id)] = ai_result
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    secret = "strong-internal-webhook-secret-for-tests"
    timestamp = int(datetime.now(UTC).timestamp())
    body = f'{{"ai_result_id":"{ai_result.id}"}}'.encode("utf-8")
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
        f"/internal/weekly-review/{session.id}/attach-ai-result",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Timestamp": str(timestamp),
            "X-Signature": signature,
            "Idempotency-Key": "wr-attach-route-1",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "initial_summary_ready"


def test_internal_attach_ai_result_requires_hmac(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="preparing_initial_summary")
    ai_result = _ai_result(current_user.id)
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AIResult, ai_result.id)] = ai_result
    monkeypatch.setattr(
        internal_webhooks,
        "get_settings",
        lambda: SimpleNamespace(
            internal_webhook_secret="strong-internal-webhook-secret-for-tests",
            webhook_timestamp_tolerance_seconds=60,
        ),
    )

    app = FastAPI()
    app.include_router(internal.router, prefix="/internal")
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    response = client.post(
        f"/internal/weekly-review/{session.id}/attach-ai-result",
        json={"ai_result_id": str(ai_result.id)},
        headers={"Idempotency-Key": "wr-attach-missing-hmac"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing signature."


def test_n8n_client_signs_outbound_payload() -> None:
    settings = Settings(
        jwt_secret_key="strong-jwt-secret-for-tests-that-is-long",
        internal_webhook_secret="strong-internal-secret-for-tests-long",
        n8n_base_url="https://n8n.example/webhook/",
        n8n_webhook_secret="n8n-webhook-secret-for-tests",
    )
    payload = {"b": 2, "a": 1}

    signed = n8n_client.build_signed_n8n_request(
        path="/wr/start",
        payload=payload,
        idempotency_key="n8n-trigger-1",
        settings=settings,
        timestamp=123,
    )

    expected_body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    expected_signature = hmac.new(
        settings.n8n_webhook_secret.encode("utf-8"),
        b"123." + expected_body,
        sha256,
    ).hexdigest()
    assert signed.url == "https://n8n.example/webhook/wr/start"
    assert signed.body == expected_body
    assert signed.headers["X-Timestamp"] == "123"
    assert signed.headers["X-Signature"] == expected_signature
    assert signed.headers["Idempotency-Key"] == "n8n-trigger-1"


def test_n8n_client_refuses_unsigned_outbound_payload_when_secret_missing() -> None:
    settings = Settings(
        jwt_secret_key="strong-jwt-secret-for-tests-that-is-long",
        internal_webhook_secret="strong-internal-secret-for-tests-long",
        n8n_base_url="https://n8n.example/webhook/",
        n8n_webhook_secret=None,
    )

    with pytest.raises(n8n_client.N8NConfigurationError, match="N8N_WEBHOOK_SECRET"):
        n8n_client.build_signed_n8n_request(
            path="imperium/wr/interactive-start-qwen-dry-run",
            payload={"task_id": "task"},
            idempotency_key="n8n-trigger-no-secret",
            settings=settings,
            timestamp=123,
        )

    assert n8n_client.n8n_is_configured(settings) is False


def test_n8n_client_rejects_non_http_base_url() -> None:
    settings = Settings(
        jwt_secret_key="strong-jwt-secret-for-tests-that-is-long",
        internal_webhook_secret="strong-internal-secret-for-tests-long",
        n8n_base_url="file:///tmp/n8n.sock",
        n8n_webhook_secret="n8n-webhook-secret-for-tests",
    )

    with pytest.raises(n8n_client.N8NConfigurationError, match="http"):
        n8n_client.build_signed_n8n_request(
            path="imperium/wr/interactive-start-qwen-dry-run",
            payload={"task_id": "task"},
            idempotency_key="n8n-trigger-bad-url",
            settings=settings,
            timestamp=123,
        )


def test_wr_bridge_callback_matches_n8n_export_contract(monkeypatch) -> None:
    # Equivalence lock: the ported bridge produces the exact callback the n8n
    # export produced (fixtures from ops/n8n/workflows JSON), except model_used
    # which is resolved via the local_executor role (DV-6).
    from fixtures.n8n_wr_payloads import (
        EXPECTED_START_CALLBACK_PROVIDER,
        EXPECTED_START_CALLBACK_RESULT_TYPE,
        EXPECTED_START_CALLBACK_SOURCE,
        EXPECTED_START_IDEMPOTENCY_TEMPLATE,
        EXPECTED_START_RAW_WORKFLOW,
        interactive_start_payload,
    )

    task_id = uuid4()
    session_id = uuid4()
    ai_task = AITask(
        id=task_id,
        user_id=uuid4(),
        task_type="weekly_report.interactive.start",
        status="queued",
        source_module="imperium",
        input_payload={},
        prepared_payload=interactive_start_payload(task_id=str(task_id), session_id=str(session_id)),
    )

    captured = {}

    def fake_receive(db, *, task_id, payload, idempotency_key):
        captured["callback"] = payload
        captured["idempotency_key"] = idempotency_key
        return SimpleNamespace(id=uuid4()), False

    def fake_attach(db, *, session_id, payload, idempotency_key, request_method, request_path):
        captured["attach_idempotency_key"] = idempotency_key
        captured["attach_payload"] = payload
        return SimpleNamespace(), False

    monkeypatch.setattr(wr_bridge_module, "receive_ai_result", fake_receive)
    monkeypatch.setattr(wr_bridge_module, "attach_ai_result_to_session", fake_attach)
    monkeypatch.setattr(
        wr_bridge_module, "resolve_model_id", lambda role, db=None: "qwen3-32b"
    )

    wr_bridge_module.run_wr_interactive_start(FakeDb(), ai_task=ai_task)

    callback = captured["callback"]
    assert callback.result_type == EXPECTED_START_CALLBACK_RESULT_TYPE
    assert callback.result_payload["source"] == EXPECTED_START_CALLBACK_SOURCE
    assert callback.provider == EXPECTED_START_CALLBACK_PROVIDER
    assert callback.raw_payload["workflow"] == EXPECTED_START_RAW_WORKFLOW
    assert callback.model_used == "qwen3-32b"
    assert captured["idempotency_key"] == EXPECTED_START_IDEMPOTENCY_TEMPLATE.format(task_id=task_id)


def test_n8n_client_is_deprecated_and_has_no_caller() -> None:
    # Passe 0: n8n is out of the production path. The client module stays only
    # until the VPS export is confirmed, warns on import, and nothing calls it.
    import subprocess

    result = subprocess.run(
        ["grep", "-rn", "n8n_client", "app/"],
        capture_output=True,
        text=True,
        check=False,
    )
    callers = [
        line
        for line in result.stdout.splitlines()
        if "app/services/integrations/n8n_client.py" not in line.split(":")[0]
    ]
    assert callers == []
    assert "deprecated" in (n8n_client.__doc__ or "").lower()


def test_mock_ai_summary_attachment_is_proposal_only(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="preparing_initial_summary")
    ai_task = AITask(
        id=uuid4(),
        user_id=current_user.id,
        task_type="weekly_report.interactive.start",
        status="queued",
        source_module="imperium",
        input_payload={"week_start": "2026-04-27", "week_end": "2026-05-03"},
    )
    session.current_ai_task_id = ai_task.id
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AITask, ai_task.id)] = ai_task
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    result, duplicate = wr.mock_weekly_review_summary(
        db,
        session_id=session.id,
        payload=AIResultCallback(
            result_type="weekly_report.summary",
            result_payload={"summary": "Mock initial WR summary"},
            model_used="mock-qwen",
            provider="mock",
        ),
        idempotency_key="wr-mock-summary-1",
        request_method="POST",
        request_path=f"/api/internal/weekly-review/{session.id}/mock-ai-summary",
    )

    ai_result = next(item for item in db.added if isinstance(item, AIResult))
    assert duplicate is False
    assert result.status == "initial_summary_ready"
    assert ai_result.status == "pending_validation"
    assert any(isinstance(item, ImperiumWeeklyReviewMessage) for item in db.added)
    assert not any(isinstance(item, ImperiumWeeklyReviewFinalReport) for item in db.added)
    assert session.status != "approved"


def test_mock_summary_replay_uses_sub_idempotency_keys_without_duplicates(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="preparing_initial_summary")
    ai_task = _ai_task(current_user.id)
    session.current_ai_task_id = ai_task.id
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AITask, ai_task.id)] = ai_task
    monkeypatch.setattr(
        wr,
        "_get_existing_idempotency",
        lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key),
    )
    receive_calls = []

    def fake_receive_ai_result(_db, *, task_id, payload, idempotency_key):
        receive_calls.append(idempotency_key)
        existing = next(
            (
                item
                for item in db.added
                if isinstance(item, AIResult)
                and item.task_id == task_id
                and item.idempotency_key == idempotency_key
            ),
            None,
        )
        if existing is not None:
            return existing, True
        ai_result = _ai_result(current_user.id, task_id=task_id)
        ai_result.result_type = payload.result_type
        ai_result.result_payload = payload.result_payload
        ai_result.idempotency_key = idempotency_key
        db.add(ai_result)
        return ai_result, False

    monkeypatch.setattr(wr, "receive_ai_result", fake_receive_ai_result)
    payload = AIResultCallback(
        result_type="weekly_report.summary",
        result_payload={"summary": "Mock initial WR summary"},
        model_used="mock-qwen",
        provider="mock",
    )

    first, duplicate = wr.mock_weekly_review_summary(
        db,
        session_id=session.id,
        payload=payload,
        idempotency_key="wr-mock-summary-replay",
        request_method="POST",
        request_path=f"/api/internal/weekly-review/{session.id}/mock-ai-summary",
    )
    replay, replay_duplicate = wr.mock_weekly_review_summary(
        db,
        session_id=session.id,
        payload=payload,
        idempotency_key="wr-mock-summary-replay",
        request_method="POST",
        request_path=f"/api/internal/weekly-review/{session.id}/mock-ai-summary",
    )

    assert duplicate is False
    assert replay_duplicate is True
    assert replay.id == first.id
    assert receive_calls == ["wr-mock-summary-replay:ai-result", "wr-mock-summary-replay:ai-result"]
    assert len([item for item in db.added if isinstance(item, AIResult)]) == 1
    assert len([item for item in db.added if isinstance(item, ImperiumWeeklyReviewMessage)]) == 1
    assert len([item for item in db.added if isinstance(item, IdempotencyKey)]) == 1
    assert db.added[-1].idempotency_key == "wr-mock-summary-replay:wr-attach"


def test_mock_summary_same_key_different_payload_conflicts(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="preparing_initial_summary")
    ai_task = _ai_task(current_user.id)
    session.current_ai_task_id = ai_task.id
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AITask, ai_task.id)] = ai_task
    seen_hashes = {}

    def fake_receive_ai_result(_db, *, task_id, payload, idempotency_key):
        payload_hash = json.dumps(payload.model_dump(mode="json"), sort_keys=True, default=str)
        if idempotency_key in seen_hashes and seen_hashes[idempotency_key] != payload_hash:
            raise wr.WeeklyReviewAIResultConflictError("Idempotency key already used with different payload.")
        seen_hashes[idempotency_key] = payload_hash
        existing = next(
            (item for item in db.added if isinstance(item, AIResult) and item.idempotency_key == idempotency_key),
            None,
        )
        if existing is not None:
            return existing, True
        ai_result = _ai_result(current_user.id, task_id=task_id)
        ai_result.result_type = payload.result_type
        ai_result.result_payload = payload.result_payload
        ai_result.idempotency_key = idempotency_key
        db.add(ai_result)
        return ai_result, False

    monkeypatch.setattr(wr, "receive_ai_result", fake_receive_ai_result)
    monkeypatch.setattr(
        wr,
        "_get_existing_idempotency",
        lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key),
    )

    wr.mock_weekly_review_summary(
        db,
        session_id=session.id,
        payload=AIResultCallback(result_type="weekly_report.summary", result_payload={"summary": "First"}),
        idempotency_key="wr-mock-summary-conflict",
        request_method="POST",
        request_path=f"/api/internal/weekly-review/{session.id}/mock-ai-summary",
    )

    with pytest.raises(wr.WeeklyReviewAIResultConflictError, match="different payload"):
        wr.mock_weekly_review_summary(
            db,
            session_id=session.id,
            payload=AIResultCallback(result_type="weekly_report.summary", result_payload={"summary": "Changed"}),
            idempotency_key="wr-mock-summary-conflict",
            request_method="POST",
            request_path=f"/api/internal/weekly-review/{session.id}/mock-ai-summary",
        )

    assert len([item for item in db.added if isinstance(item, AIResult)]) == 1
    assert len([item for item in db.added if isinstance(item, ImperiumWeeklyReviewMessage)]) == 1


def test_mock_summary_rejects_closed_session(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="cancelled")
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    with pytest.raises(wr.WeeklyReviewStateConflictError, match="Cannot attach AI result to a closed weekly review session."):
        wr.mock_weekly_review_summary(
            db,
            session_id=session.id,
            payload=AIResultCallback(
                result_type="weekly_report.summary",
                result_payload={"summary": "Mock initial WR summary"},
                model_used="mock-qwen",
                provider="mock",
            ),
            idempotency_key="wr-mock-summary-closed",
            request_method="POST",
            request_path=f"/api/internal/weekly-review/{session.id}/mock-ai-summary",
        )

    assert session.status == "cancelled"
    assert not any(isinstance(item, AIResult) for item in db.added)


def test_same_idempotency_key_on_different_wr_endpoint_has_clear_conflict() -> None:
    current_user = _user()
    existing = IdempotencyKey(
        id=uuid4(),
        user_id=current_user.id,
        idempotency_key="wr-cross-endpoint-key",
        request_method="POST",
        request_path="/api/imperium/weekly-review/old/messages",
        request_hash="old-hash",
        response_body={"id": str(uuid4())},
    )

    with pytest.raises(wr.WeeklyReviewIdempotencyConflictError, match="Idempotency-Key already used on a different endpoint."):
        wr._handle_idempotency(
            existing,
            "new-hash",
            WeeklyReviewMessageRead,
            request_path="/api/imperium/weekly-review/new/cancel",
        )


def test_internal_mock_ai_summary_hmac_without_plaintext_secret(monkeypatch) -> None:
    db = FakeDb()
    current_user = _user()
    session = _session(current_user.id, status="preparing_initial_summary")
    ai_task = AITask(
        id=uuid4(),
        user_id=current_user.id,
        task_type="weekly_report.interactive.start",
        status="queued",
        source_module="imperium",
        input_payload={"week_start": "2026-04-27", "week_end": "2026-05-03"},
    )
    session.current_ai_task_id = ai_task.id
    db.objects[(ImperiumWeeklyReviewSession, session.id)] = session
    db.objects[(AITask, ai_task.id)] = ai_task
    monkeypatch.setattr(wr, "_get_existing_idempotency", lambda *args, **kwargs: None)

    secret = "strong-internal-webhook-secret-for-tests"
    timestamp = int(datetime.now(UTC).timestamp())
    body = (
        b'{"result_type":"weekly_report.summary","result_payload":{"summary":"Mock WR summary"},'
        b'"model_used":"mock-qwen","provider":"mock"}'
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
        f"/internal/weekly-review/{session.id}/mock-ai-summary",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Timestamp": str(timestamp),
            "X-Signature": signature,
            "Idempotency-Key": "wr-mock-summary-route-1",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "initial_summary_ready"


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


def test_weekly_review_ready_requires_configured_canonical_user(monkeypatch) -> None:
    db = FakeDb()
    secret = "strong-internal-webhook-secret-for-tests"
    body = b""
    monkeypatch.setattr(
        internal_webhooks,
        "get_settings",
        lambda: SimpleNamespace(
            internal_webhook_secret=secret,
            webhook_timestamp_tolerance_seconds=60,
        ),
    )
    monkeypatch.setattr(internal, "get_settings", lambda: SimpleNamespace(imperium_canonical_user_id=None))

    app = FastAPI()
    app.include_router(internal.router, prefix="/internal")
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    response = client.post(
        "/internal/weekly-review/ready?week_start=2026-04-27",
        content=body,
        headers=_signed_internal_headers(secret, body, idempotency_key="wr-ready-missing-user"),
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Canonical user is not configured."


def test_weekly_review_ready_configured_user_not_found(monkeypatch) -> None:
    db = FakeDb()
    configured_user_id = uuid4()
    secret = "strong-internal-webhook-secret-for-tests"
    body = b""
    monkeypatch.setattr(
        internal_webhooks,
        "get_settings",
        lambda: SimpleNamespace(
            internal_webhook_secret=secret,
            webhook_timestamp_tolerance_seconds=60,
        ),
    )
    monkeypatch.setattr(internal, "get_settings", lambda: SimpleNamespace(imperium_canonical_user_id=configured_user_id))

    app = FastAPI()
    app.include_router(internal.router, prefix="/internal")
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    response = client.post(
        "/internal/weekly-review/ready?week_start=2026-04-27",
        content=body,
        headers=_signed_internal_headers(secret, body, idempotency_key="wr-ready-missing-row"),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Canonical user not found."


def test_weekly_review_ready_uses_configured_canonical_user(monkeypatch) -> None:
    db = FakeDb()
    configured_user_id = uuid4()
    user = User(id=configured_user_id, email="canonical@example.com")
    db.objects[(User, configured_user_id)] = user
    secret = "strong-internal-webhook-secret-for-tests"
    body = b""
    monkeypatch.setattr(
        internal_webhooks,
        "get_settings",
        lambda: SimpleNamespace(
            internal_webhook_secret=secret,
            webhook_timestamp_tolerance_seconds=60,
        ),
    )
    monkeypatch.setattr(internal, "get_settings", lambda: SimpleNamespace(imperium_canonical_user_id=configured_user_id))

    app = FastAPI()
    app.include_router(internal.router, prefix="/internal")
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    response = client.post(
        "/internal/weekly-review/ready?week_start=2026-04-27",
        content=body,
        headers=_signed_internal_headers(secret, body, idempotency_key="wr-ready-ok"),
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "week_start": "2026-04-27", "ready": True}
