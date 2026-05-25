from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium
from app.models.imperium import ImperiumMission


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

    def scalars(self, query):
        self.queries.append(query)
        return []


def _user(user_id=None) -> SimpleNamespace:
    return SimpleNamespace(id=user_id or uuid4())


def _client(db: FakeDb, current_user: SimpleNamespace) -> TestClient:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _mission(user_id, **overrides) -> ImperiumMission:
    now = datetime.now(UTC)
    mission = ImperiumMission(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        title=overrides.pop("title", "Mission detail"),
        category=overrides.pop("category", None),
        domain=overrides.pop("domain", "business"),
        priority_level=overrides.pop("priority_level", 3),
        mission_type_category=overrides.pop("mission_type_category", None),
        status=overrides.pop("status", "backlog"),
        planned_start_at=overrides.pop("planned_start_at", None),
        planned_end_at=overrides.pop("planned_end_at", None),
        started_at=overrides.pop("started_at", now),
        ended_at=overrides.pop("ended_at", None),
        created_at=overrides.pop("created_at", now),
        updated_at=overrides.pop("updated_at", now),
    )
    for key, value in overrides.items():
        setattr(mission, key, value)
    return mission


def test_mission_detail_returns_backlog_mission_for_current_user() -> None:
    current_user = _user()
    started_at = datetime(2026, 5, 25, 7, 45, tzinfo=UTC)
    created_at = datetime(2026, 5, 25, 7, 40, tzinfo=UTC)
    updated_at = datetime(2026, 5, 25, 7, 50, tzinfo=UTC)
    mission = _mission(
        current_user.id,
        status="backlog",
        started_at=started_at,
        created_at=created_at,
        updated_at=updated_at,
    )
    setattr(mission, "weighted_score", 80)
    setattr(mission, "coefficient", 8)
    setattr(mission, "ai_usable_reason", True)
    db = FakeDb(scalar_results=[mission])

    response = _client(db, current_user).get(f"/imperium/missions/{mission.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["safe_explanation"] == "Mission detail for current user."
    assert body["mission"]["id"] == str(mission.id)
    assert body["mission"]["status"] == "backlog"
    assert body["mission"]["created_at"] == created_at.isoformat().replace("+00:00", "Z")
    assert body["mission"]["updated_at"] == updated_at.isoformat().replace("+00:00", "Z")
    assert "started_at" not in body["mission"]
    assert "ended_at" not in body["mission"]
    assert "weighted_score" not in body["mission"]
    assert "coefficient" not in body["mission"]
    assert "ai_usable_reason" not in body["mission"]
    assert mission.status == "backlog"
    assert mission.started_at == started_at
    assert mission.ended_at is None
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_mission_detail_returns_active_mission_for_current_user() -> None:
    current_user = _user()
    started_at = datetime(2026, 5, 25, 8, 0, tzinfo=UTC)
    created_at = datetime(2026, 5, 25, 7, 55, tzinfo=UTC)
    updated_at = datetime(2026, 5, 25, 8, 5, tzinfo=UTC)
    mission = _mission(
        current_user.id,
        status="active",
        started_at=started_at,
        created_at=created_at,
        updated_at=updated_at,
    )
    db = FakeDb(scalar_results=[mission])

    response = _client(db, current_user).get(f"/imperium/missions/{mission.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["mission"]["status"] == "active"
    assert body["mission"]["started_at"] == started_at.isoformat().replace("+00:00", "Z")
    assert body["mission"]["created_at"] == created_at.isoformat().replace("+00:00", "Z")
    assert body["mission"]["updated_at"] == updated_at.isoformat().replace("+00:00", "Z")
    assert "ended_at" not in body["mission"]
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_mission_detail_returns_completed_mission_for_current_user() -> None:
    current_user = _user()
    started_at = datetime(2026, 5, 24, 20, 0, tzinfo=UTC)
    ended_at = datetime(2026, 5, 24, 22, 0, tzinfo=UTC)
    mission = _mission(
        current_user.id,
        status="completed",
        started_at=started_at,
        ended_at=ended_at,
    )
    db = FakeDb(scalar_results=[mission])

    response = _client(db, current_user).get(f"/imperium/missions/{mission.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["mission"]["status"] == "completed"
    assert body["mission"]["started_at"] == started_at.isoformat().replace("+00:00", "Z")
    assert body["mission"]["ended_at"] == ended_at.isoformat().replace("+00:00", "Z")
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_mission_detail_returns_failed_mission_for_current_user() -> None:
    current_user = _user()
    started_at = datetime(2026, 5, 24, 18, 0, tzinfo=UTC)
    ended_at = datetime(2026, 5, 24, 19, 0, tzinfo=UTC)
    mission = _mission(
        current_user.id,
        status="failed",
        started_at=started_at,
        ended_at=ended_at,
    )
    setattr(mission, "failure_reason", "Traffic")
    setattr(mission, "user_reported_signals", {"traffic": "heavy"})
    db = FakeDb(scalar_results=[mission])

    response = _client(db, current_user).get(f"/imperium/missions/{mission.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["mission"]["status"] == "failed"
    assert body["mission"]["started_at"] == started_at.isoformat().replace("+00:00", "Z")
    assert body["mission"]["ended_at"] == ended_at.isoformat().replace("+00:00", "Z")
    assert "failure_reason" not in body["mission"]
    assert "user_reported_signals" not in body["mission"]
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_mission_detail_returns_abandoned_mission_for_current_user() -> None:
    current_user = _user()
    started_at = datetime(2026, 5, 23, 18, 0, tzinfo=UTC)
    ended_at = datetime(2026, 5, 23, 18, 30, tzinfo=UTC)
    mission = _mission(
        current_user.id,
        status="abandoned",
        started_at=started_at,
        ended_at=ended_at,
    )
    db = FakeDb(scalar_results=[mission])

    response = _client(db, current_user).get(f"/imperium/missions/{mission.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["mission"]["status"] == "abandoned"
    assert body["mission"]["started_at"] == started_at.isoformat().replace("+00:00", "Z")
    assert body["mission"]["ended_at"] == ended_at.isoformat().replace("+00:00", "Z")
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_mission_detail_returns_404_for_missing_mission() -> None:
    current_user = _user()
    db = FakeDb(scalar_results=[None])

    response = _client(db, current_user).get(f"/imperium/missions/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Mission not found."
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_mission_detail_returns_404_for_foreign_mission() -> None:
    current_user = _user()
    foreign_user_id = uuid4()
    mission = _mission(foreign_user_id, status="active")
    db = FakeDb(scalar_results=[None])

    response = _client(db, current_user).get(f"/imperium/missions/{mission.id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Mission not found."
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_mission_detail_does_not_require_idempotency_key() -> None:
    current_user = _user()
    mission = _mission(current_user.id, status="active")
    db = FakeDb(scalar_results=[mission])

    response = _client(db, current_user).get(f"/imperium/missions/{mission.id}")

    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_mission_detail_does_not_modify_mission_state() -> None:
    current_user = _user()
    started_at = datetime(2026, 5, 25, 7, 10, tzinfo=UTC)
    ended_at = datetime(2026, 5, 25, 9, 10, tzinfo=UTC)
    created_at = datetime(2026, 5, 25, 7, 0, tzinfo=UTC)
    updated_at = datetime(2026, 5, 25, 9, 20, tzinfo=UTC)
    mission = _mission(
        current_user.id,
        status="completed",
        started_at=started_at,
        ended_at=ended_at,
        created_at=created_at,
        updated_at=updated_at,
    )
    db = FakeDb(scalar_results=[mission])

    response = _client(db, current_user).get(f"/imperium/missions/{mission.id}")

    assert response.status_code == 200
    assert mission.status == "completed"
    assert mission.started_at == started_at
    assert mission.ended_at == ended_at
    assert mission.created_at == created_at
    assert mission.updated_at == updated_at


def test_mission_detail_route_order_keeps_static_mission_routes_first() -> None:
    route_text = Path(__file__).resolve().parents[1].joinpath("app", "api", "v1", "routes", "imperium.py").read_text(
        encoding="utf-8"
    )
    detail_index = route_text.index("def mission_detail_route(")

    assert route_text.index('@router.get("/missions/active"') < detail_index
    assert route_text.index('@router.get("/missions/history"') < detail_index
    assert route_text.index('@router.get("/missions/backlog"') < detail_index
    assert route_text.index('"/missions/backlog/decision-preview"') < detail_index
    assert detail_index < route_text.index("def mission_decision_score_route(")
