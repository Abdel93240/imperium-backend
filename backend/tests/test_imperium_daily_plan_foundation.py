from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.router import api_router
from app.models.imperium import ImperiumMission, ImperiumPathCheckIn, ImperiumPathHabit, ImperiumPulseEntry
from app.services.imperium import daily_plan as daily_plan_service


BACKEND_ROOT = Path(__file__).resolve().parents[1]


class FakeDb:
    def __init__(self, *, scalar_results=None, scalars_results=None) -> None:
        self.scalar_results = list(scalar_results or [])
        self.scalars_results = [list(result) for result in scalars_results] if scalars_results is not None else []
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

    def scalars(self, query):
        self.queries.append(query)
        if self.scalars_results:
            return self.scalars_results.pop(0)
        return []


def _user(user_id=None) -> SimpleNamespace:
    return SimpleNamespace(id=user_id or uuid4())


def _client(db: FakeDb, current_user: SimpleNamespace) -> TestClient:
    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _mission(user_id, **overrides) -> ImperiumMission:
    now = overrides.pop("created_at", datetime(2026, 5, 25, 8, 0, tzinfo=UTC))
    return ImperiumMission(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        title=overrides.pop("title", "Drive focused VTC block"),
        category=overrides.pop("category", "vtc"),
        domain=overrides.pop("domain", "business"),
        priority_level=overrides.pop("priority_level", 2),
        mission_type_category=overrides.pop("mission_type_category", "cat_a"),
        status=overrides.pop("status", "active"),
        planned_start_at=overrides.pop("planned_start_at", None),
        planned_end_at=overrides.pop("planned_end_at", None),
        started_at=overrides.pop("started_at", now),
        ended_at=overrides.pop("ended_at", None),
        created_at=now,
        updated_at=overrides.pop("updated_at", now),
    )


def _habit(user_id, **overrides) -> ImperiumPathHabit:
    now = overrides.pop("created_at", datetime(2026, 5, 25, 6, 0, tzinfo=UTC))
    return ImperiumPathHabit(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        title=overrides.pop("title", "Fajr on time"),
        description=overrides.pop("description", None),
        domain=overrides.pop("domain", "worship"),
        frequency=overrides.pop("frequency", "daily"),
        is_active=overrides.pop("is_active", True),
        created_at=now,
        updated_at=overrides.pop("updated_at", now),
    )


def _check_in(user_id, habit_id, **overrides) -> ImperiumPathCheckIn:
    now = overrides.pop("created_at", datetime(2026, 5, 25, 6, 30, tzinfo=UTC))
    return ImperiumPathCheckIn(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        habit_id=habit_id,
        check_date=overrides.pop("check_date", date(2026, 5, 25)),
        status=overrides.pop("status", "done"),
        reason=overrides.pop("reason", None),
        note=overrides.pop("note", "Done"),
        created_at=now,
        updated_at=overrides.pop("updated_at", now),
    )


def _pulse_entry(user_id, **overrides) -> ImperiumPulseEntry:
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


def _empty_daily_plan_db() -> FakeDb:
    return FakeDb(scalar_results=[None, None], scalars_results=[[], [], [], [], [], [], []])


def _assert_no_user_id(value) -> None:
    if isinstance(value, dict):
        assert "user_id" not in value
        for child in value.values():
            _assert_no_user_id(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_user_id(child)


def test_daily_plan_route_is_registered_before_legacy_imperium_routes() -> None:
    api_router_text = (BACKEND_ROOT / "app" / "api" / "v1" / "router.py").read_text(encoding="utf-8")
    route_text = (
        BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_daily_plan.py"
    ).read_text(encoding="utf-8")
    legacy_route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium.py").read_text(
        encoding="utf-8"
    )

    assert api_router_text.index("imperium_daily_plan.router") < api_router_text.index("imperium.router")
    assert '@router.get("/daily-plan"' in route_text
    assert '@router.get("/daily-plan"' not in legacy_route_text
    assert 'api_router.include_router(imperium_daily_plan.router, prefix="/imperium", tags=["imperium-daily-plan"])' in api_router_text


def test_daily_plan_contract_shape_and_query_params() -> None:
    response = _client(_empty_daily_plan_db(), _user()).get("/api/imperium/daily-plan")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "date",
        "dashboard",
        "mission",
        "path",
        "pulse",
        "summary",
        "meta",
        "safe_explanation",
    }
    assert body["dashboard"]["meta"]["dashboard_version"] == "v1"
    assert body["dashboard"]["meta"]["read_only"] is True
    assert body["mission"]["mission"] is None
    assert body["path"]["count"] == 0
    assert body["pulse"]["entry"] is None
    assert body["summary"] == {
        "has_active_mission": False,
        "path_items_count": 0,
        "pulse_entry_present": False,
        "safe_explanation": "Daily plan summary computed from existing read-only snapshots.",
    }
    assert body["meta"]["daily_plan_version"] == "v1"
    assert body["meta"]["read_only"] is True
    assert body["meta"]["safe_explanation"] == "Daily plan metadata snapshot."
    assert body["safe_explanation"] == "Imperium daily plan snapshot for current user."


def test_daily_plan_default_date_uses_europe_paris_helper(monkeypatch) -> None:
    monkeypatch.setattr(daily_plan_service, "get_default_local_date", lambda: date(2026, 5, 26))

    response = _client(_empty_daily_plan_db(), _user()).get("/api/imperium/daily-plan")

    assert response.status_code == 200
    body = response.json()
    assert body["date"] == "2026-05-26"
    assert body["dashboard"]["date"] == "2026-05-26"
    assert body["path"]["date"] == "2026-05-26"
    assert body["pulse"]["date"] == "2026-05-26"


def test_daily_plan_query_date_overrides_default_date() -> None:
    response = _client(_empty_daily_plan_db(), _user()).get("/api/imperium/daily-plan?date=2026-05-24")

    assert response.status_code == 200
    body = response.json()
    assert body["date"] == "2026-05-24"
    assert body["dashboard"]["date"] == "2026-05-24"
    assert body["path"]["date"] == "2026-05-24"
    assert body["pulse"]["date"] == "2026-05-24"


def test_daily_plan_propagates_active_mission_path_and_pulse_today() -> None:
    current_user = _user()
    mission = _mission(current_user.id)
    habit = _habit(current_user.id)
    check_in = _check_in(current_user.id, habit.id)
    entry = _pulse_entry(current_user.id)
    db = FakeDb(
        scalar_results=[entry, entry],
        scalars_results=[[mission], [], [habit], [check_in], [mission], [habit], [check_in]],
    )

    response = _client(db, current_user).get("/api/imperium/daily-plan")

    assert response.status_code == 200
    body = response.json()
    assert body["mission"]["mission"]["id"] == str(mission.id)
    assert body["mission"]["safe_explanation"] == "Current active mission for user."
    assert body["path"]["items"][0]["habit"]["title"] == "Fajr on time"
    assert body["path"]["count"] == 1
    assert body["pulse"]["entry"]["id"] == str(entry.id)
    assert body["pulse"]["entry"]["notes"] == "Good baseline day"
    assert body["summary"] == {
        "has_active_mission": True,
        "path_items_count": 1,
        "pulse_entry_present": True,
        "safe_explanation": "Daily plan summary computed from existing read-only snapshots.",
    }
    assert body["dashboard"]["mission"]["active_mission"]["id"] == str(mission.id)
    assert body["dashboard"]["path"]["count"] == 1
    assert body["dashboard"]["pulse"]["entry"]["id"] == str(entry.id)
    assert "user_id" not in body["mission"]["mission"]
    assert "user_id" not in body["path"]["items"][0]["habit"]
    assert "user_id" not in body["pulse"]["entry"]
    assert "user_id" not in body["dashboard"]
    assert "imperium_missions.user_id" in "\n".join(str(query) for query in db.queries)
    assert "imperium_path_habits.user_id" in "\n".join(str(query) for query in db.queries)
    assert "imperium_pulse_entries.user_id" in "\n".join(str(query) for query in db.queries)


def test_daily_plan_is_strictly_user_scoped_and_does_not_require_idempotency_key() -> None:
    current_user = _user()
    other_user = _user()
    own_mission = _mission(current_user.id)
    own_habit = _habit(current_user.id)
    own_check_in = _check_in(current_user.id, own_habit.id)
    own_entry = _pulse_entry(current_user.id)
    foreign_mission = _mission(other_user.id, title="Foreign mission")
    foreign_habit = _habit(other_user.id, title="Foreign habit")
    foreign_entry = _pulse_entry(other_user.id, notes="Foreign pulse")
    db = FakeDb(
        scalar_results=[own_entry, own_entry],
        scalars_results=[[own_mission], [], [own_habit], [own_check_in], [own_mission], [own_habit], [own_check_in]],
    )

    response = _client(db, current_user).get("/api/imperium/daily-plan")

    assert response.status_code == 200
    body = response.json()
    assert body["mission"]["mission"]["title"] == own_mission.title
    assert body["path"]["items"][0]["habit"]["title"] == own_habit.title
    assert body["pulse"]["entry"]["notes"] == own_entry.notes
    assert foreign_mission.title != body["mission"]["mission"]["title"]
    assert foreign_habit.title != body["path"]["items"][0]["habit"]["title"]
    assert foreign_entry.notes != body["pulse"]["entry"]["notes"]
    query_text = "\n".join(str(query) for query in db.queries)
    assert "imperium_missions.user_id" in query_text
    assert "imperium_path_habits.user_id" in query_text
    assert "imperium_path_check_ins.user_id" in query_text
    assert "imperium_pulse_entries.user_id" in query_text


def test_daily_plan_is_read_only_and_does_not_auto_create_rows() -> None:
    db = _empty_daily_plan_db()
    response = _client(db, _user()).get("/api/imperium/daily-plan")

    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False
    assert db.rolled_back is False


def test_daily_plan_does_not_expose_user_id_and_has_utc_metadata() -> None:
    response = _client(_empty_daily_plan_db(), _user()).get("/api/imperium/daily-plan")

    assert response.status_code == 200
    body = response.json()
    _assert_no_user_id(body)
    snapshot_generated_at = datetime.fromisoformat(body["meta"]["snapshot_generated_at"])
    assert snapshot_generated_at.tzinfo is not None
    assert snapshot_generated_at.utcoffset() == timedelta(0)
    assert abs((datetime.now(UTC) - snapshot_generated_at).total_seconds()) < 10
    dashboard_generated_at = datetime.fromisoformat(body["dashboard"]["meta"]["snapshot_generated_at"])
    assert dashboard_generated_at.tzinfo is not None
    assert dashboard_generated_at.utcoffset() == timedelta(0)


def test_daily_plan_does_not_introduce_ai_n8n_pgvector_memory_or_cross_module_linkage() -> None:
    route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_daily_plan.py").read_text(
        encoding="utf-8"
    )
    service_text = (BACKEND_ROOT / "app" / "services" / "imperium" / "daily_plan.py").read_text(encoding="utf-8")
    schema_text = (BACKEND_ROOT / "app" / "schemas" / "daily_plan.py").read_text(encoding="utf-8")
    lowered = "\n".join([route_text, service_text, schema_text]).lower()

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
        "pgvector",
        "embedding",
        "ai_memories",
        "memory commit",
        "ocr",
        "replanning",
        "scoring",
        "coaching",
        "recommendation",
        "health_score",
        "calendar",
        "db.add(",
        "db.flush",
        "db.commit",
        "cross-module",
    ):
        assert forbidden not in lowered


def test_daily_plan_does_not_use_legacy_dashboard_aggregator() -> None:
    service_text = (BACKEND_ROOT / "app" / "services" / "imperium" / "daily_plan.py").read_text(encoding="utf-8")

    assert "get_dashboard_snapshot" not in service_text
    assert "legacy dashboard aggregator" not in service_text.lower()
    assert "get_imperium_dashboard_foundation" in service_text
