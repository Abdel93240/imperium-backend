from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium
from app.models.imperium import ImperiumMission, ImperiumMissionScore


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
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _mission(user_id, **overrides) -> ImperiumMission:
    now = datetime.now(UTC)
    mission = ImperiumMission(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        title=overrides.pop("title", "Decision score mission"),
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


def _score(user_id, mission_id, *, bucket: int, intrinsic_score: int = 10) -> ImperiumMissionScore:
    now = datetime.now(UTC)
    return ImperiumMissionScore(
        id=uuid4(),
        user_id=user_id,
        mission_id=mission_id,
        domain="business",
        intrinsic_score=intrinsic_score,
        domain_coefficient=8,
        weighted_score=intrinsic_score * 8,
        explanation={
            "priority_bucket": bucket,
            "score_status": "partial",
            "missing_fields": ["deadline_at"],
            "internal_prompt": "must not leak",
            "memory_candidate": "must not leak",
        },
        source="decision_framework_v1",
        created_at=now,
        updated_at=now,
    )


def test_decision_score_returns_safe_summary_for_backlog_mission() -> None:
    current_user = _user()
    mission = _mission(current_user.id, status="backlog", priority_level=1)
    db = FakeDb(scalar_results=[mission, _score(current_user.id, mission.id, bucket=4)])

    response = _client(db, current_user).get(f"/imperium/missions/{mission.id}/decision-score")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "mission_id": str(mission.id),
        "status": "backlog",
        "priority_level": 1,
        "priority_bucket": 4,
        "score_summary": {
            "label": "high",
            "reason_codes": ["HIGH_PRIORITY_BUCKET", "LOW_PRIORITY_LEVEL"],
        },
        "safe_explanation": "Deterministic backend decision summary based on stored mission fields only.",
    }
    assert "imperium_missions.user_id" in str(db.queries[0])
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_decision_score_returns_safe_summary_for_active_mission() -> None:
    current_user = _user()
    mission = _mission(current_user.id, status="active", priority_level=3)
    db = FakeDb(scalar_results=[mission, _score(current_user.id, mission.id, bucket=2)])

    response = _client(db, current_user).get(f"/imperium/missions/{mission.id}/decision-score")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "active"
    assert body["priority_bucket"] == 2
    assert body["score_summary"] == {
        "label": "medium",
        "reason_codes": ["MEDIUM_PRIORITY_BUCKET", "NORMAL_PRIORITY_LEVEL"],
    }


def test_decision_score_returns_safe_summary_for_completed_mission() -> None:
    current_user = _user()
    ended_at = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    mission = _mission(current_user.id, status="completed", priority_level=5, ended_at=ended_at)
    db = FakeDb(scalar_results=[mission, _score(current_user.id, mission.id, bucket=1)])

    response = _client(db, current_user).get(f"/imperium/missions/{mission.id}/decision-score")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["priority_bucket"] == 1
    assert body["score_summary"] == {
        "label": "low",
        "reason_codes": ["LOW_PRIORITY_BUCKET", "NORMAL_PRIORITY_LEVEL"],
    }


def test_decision_score_returns_404_for_missing_mission() -> None:
    current_user = _user()
    db = FakeDb(scalar_results=[None])

    response = _client(db, current_user).get(f"/imperium/missions/{uuid4()}/decision-score")

    assert response.status_code == 404
    assert response.json()["detail"] == "Mission not found."
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_decision_score_returns_404_for_foreign_mission() -> None:
    current_user = _user()
    foreign_mission = _mission(uuid4(), status="active")
    db = FakeDb(scalar_results=[None])

    response = _client(db, current_user).get(f"/imperium/missions/{foreign_mission.id}/decision-score")

    assert response.status_code == 404
    assert response.json()["detail"] == "Mission not found."
    assert "imperium_missions.user_id" in str(db.queries[0])
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_decision_score_include_reasons_false_hides_reason_codes() -> None:
    current_user = _user()
    mission = _mission(current_user.id, status="backlog", priority_level=1)
    db = FakeDb(scalar_results=[mission, _score(current_user.id, mission.id, bucket=4)])

    response = _client(db, current_user).get(
        f"/imperium/missions/{mission.id}/decision-score?include_reasons=false"
    )

    assert response.status_code == 200
    assert response.json()["score_summary"] == {"label": "high"}


def test_decision_score_does_not_require_idempotency_key() -> None:
    current_user = _user()
    mission = _mission(current_user.id, status="active")
    db = FakeDb(scalar_results=[mission, None])

    response = _client(db, current_user).get(f"/imperium/missions/{mission.id}/decision-score")

    assert response.status_code == 200
    assert response.json()["priority_bucket"] == 0
    assert response.json()["score_summary"]["label"] == "low"


def test_decision_score_is_read_only_and_does_not_change_state_or_timestamps() -> None:
    current_user = _user()
    started_at = datetime(2026, 5, 25, 7, 0, tzinfo=UTC)
    ended_at = datetime(2026, 5, 25, 8, 0, tzinfo=UTC)
    created_at = datetime(2026, 5, 25, 6, 50, tzinfo=UTC)
    updated_at = datetime(2026, 5, 25, 8, 10, tzinfo=UTC)
    mission = _mission(
        current_user.id,
        status="completed",
        priority_level=2,
        started_at=started_at,
        ended_at=ended_at,
        created_at=created_at,
        updated_at=updated_at,
    )
    db = FakeDb(scalar_results=[mission, _score(current_user.id, mission.id, bucket=3)])

    response = _client(db, current_user).get(f"/imperium/missions/{mission.id}/decision-score")

    assert response.status_code == 200
    assert mission.status == "completed"
    assert mission.started_at == started_at
    assert mission.ended_at == ended_at
    assert mission.created_at == created_at
    assert mission.updated_at == updated_at
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_decision_score_response_exposes_no_internal_fields() -> None:
    current_user = _user()
    mission = _mission(current_user.id, status="active", priority_level=2)
    db = FakeDb(scalar_results=[mission, _score(current_user.id, mission.id, bucket=4)])

    response = _client(db, current_user).get(f"/imperium/missions/{mission.id}/decision-score")

    assert response.status_code == 200
    body_text = response.text
    for forbidden in (
        "coefficient",
        "domain_coefficient",
        "weighted_score",
        "final_weighted_score",
        "intrinsic_score",
        '"explanation"',
        "missing_fields",
        "source",
        "provider",
        "qwen",
        "openai",
        "anthropic",
        "claude",
        "gemini",
        "n8n",
        "memory",
        "embedding",
        "calendar",
        "internal_prompt",
    ):
        assert forbidden not in body_text.lower()


def test_decision_score_route_order_does_not_hit_mission_detail_route() -> None:
    current_user = _user()
    mission = _mission(current_user.id, status="backlog", priority_level=1)
    db = FakeDb(scalar_results=[mission, _score(current_user.id, mission.id, bucket=4)])

    response = _client(db, current_user).get(f"/imperium/missions/{mission.id}/decision-score")

    assert response.status_code == 200
    body = response.json()
    assert "mission" not in body
    assert body["mission_id"] == str(mission.id)
    assert body["score_summary"]["label"] == "high"


def test_decision_score_route_order_keeps_static_routes_before_dynamic_detail() -> None:
    route_text = Path(__file__).resolve().parents[1].joinpath("app", "api", "v1", "routes", "imperium.py").read_text(
        encoding="utf-8"
    )
    detail_index = route_text.index("def mission_detail_route(")
    decision_index = route_text.index("def mission_decision_score_route(")

    assert route_text.index('@router.get("/missions/active"') < detail_index
    assert route_text.index('@router.get("/missions/history"') < detail_index
    assert route_text.index('@router.get("/missions/backlog"') < detail_index
    assert route_text.index('"/missions/backlog/decision-preview"') < detail_index
    assert detail_index < decision_index


def test_decision_score_read_has_no_ai_n8n_pgvector_embedding_memory_calendar_or_writes() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    service_text = backend_root.joinpath("app", "services", "imperium", "missions.py").read_text(encoding="utf-8")
    route_text = backend_root.joinpath("app", "api", "v1", "routes", "imperium.py").read_text(encoding="utf-8")
    schema_text = backend_root.joinpath("app", "schemas", "imperium.py").read_text(encoding="utf-8")
    service_section = service_text.split("def get_mission_decision_score", maxsplit=1)[1].split(
        "def _get_existing_idempotency",
        maxsplit=1,
    )[0]
    route_section = route_text.split("def mission_decision_score_route(", maxsplit=1)[1].split(
        '@router.get("/priorities"',
        maxsplit=1,
    )[0]
    schema_section = schema_text.split("class MissionDecisionScorePublicSummary", maxsplit=1)[1].split(
        "class PathItemStatus",
        maxsplit=1,
    )[0]
    combined = "\n".join([service_section, route_section, schema_section])
    lowered = combined.lower()

    assert "Idempotency-Key" not in route_section
    assert "db.add" not in service_section
    assert "db.flush" not in service_section
    assert "db.commit" not in service_section
    assert "mission.status =" not in service_section
    assert "QwenClient" not in combined
    assert "providers" not in combined
    assert "openai" not in lowered
    assert "anthropic" not in lowered
    assert "gemini" not in lowered
    assert "claude" not in lowered
    assert "n8n" not in lowered
    assert "pgvector" not in lowered
    assert "embedding" not in lowered
    assert "memory commit" not in lowered
    assert "calendar" not in lowered
    assert "coefficient" not in schema_section
    assert "weighted_score" not in schema_section
