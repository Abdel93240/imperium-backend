from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium_pulse
from app.models.imperium import ImperiumPulseEntry


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
    app.include_router(imperium_pulse.router, prefix="/imperium/pulse")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _entry(user_id, **overrides) -> ImperiumPulseEntry:
    now = overrides.pop("created_at", datetime(2026, 5, 25, 8, 0, tzinfo=UTC))
    return ImperiumPulseEntry(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        entry_date=overrides.pop("entry_date", date(2026, 5, 25)),
        sleep_hours=overrides.pop("sleep_hours", Decimal("7.50")),
        energy_level=overrides.pop("energy_level", 8),
        fatigue_level=overrides.pop("fatigue_level", 3),
        weight_kg=overrides.pop("weight_kg", Decimal("92.40")),
        workout_done=overrides.pop("workout_done", True),
        workout_type=overrides.pop("workout_type", "street_workout"),
        notes=overrides.pop("notes", "Good baseline day"),
        created_at=now,
        updated_at=overrides.pop("updated_at", now),
    )


def test_pulse_stats_summary_empty_returns_nulls_and_zeros() -> None:
    current_user = _user()
    db = FakeDb(scalars_results=[[]])

    response = _client(db, current_user).get("/imperium/pulse/stats/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["entry_count"] == 0
    assert body["average_sleep_hours"] is None
    assert body["average_energy_level"] is None
    assert body["average_fatigue_level"] is None
    assert body["latest_weight_kg"] is None
    assert body["workout_count"] == 0
    assert body["safe_explanation"] == "Pulse summary statistics for current user."


def test_pulse_stats_summary_computes_averages_and_workout_count() -> None:
    current_user = _user()
    entries = [
        _entry(
            current_user.id,
            entry_date=date(2026, 5, 27),
            sleep_hours=Decimal("7.20"),
            energy_level=7,
            fatigue_level=5,
            weight_kg=Decimal("91.70"),
            workout_done=True,
        ),
        _entry(
            current_user.id,
            entry_date=date(2026, 5, 26),
            sleep_hours=Decimal("7.50"),
            energy_level=8,
            fatigue_level=4,
            weight_kg=Decimal("91.90"),
            workout_done=False,
        ),
        _entry(
            current_user.id,
            entry_date=date(2026, 5, 25),
            sleep_hours=Decimal("7.35"),
            energy_level=6,
            fatigue_level=3,
            weight_kg=Decimal("92.10"),
            workout_done=True,
        ),
    ]
    db = FakeDb(scalars_results=[entries])

    response = _client(db, current_user).get("/imperium/pulse/stats/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["entry_count"] == 3
    assert body["average_sleep_hours"] == 7.35
    assert body["average_energy_level"] == 7.0
    assert body["average_fatigue_level"] == 4.0
    assert body["workout_count"] == 2


def test_pulse_stats_summary_ignores_null_values_in_averages() -> None:
    current_user = _user()
    entries = [
        _entry(current_user.id, sleep_hours=None, energy_level=None, fatigue_level=None),
        _entry(current_user.id, sleep_hours=Decimal("6.50"), energy_level=8, fatigue_level=None),
        _entry(current_user.id, sleep_hours=Decimal("7.50"), energy_level=None, fatigue_level=4),
    ]
    db = FakeDb(scalars_results=[entries])

    response = _client(db, current_user).get("/imperium/pulse/stats/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["entry_count"] == 3
    assert body["average_sleep_hours"] == 7.0
    assert body["average_energy_level"] == 8.0
    assert body["average_fatigue_level"] == 4.0


def test_pulse_stats_summary_returns_latest_weight_from_period() -> None:
    current_user = _user()
    entries = [
        _entry(current_user.id, entry_date=date(2026, 5, 25), weight_kg=None),
        _entry(current_user.id, entry_date=date(2026, 5, 24), weight_kg=Decimal("90.10")),
        _entry(current_user.id, entry_date=date(2026, 5, 23), weight_kg=Decimal("89.90")),
    ]
    db = FakeDb(scalars_results=[entries])

    response = _client(db, current_user).get("/imperium/pulse/stats/summary")

    assert response.status_code == 200
    assert response.json()["latest_weight_kg"] == 90.1


def test_pulse_stats_summary_latest_weight_uses_deterministic_order() -> None:
    current_user = _user()
    created_at = datetime(2026, 5, 25, 11, 0, tzinfo=UTC)
    first_id = UUID(int=1)
    second_id = UUID(int=2)
    entries = [
        _entry(
            current_user.id,
            id=first_id,
            entry_date=date(2026, 5, 25),
            created_at=created_at,
            weight_kg=Decimal("91.10"),
        ),
        _entry(
            current_user.id,
            id=second_id,
            entry_date=date(2026, 5, 25),
            created_at=created_at,
            weight_kg=Decimal("91.90"),
        ),
    ]
    db = FakeDb(scalars_results=[entries])

    response = _client(db, current_user).get("/imperium/pulse/stats/summary")

    assert response.status_code == 200
    assert response.json()["latest_weight_kg"] == 91.1
    query_text = "\n".join(str(query) for query in db.queries)
    assert "imperium_pulse_entries.entry_date DESC" in query_text
    assert "imperium_pulse_entries.created_at DESC" in query_text
    assert "imperium_pulse_entries.id ASC" in query_text


def test_pulse_stats_summary_workout_count_counts_only_true() -> None:
    current_user = _user()
    entries = [
        _entry(current_user.id, workout_done=True),
        _entry(current_user.id, workout_done=False),
        _entry(current_user.id, workout_done=None),
        _entry(current_user.id, workout_done=True),
    ]
    db = FakeDb(scalars_results=[entries])

    response = _client(db, current_user).get("/imperium/pulse/stats/summary")

    assert response.status_code == 200
    assert response.json()["workout_count"] == 2


def test_pulse_stats_summary_is_user_scoped_and_does_not_require_idempotency_key() -> None:
    current_user = _user()
    other_user = _user()
    own = _entry(current_user.id)
    foreign = _entry(other_user.id, notes="Foreign")
    db = FakeDb(scalars_results=[[own]])

    response = _client(db, current_user).get("/imperium/pulse/stats/summary")

    assert response.status_code == 200
    assert response.json()["entry_count"] == 1
    assert foreign.notes == "Foreign"
    query_text = "\n".join(str(query) for query in db.queries)
    assert "imperium_pulse_entries.user_id" in query_text
    assert "Idempotency-Key" not in query_text


def test_pulse_stats_summary_supports_date_filters() -> None:
    current_user = _user()
    entry = _entry(current_user.id)
    db = FakeDb(scalars_results=[[entry], [entry]])
    client = _client(db, current_user)

    from_response = client.get("/imperium/pulse/stats/summary?date_from=2026-05-01")
    to_response = client.get("/imperium/pulse/stats/summary?date_to=2026-05-31")

    assert from_response.status_code == 200
    assert to_response.status_code == 200
    query_text = "\n".join(str(query) for query in db.queries)
    assert "imperium_pulse_entries.entry_date" in query_text
    assert ">=" in query_text
    assert "<=" in query_text


def test_pulse_stats_summary_validates_date_range() -> None:
    response = _client(FakeDb(scalars_results=[[]]), _user()).get(
        "/imperium/pulse/stats/summary?date_from=2026-05-30&date_to=2026-05-01"
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "date_from must be before or equal to date_to."


def test_pulse_stats_summary_is_read_only_and_does_not_auto_create_or_modify_entries() -> None:
    current_user = _user()
    db = FakeDb(scalars_results=[[]])

    response = _client(db, current_user).get("/imperium/pulse/stats/summary")

    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False
    assert db.rolled_back is False


def test_pulse_stats_summary_no_ai_n8n_pgvector_memory_scoring_coaching_recommendations_or_cross_module_linkage() -> None:
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
        "automatic memory",
        "calendar",
        "replanning",
        "scoring",
        "discipline_score",
        "weighted_score",
        "coaching",
        "recommendation",
        "mission",
        "vault",
    ):
        assert forbidden not in combined
