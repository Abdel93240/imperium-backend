from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.models.imperium import ImperiumWeeklyReviewState
from app.services.imperium import weekly_review_state


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.flushed = False
        self.committed = False

    def add(self, obj) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed = True

    def commit(self) -> None:
        self.committed = True


def _current_user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4())


def _weekly_review_state(*, user_id, ready: bool, launched: bool) -> ImperiumWeeklyReviewState:
    return ImperiumWeeklyReviewState(
        id=uuid4(),
        user_id=user_id,
        week_start=date(2026, 4, 27),
        ready=ready,
        launched=launched,
        analysis_status="pending",
        created_at=datetime.now(UTC),
    )


def test_mark_weekly_review_ready_stores_http_200_metadata(monkeypatch) -> None:
    db = FakeSession()
    current_user = _current_user()
    state = _weekly_review_state(user_id=current_user.id, ready=False, launched=False)

    monkeypatch.setattr(weekly_review_state, "_get_existing_idempotency", lambda *args, **kwargs: None)
    monkeypatch.setattr(weekly_review_state, "_get_weekly_review_state", lambda *args, **kwargs: state)

    _result, duplicate = weekly_review_state.mark_weekly_review_ready(
        db,
        current_user=current_user,
        week_start=date(2026, 4, 27),
        idempotency_key="weekly-ready-key",
        request_method="POST",
        request_path="/api/internal/weekly-review/ready",
    )

    assert duplicate is False
    assert db.committed is True
    assert db.added[0].response_status_code == 200


def test_launch_weekly_review_stores_http_201_metadata(monkeypatch) -> None:
    db = FakeSession()
    current_user = _current_user()
    state = _weekly_review_state(user_id=current_user.id, ready=True, launched=False)

    monkeypatch.setattr(weekly_review_state, "_get_existing_idempotency", lambda *args, **kwargs: None)
    monkeypatch.setattr(weekly_review_state, "_get_weekly_review_state", lambda *args, **kwargs: state)

    _result, duplicate = weekly_review_state.launch_weekly_review(
        db,
        current_user=current_user,
        week_start=date(2026, 4, 27),
        idempotency_key="weekly-launch-key",
        request_method="POST",
        request_path="/api/imperium/weekly-review/launch",
    )

    assert duplicate is False
    assert db.committed is True
    assert db.added[0].response_status_code == 201
