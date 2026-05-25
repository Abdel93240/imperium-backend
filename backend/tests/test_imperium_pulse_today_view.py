from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium_pulse
from app.models.imperium import ImperiumPulseEntry


BACKEND_ROOT = Path(__file__).resolve().parents[1]


class FakeDb:
    def __init__(self, *, scalar_results=None) -> None:
        self.scalar_results = list(scalar_results or [])
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

    def scalar(self, query):
        self.queries.append(query)
        if self.scalar_results:
            return self.scalar_results.pop(0)
        return None


def _user(user_id=None) -> SimpleNamespace:
    return SimpleNamespace(id=user_id or uuid4())


def _client(db: FakeDb, current_user: SimpleNamespace) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_pulse.router, prefix="/imperium/pulse")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _entry(user_id, **overrides) -> ImperiumPulseEntry:
    now = overrides.pop("created_at", datetime(2026, 5, 25, 7, 0, tzinfo=UTC))
    return ImperiumPulseEntry(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        entry_date=overrides.pop("entry_date", date(2026, 5, 25)),
        sleep_hours=overrides.pop("sleep_hours", 7.5),
        energy_level=overrides.pop("energy_level", 8),
        fatigue_level=overrides.pop("fatigue_level", 3),
        weight_kg=overrides.pop("weight_kg", 92.4),
        workout_done=overrides.pop("workout_done", True),
        workout_type=overrides.pop("workout_type", "street_workout"),
        notes=overrides.pop("notes", "Good baseline day"),
        created_at=now,
        updated_at=overrides.pop("updated_at", now),
    )


def test_pulse_today_default_date_uses_europe_paris_helper(monkeypatch) -> None:
    current_user = _user()
    db = FakeDb(scalar_results=[None])
    monkeypatch.setattr(imperium_pulse, "get_default_local_date", lambda: date(2026, 5, 26))

    response = _client(db, current_user).get("/imperium/pulse/today")

    assert response.status_code == 200
    body = response.json()
    assert body["date"] == "2026-05-26"
    assert body["entry"] is None
    assert body["safe_explanation"] == "Pulse today entry for current user."


def test_pulse_today_returns_existing_entry_for_current_user() -> None:
    current_user = _user()
    entry = _entry(current_user.id)
    db = FakeDb(scalar_results=[entry])

    response = _client(db, current_user).get("/imperium/pulse/today")

    assert response.status_code == 200
    body = response.json()
    assert body["entry"]["id"] == str(entry.id)
    assert body["entry"]["entry_date"] == entry.entry_date.isoformat()
    assert body["entry"]["sleep_hours"] == 7.5
    assert body["entry"]["energy_level"] == 8
    assert "user_id" not in body["entry"]


def test_pulse_today_never_returns_other_user_entry() -> None:
    current_user = _user()
    other_user = _user()
    own = _entry(current_user.id, notes="Own")
    foreign = _entry(other_user.id, notes="Foreign")
    db = FakeDb(scalar_results=[own])

    response = _client(db, current_user).get("/imperium/pulse/today")

    assert response.status_code == 200
    assert response.json()["entry"]["notes"] == "Own"
    assert response.json()["entry"]["notes"] != foreign.notes
    query_text = "\n".join(str(query) for query in db.queries)
    assert "imperium_pulse_entries.user_id" in query_text


def test_pulse_today_supports_date_query_param() -> None:
    current_user = _user()
    entry = _entry(current_user.id, entry_date=date(2026, 5, 24))
    db = FakeDb(scalar_results=[entry])

    response = _client(db, current_user).get("/imperium/pulse/today?date=2026-05-24")

    assert response.status_code == 200
    body = response.json()
    assert body["date"] == "2026-05-24"
    assert body["entry"]["entry_date"] == "2026-05-24"
    assert "imperium_pulse_entries.entry_date" in "\n".join(str(query) for query in db.queries)


def test_pulse_today_does_not_require_idempotency_key() -> None:
    response = _client(FakeDb(scalar_results=[None]), _user()).get("/imperium/pulse/today")

    assert response.status_code == 200


def test_pulse_today_is_read_only_and_does_not_auto_create_entry() -> None:
    current_user = _user()
    db = FakeDb(scalar_results=[None])

    response = _client(db, current_user).get("/imperium/pulse/today")

    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False
    assert db.rolled_back is False


def test_pulse_today_does_not_introduce_ai_n8n_pgvector_memory_or_cross_module_linkage() -> None:
    route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_pulse.py").read_text(encoding="utf-8")
    service_text = (BACKEND_ROOT / "app" / "services" / "pulse" / "entries.py").read_text(encoding="utf-8")
    schema_text = (BACKEND_ROOT / "app" / "schemas" / "pulse.py").read_text(encoding="utf-8")
    combined = "\n".join([route_text, service_text, schema_text]).lower()

    for forbidden in (
        "qwenclient",
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
        "memory commit",
        "calendar",
        "replanning",
        "weighted_score",
        "coaching",
        "mission_id",
        "vault",
    ):
        assert forbidden not in combined
