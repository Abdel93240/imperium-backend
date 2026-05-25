from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium_path
from app.models.imperium import ImperiumPathCheckIn, ImperiumPathHabit


BACKEND_ROOT = Path(__file__).resolve().parents[1]


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


def _assert_habit_body(body: dict, habit: ImperiumPathHabit) -> None:
    assert body["id"] == str(habit.id)
    assert body["title"] == habit.title
    assert body["description"] == habit.description
    assert body["domain"] == habit.domain
    assert body["frequency"] == habit.frequency
    assert body["is_active"] is True
    assert body["created_at"] == habit.created_at.isoformat().replace("+00:00", "Z")
    assert body["updated_at"] == habit.updated_at.isoformat().replace("+00:00", "Z")
    assert "user_id" not in body


def _assert_check_in_body(body: dict, check_in: ImperiumPathCheckIn) -> None:
    assert body["id"] == str(check_in.id)
    assert body["habit_id"] == str(check_in.habit_id)
    assert body["check_date"] == check_in.check_date.isoformat()
    assert body["status"] == check_in.status
    assert body["reason"] == check_in.reason
    assert body["note"] == check_in.note
    assert body["created_at"] == check_in.created_at.isoformat().replace("+00:00", "Z")
    assert "user_id" not in body


def test_get_path_today_default_date_uses_europe_paris_helper(monkeypatch) -> None:
    current_user = _user()
    habit = _habit(current_user.id)
    db = FakeDb(scalars_results=[[habit], []])
    monkeypatch.setattr(imperium_path, "get_default_local_date", lambda: date(2026, 5, 26))

    response = _client(db, current_user).get("/imperium/path/today")

    assert response.status_code == 200
    body = response.json()
    assert body["date"] == "2026-05-26"
    assert body["count"] == 1
    assert body["safe_explanation"] == "Path today view for current user."
    assert body["items"][0]["status"] == "pending"
    _assert_habit_body(body["items"][0]["habit"], habit)
    assert body["items"][0]["check_in"] is None
    assert len(db.queries) == 2


def test_get_path_today_returns_done_when_done_check_in_exists() -> None:
    current_user = _user()
    habit = _habit(current_user.id)
    check_in = _check_in(current_user.id, habit.id, status="done", reason=None, note="Completed after fajr")
    db = FakeDb(scalars_results=[[habit], [check_in]])

    response = _client(db, current_user).get("/imperium/path/today")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["status"] == "done"
    _assert_habit_body(body["items"][0]["habit"], habit)
    _assert_check_in_body(body["items"][0]["check_in"], check_in)


def test_get_path_today_returns_missed_when_missed_check_in_exists() -> None:
    current_user = _user()
    habit = _habit(current_user.id)
    check_in = _check_in(current_user.id, habit.id, status="missed", reason="Overslept", note=None)
    db = FakeDb(scalars_results=[[habit], [check_in]])

    response = _client(db, current_user).get("/imperium/path/today")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["status"] == "missed"
    _assert_check_in_body(body["items"][0]["check_in"], check_in)


def test_get_path_today_excludes_inactive_habits() -> None:
    current_user = _user()
    active = _habit(current_user.id, title="Fajr on time")
    inactive = _habit(current_user.id, title="Daily reading", is_active=False)
    db = FakeDb(scalars_results=[[active], []])

    response = _client(db, current_user).get("/imperium/path/today")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["habit"]["title"] == "Fajr on time"
    assert inactive.title != body["items"][0]["habit"]["title"]
    assert "imperium_path_habits.is_active" in "\n".join(str(query) for query in db.queries)


def test_get_path_today_is_strictly_user_scoped_and_does_not_require_idempotency_key() -> None:
    current_user = _user()
    other_user = _user()
    own = _habit(current_user.id)
    foreign = _habit(other_user.id, title="Foreign habit")
    db = FakeDb(scalars_results=[[own], []])

    response = _client(db, current_user).get("/imperium/path/today")

    assert response.status_code == 200
    assert response.json()["items"][0]["habit"]["title"] == own.title
    query_text = "\n".join(str(query) for query in db.queries)
    assert "imperium_path_habits.user_id" in query_text
    assert "imperium_path_check_ins.user_id" in query_text
    assert "Idempotency-Key" not in query_text
    assert foreign.title != response.json()["items"][0]["habit"]["title"]


def test_get_path_today_filters_domain_and_frequency_and_supports_date_query_param() -> None:
    current_user = _user()
    habit = _habit(current_user.id, domain="worship", frequency="weekly")
    check_in = _check_in(current_user.id, habit.id, check_date=date(2026, 5, 24), status="done")
    db = FakeDb(scalars_results=[[habit], [check_in]])

    response = _client(db, current_user).get("/imperium/path/today?date=2026-05-24&domain=worship&frequency=weekly")

    assert response.status_code == 200
    body = response.json()
    assert body["date"] == "2026-05-24"
    assert body["items"][0]["habit"]["domain"] == "worship"
    assert body["items"][0]["habit"]["frequency"] == "weekly"
    query_text = "\n".join(str(query) for query in db.queries)
    assert "imperium_path_habits.domain" in query_text
    assert "imperium_path_habits.frequency" in query_text
    assert "imperium_path_check_ins.check_date" in query_text


def test_get_path_today_is_read_only_and_does_not_create_check_ins() -> None:
    current_user = _user()
    habit = _habit(current_user.id)
    db = FakeDb(scalars_results=[[habit], []])

    response = _client(db, current_user).get("/imperium/path/today")

    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False
    assert db.rolled_back is False


def test_get_path_today_returns_deterministic_order_by_created_at_then_id() -> None:
    current_user = _user()
    first = _habit(
        current_user.id,
        id=UUID(int=1),
        title="First",
        created_at=datetime(2026, 5, 24, 8, 0, tzinfo=UTC),
    )
    second = _habit(
        current_user.id,
        id=UUID(int=2),
        title="Second",
        created_at=datetime(2026, 5, 24, 8, 0, tzinfo=UTC),
    )
    db = FakeDb(scalars_results=[[first, second], []])

    response = _client(db, current_user).get("/imperium/path/today?date=2026-05-24")

    assert response.status_code == 200
    body = response.json()
    assert [item["habit"]["id"] for item in body["items"]] == [str(first.id), str(second.id)]
    query_text = str(db.queries[0])
    lowered_query_text = query_text.lower()
    assert "order by" in lowered_query_text
    assert "imperium_path_habits.created_at" in lowered_query_text
    assert "imperium_path_habits.id" in lowered_query_text


def test_get_path_today_does_not_introduce_ai_n8n_pgvector_memory_calendar_scoring_or_mission_vault_logic() -> None:
    route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_path.py").read_text(encoding="utf-8").lower()
    service_text = (BACKEND_ROOT / "app" / "services" / "path" / "habits.py").read_text(encoding="utf-8").lower()
    schema_text = (BACKEND_ROOT / "app" / "schemas" / "path.py").read_text(encoding="utf-8").lower()
    combined = "\n".join([route_text, service_text, schema_text])

    for forbidden in (
        "qwenclient",
        "providers",
        "openai",
        "anthropic",
        "gemini",
        "claude",
        "n8n_client",
        "trigger_n8n",
        "ai agent",
        "aiagent",
        "n8n-nodes-langchain.agent",
        "pgvector",
        "embedding",
        "ai_memories",
        "automatic memory",
        "memory commit",
        "calendar",
        "replanning",
        "discipline_score",
        "weighted_score",
        "mission_id",
        "vault",
    ):
        assert forbidden not in combined
