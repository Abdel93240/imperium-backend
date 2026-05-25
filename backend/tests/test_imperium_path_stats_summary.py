from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium_path
from app.models.imperium import ImperiumPathCheckIn, ImperiumPathHabit


class FakeDb:
    def __init__(self, *, scalars_results=None) -> None:
        self.scalars_results = [list(result) for result in scalars_results] if scalars_results is not None else None
        self.added = []
        self.queries = []
        self.flushed = False
        self.committed = False
        self.rolled_back = False

    def add(self, obj) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed = True

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def scalars(self, query):
        self.queries.append(query)
        if self.scalars_results is not None:
            if self.scalars_results:
                return self.scalars_results.pop(0)
            return []
        return []


def _user(user_id=None) -> SimpleNamespace:
    return SimpleNamespace(id=user_id or uuid4())


def _client(db: FakeDb, current_user: SimpleNamespace) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_path.router, prefix="/imperium/path")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _habit(user_id, **overrides) -> ImperiumPathHabit:
    now = overrides.pop("created_at", datetime(2026, 5, 25, 8, 0, tzinfo=UTC))
    return ImperiumPathHabit(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        title=overrides.pop("title", "Fajr on time"),
        description=overrides.pop("description", "Pray before sunrise"),
        domain=overrides.pop("domain", "worship"),
        frequency=overrides.pop("frequency", "daily"),
        is_active=overrides.pop("is_active", True),
        created_at=now,
        updated_at=overrides.pop("updated_at", now),
    )


def _check_in(user_id, habit_id, **overrides) -> ImperiumPathCheckIn:
    now = overrides.pop("created_at", datetime(2026, 5, 25, 9, 0, tzinfo=UTC))
    return ImperiumPathCheckIn(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        habit_id=habit_id,
        check_date=overrides.pop("check_date", date(2026, 5, 25)),
        status=overrides.pop("status", "done"),
        reason=overrides.pop("reason", None),
        note=overrides.pop("note", "Completed"),
        created_at=now,
        updated_at=overrides.pop("updated_at", now),
    )


def test_path_stats_summary_returns_zeros_for_empty_results() -> None:
    current_user = _user()
    db = FakeDb(scalars_results=[[], []])

    response = _client(db, current_user).get("/imperium/path/stats/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["date_from"] is None
    assert body["date_to"] is None
    assert body["domain"] is None
    assert body["frequency"] is None
    assert body["total_active_habits"] == 0
    assert body["done_count"] == 0
    assert body["missed_count"] == 0
    assert body["check_in_count"] == 0
    assert body["completion_rate_percent"] == 0.0
    assert body["safe_explanation"] == "Path summary stats computed from current user's habits and check-ins."


def test_path_stats_summary_counts_active_habits_and_ignores_pending_implicits() -> None:
    current_user = _user()
    active_habit = _habit(current_user.id, is_active=True)
    db = FakeDb(scalars_results=[[active_habit], []])

    response = _client(db, current_user).get("/imperium/path/stats/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total_active_habits"] == 1
    assert body["done_count"] == 0
    assert body["missed_count"] == 0
    assert body["check_in_count"] == 0
    assert body["completion_rate_percent"] == 0.0
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False
    assert db.rolled_back is False


def test_path_stats_summary_counts_done_missed_and_completion_rate_from_existing_check_ins() -> None:
    current_user = _user()
    active_habit = _habit(current_user.id, title="Fajr on time", domain="worship", frequency="daily", is_active=True)
    inactive_habit = _habit(
        current_user.id,
        title="Quran reading",
        domain="worship",
        frequency="daily",
        is_active=False,
    )
    done_check_ins = [_check_in(current_user.id, active_habit.id, status="done") for _ in range(10)]
    missed_check_ins = [
        _check_in(current_user.id, active_habit.id, status="missed", reason="Overslept", note=None),
        _check_in(current_user.id, inactive_habit.id, status="missed", reason="Overslept", note=None),
    ]
    db = FakeDb(scalars_results=[[active_habit], [*done_check_ins, *missed_check_ins]])

    response = _client(db, current_user).get("/imperium/path/stats/summary?domain=worship&frequency=daily")

    assert response.status_code == 200
    body = response.json()
    assert body["domain"] == "worship"
    assert body["frequency"] == "daily"
    assert body["total_active_habits"] == 1
    assert body["done_count"] == 10
    assert body["missed_count"] == 2
    assert body["check_in_count"] == 12
    assert body["completion_rate_percent"] == 83.33


def test_path_stats_summary_is_strictly_user_scoped_and_does_not_require_idempotency_key() -> None:
    current_user = _user()
    other_user = _user()
    own_habit = _habit(current_user.id)
    foreign_habit = _habit(other_user.id, title="Foreign habit")
    own_check_in = _check_in(current_user.id, own_habit.id)
    foreign_check_in = _check_in(other_user.id, foreign_habit.id)
    db = FakeDb(scalars_results=[[own_habit], [own_check_in]])

    response = _client(db, current_user).get("/imperium/path/stats/summary")

    assert response.status_code == 200
    query_text = "\n".join(str(query) for query in db.queries)
    assert "imperium_path_habits.user_id" in query_text
    assert "imperium_path_check_ins.user_id" in query_text
    assert "Idempotency-Key" not in query_text
    assert foreign_habit.user_id == other_user.id
    assert foreign_check_in.user_id == other_user.id


def test_path_stats_summary_filters_date_from() -> None:
    current_user = _user()
    habit = _habit(current_user.id)
    db = FakeDb(scalars_results=[[habit], []])

    response = _client(db, current_user).get("/imperium/path/stats/summary?date_from=2026-05-10")

    assert response.status_code == 200
    body = response.json()
    assert body["date_from"] == "2026-05-10"
    assert body["check_in_count"] == 0
    query_text = "\n".join(str(query) for query in db.queries)
    assert "imperium_path_check_ins.check_date" in query_text
    assert ">=" in query_text


def test_path_stats_summary_filters_date_to() -> None:
    current_user = _user()
    habit = _habit(current_user.id)
    db = FakeDb(scalars_results=[[habit], []])

    response = _client(db, current_user).get("/imperium/path/stats/summary?date_to=2026-05-20")

    assert response.status_code == 200
    body = response.json()
    assert body["date_to"] == "2026-05-20"
    assert body["check_in_count"] == 0
    query_text = "\n".join(str(query) for query in db.queries)
    assert "imperium_path_check_ins.check_date" in query_text
    assert "<=" in query_text


def test_path_stats_summary_filters_domain() -> None:
    current_user = _user()
    habit = _habit(current_user.id, domain="worship")
    db = FakeDb(scalars_results=[[habit], []])

    response = _client(db, current_user).get("/imperium/path/stats/summary?domain=worship")

    assert response.status_code == 200
    body = response.json()
    assert body["domain"] == "worship"
    query_text = "\n".join(str(query) for query in db.queries)
    assert "imperium_path_habits.domain" in query_text


def test_path_stats_summary_filters_frequency() -> None:
    current_user = _user()
    habit = _habit(current_user.id, frequency="weekly")
    db = FakeDb(scalars_results=[[habit], []])

    response = _client(db, current_user).get("/imperium/path/stats/summary?frequency=weekly")

    assert response.status_code == 200
    body = response.json()
    assert body["frequency"] == "weekly"
    query_text = "\n".join(str(query) for query in db.queries)
    assert "imperium_path_habits.frequency" in query_text


def test_path_stats_summary_is_read_only_and_does_not_create_check_ins() -> None:
    current_user = _user()
    habit = _habit(current_user.id)
    check_in = _check_in(current_user.id, habit.id)
    db = FakeDb(scalars_results=[[habit], [check_in]])

    response = _client(db, current_user).get("/imperium/path/stats/summary")

    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False
    assert db.rolled_back is False
