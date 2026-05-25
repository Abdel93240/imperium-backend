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
        title=overrides.pop("title", "Historical mission"),
        category=overrides.pop("category", None),
        domain=overrides.pop("domain", "business"),
        priority_level=overrides.pop("priority_level", 3),
        mission_type_category=overrides.pop("mission_type_category", None),
        status=overrides.pop("status", "completed"),
        planned_start_at=overrides.pop("planned_start_at", None),
        planned_end_at=overrides.pop("planned_end_at", None),
        started_at=overrides.pop("started_at", now),
        ended_at=overrides.pop("ended_at", now),
        created_at=overrides.pop("created_at", now),
        updated_at=overrides.pop("updated_at", now),
    )
    for key, value in overrides.items():
        setattr(mission, key, value)
    return mission


def test_mission_history_returns_completed_failed_and_abandoned_for_current_user() -> None:
    current_user = _user()
    completed = _mission(
        current_user.id,
        title="Completed",
        status="completed",
        ended_at=datetime(2026, 5, 25, 10, 0, tzinfo=UTC),
    )
    failed = _mission(
        current_user.id,
        title="Failed",
        status="failed",
        ended_at=datetime(2026, 5, 25, 9, 0, tzinfo=UTC),
    )
    abandoned = _mission(
        current_user.id,
        title="Abandoned",
        status="abandoned",
        ended_at=datetime(2026, 5, 25, 8, 0, tzinfo=UTC),
    )
    backlog = _mission(current_user.id, title="Backlog", status="backlog")
    active = _mission(current_user.id, title="Active", status="active")
    foreign = _mission(uuid4(), title="Foreign", status="completed")
    db = FakeDb(scalars_results=[[completed, failed, abandoned, backlog, active, foreign]])

    response = _client(db, current_user).get("/imperium/missions/history")

    assert response.status_code == 200
    body = response.json()
    assert body["safe_explanation"] == "Mission history for current user."
    assert [item["title"] for item in body["items"]] == ["Completed", "Failed", "Abandoned"]
    assert body["count"] == 3
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert all(item["status"] in {"completed", "failed", "abandoned"} for item in body["items"])
    assert all("weighted_score" not in item for item in body["items"])
    assert all("decision_score" not in item for item in body["items"])
    assert all("coefficient" not in item for item in body["items"])
    assert all("ai_usable_reason" not in item for item in body["items"])
    assert all("failure_reason" not in item for item in body["items"])
    assert all("completion_note" not in item for item in body["items"])
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False
    assert completed.status == "completed"
    assert failed.status == "failed"
    assert abandoned.status == "abandoned"


def test_mission_history_query_is_user_scoped_and_excludes_non_hist_statuses() -> None:
    current_user = _user()
    own = _mission(current_user.id, title="Own", status="completed")
    foreign = _mission(uuid4(), title="Foreign", status="completed")
    backlog = _mission(current_user.id, title="Backlog", status="backlog")
    active = _mission(current_user.id, title="Active", status="active")
    db = FakeDb(scalars_results=[[own, foreign, backlog, active]])

    response = _client(db, current_user).get("/imperium/missions/history")

    assert response.status_code == 200
    assert [item["title"] for item in response.json()["items"]] == ["Own"]
    query_text = str(db.queries[0])
    assert "imperium_missions.user_id" in query_text
    assert "imperium_missions.status" in query_text


def test_mission_history_filters_by_status_domain_priority_and_time_window() -> None:
    current_user = _user()
    matched = _mission(
        current_user.id,
        title="Matched",
        status="failed",
        domain="finance",
        priority_level=7,
        started_at=datetime(2026, 5, 20, 7, 0, tzinfo=UTC),
        ended_at=datetime(2026, 5, 20, 9, 0, tzinfo=UTC),
    )
    wrong_status = _mission(current_user.id, title="Wrong status", status="completed", domain="finance", priority_level=7)
    wrong_domain = _mission(current_user.id, title="Wrong domain", status="failed", domain="business", priority_level=7)
    wrong_priority = _mission(current_user.id, title="Wrong priority", status="failed", domain="finance", priority_level=4)
    too_early = _mission(
        current_user.id,
        title="Too early",
        status="failed",
        domain="finance",
        priority_level=7,
        started_at=datetime(2026, 5, 19, 7, 0, tzinfo=UTC),
        ended_at=datetime(2026, 5, 19, 9, 0, tzinfo=UTC),
    )
    too_late = _mission(
        current_user.id,
        title="Too late",
        status="failed",
        domain="finance",
        priority_level=7,
        started_at=datetime(2026, 5, 21, 7, 0, tzinfo=UTC),
        ended_at=datetime(2026, 5, 21, 9, 0, tzinfo=UTC),
    )
    db = FakeDb(scalars_results=[[matched, wrong_status, wrong_domain, wrong_priority, too_early, too_late]])

    response = _client(
        db,
        current_user,
    ).get(
        "/imperium/missions/history"
        "?status=failed&domain=finance&priority_level=7"
        "&started_after=2026-05-20T00:00:00Z&ended_before=2026-05-21T00:00:00Z"
    )

    assert response.status_code == 200
    assert [item["title"] for item in response.json()["items"]] == ["Matched"]


def test_mission_history_respects_limit_offset_and_deterministic_sorting() -> None:
    current_user = _user()
    mission_a = _mission(
        current_user.id,
        id=uuid4(),
        title="A",
        ended_at=datetime(2026, 5, 25, 10, 0, tzinfo=UTC),
        created_at=datetime(2026, 5, 25, 9, 0, tzinfo=UTC),
    )
    mission_b = _mission(
        current_user.id,
        id=uuid4(),
        title="B",
        ended_at=datetime(2026, 5, 25, 10, 0, tzinfo=UTC),
        created_at=datetime(2026, 5, 25, 8, 30, tzinfo=UTC),
    )
    mission_c = _mission(
        current_user.id,
        id=uuid4(),
        title="C",
        ended_at=datetime(2026, 5, 24, 10, 0, tzinfo=UTC),
        created_at=datetime(2026, 5, 25, 11, 0, tzinfo=UTC),
    )
    db = FakeDb(scalars_results=[[mission_c, mission_a, mission_b]])

    response = _client(db, current_user).get("/imperium/missions/history?limit=1&offset=1")

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 1
    assert body["offset"] == 1
    assert body["count"] == 1
    assert [item["title"] for item in body["items"]] == ["B"]


def test_mission_history_returns_empty_list_cleanly() -> None:
    current_user = _user()
    db = FakeDb(scalars_results=[[]])

    response = _client(db, current_user).get("/imperium/missions/history")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "count": 0,
        "limit": 20,
        "offset": 0,
        "safe_explanation": "Mission history for current user.",
    }


def test_mission_history_does_not_require_idempotency_key() -> None:
    current_user = _user()
    db = FakeDb(scalars_results=[[]])

    response = _client(db, current_user).get("/imperium/missions/history")

    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_mission_history_does_not_modify_mission_state() -> None:
    current_user = _user()
    started_at = datetime(2026, 5, 25, 7, 30, tzinfo=UTC)
    ended_at = datetime(2026, 5, 25, 9, 45, tzinfo=UTC)
    created_at = datetime(2026, 5, 25, 7, 0, tzinfo=UTC)
    updated_at = datetime(2026, 5, 25, 9, 50, tzinfo=UTC)
    mission = _mission(
        current_user.id,
        title="Immutable",
        started_at=started_at,
        ended_at=ended_at,
        created_at=created_at,
        updated_at=updated_at,
    )
    db = FakeDb(scalars_results=[[mission]])

    response = _client(db, current_user).get("/imperium/missions/history")

    assert response.status_code == 200
    assert mission.status == "completed"
    assert mission.started_at == started_at
    assert mission.ended_at == ended_at
    assert mission.created_at == created_at
    assert mission.updated_at == updated_at


def test_mission_history_public_shape_does_not_expose_internal_scores() -> None:
    current_user = _user()
    mission = _mission(current_user.id)
    setattr(mission, "decision_score", {"coefficient": 8, "weighted_score": 80})
    setattr(mission, "weighted_score", 80)
    setattr(mission, "coefficient", 8)
    setattr(mission, "ai_usable_reason", True)
    db = FakeDb(scalars_results=[[mission]])

    response = _client(db, current_user).get("/imperium/missions/history")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert "decision_score" not in item
    assert "weighted_score" not in item
    assert "coefficient" not in item
    assert "ai_usable_reason" not in item
