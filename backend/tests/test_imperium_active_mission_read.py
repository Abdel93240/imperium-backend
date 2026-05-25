from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium
from app.models.imperium import ImperiumMission


class FakeDb:
    def __init__(self, *, scalar_results=None, scalars_results=None) -> None:
        self.scalar_results = list(scalar_results or [])
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

    def scalar(self, query):
        self.queries.append(query)
        if self.scalar_results:
            return self.scalar_results.pop(0)
        return None

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
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _mission(user_id, **overrides) -> ImperiumMission:
    now = datetime.now(UTC)
    mission = ImperiumMission(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        title=overrides.pop("title", "Active mission"),
        category=overrides.pop("category", None),
        domain=overrides.pop("domain", "business"),
        priority_level=overrides.pop("priority_level", 3),
        mission_type_category=overrides.pop("mission_type_category", None),
        status=overrides.pop("status", "active"),
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


def test_active_mission_returns_current_user_mission_without_internal_fields() -> None:
    current_user = _user()
    started_at = datetime(2026, 5, 25, 8, 0, tzinfo=UTC)
    created_at = datetime(2026, 5, 25, 7, 55, tzinfo=UTC)
    updated_at = datetime(2026, 5, 25, 8, 5, tzinfo=UTC)
    mission = _mission(
        current_user.id,
        started_at=started_at,
        created_at=created_at,
        updated_at=updated_at,
    )
    db = FakeDb(scalars_results=[[mission]])

    response = _client(db, current_user).get("/imperium/missions/active")

    assert response.status_code == 200
    body = response.json()
    assert body["safe_explanation"] == "Current active mission for user."
    assert body["mission"]["id"] == str(mission.id)
    assert body["mission"]["status"] == "active"
    assert body["mission"]["started_at"] == started_at.isoformat().replace("+00:00", "Z")
    assert body["mission"]["created_at"] == created_at.isoformat().replace("+00:00", "Z")
    assert body["mission"]["updated_at"] == updated_at.isoformat().replace("+00:00", "Z")
    assert "ended_at" not in body["mission"]
    assert "decision_score" not in body["mission"]
    assert "weighted_score" not in body["mission"]
    assert "coefficient" not in body["mission"]
    assert mission.status == "active"
    assert mission.started_at == started_at
    assert mission.ended_at is None
    assert mission.created_at == created_at
    assert mission.updated_at == updated_at
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_active_mission_returns_null_when_none_exists() -> None:
    current_user = _user()
    db = FakeDb(scalars_results=[[]])

    response = _client(db, current_user).get("/imperium/missions/active")

    assert response.status_code == 200
    assert response.json() == {
        "mission": None,
        "safe_explanation": "No active mission found for current user.",
    }
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_active_mission_query_is_user_scoped() -> None:
    current_user = _user()
    mission = _mission(current_user.id, title="Scoped mission")
    db = FakeDb(scalars_results=[[mission]])

    response = _client(db, current_user).get("/imperium/missions/active")

    assert response.status_code == 200
    assert response.json()["mission"]["id"] == str(mission.id)
    query_text = str(db.queries[0])
    assert "imperium_missions.user_id" in query_text
    assert "imperium_missions.status" in query_text


def test_active_mission_returns_409_when_multiple_active_missions_exist() -> None:
    current_user = _user()
    mission_one = _mission(current_user.id, title="Mission one")
    mission_two = _mission(current_user.id, title="Mission two")
    db = FakeDb(scalars_results=[[mission_one, mission_two]])

    response = _client(db, current_user).get("/imperium/missions/active")

    assert response.status_code == 409
    assert response.json()["detail"] == "Multiple active missions found for current user."
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_active_mission_does_not_require_idempotency_key() -> None:
    current_user = _user()
    db = FakeDb(scalars_results=[[]])

    response = _client(db, current_user).get("/imperium/missions/active")

    assert response.status_code == 200
