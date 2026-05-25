from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium
from app.models.enums import IdempotencyStatus
from app.models.event import Event
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumMission
from app.services.imperium.missions import _hash_request


class FakeDb:
    def __init__(self, *, scalar_results=None) -> None:
        self.scalar_results = list(scalar_results or [])
        self.added = []
        self.queries = []
        self.flushed = False
        self.committed = False
        self.rolled_back = False

    def add(self, obj) -> None:
        self._prepare(obj)
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed = True
        for item in self.added:
            self._prepare(item)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def scalar(self, query):
        self.queries.append(query)
        if self.scalar_results:
            return self.scalar_results.pop(0)
        return None

    def _prepare(self, obj) -> None:
        now = datetime.now(UTC)
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()
        if hasattr(obj, "created_at") and getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if hasattr(obj, "updated_at") and getattr(obj, "updated_at", None) is None:
            obj.updated_at = now


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


def _post_complete(client: TestClient, mission_id, *, key: str, payload: dict):
    return client.post(
        f"/imperium/missions/{mission_id}/complete",
        headers={"Idempotency-Key": key},
        json=payload,
    )


def _post_fail(client: TestClient, mission_id, *, key: str | None, payload: dict):
    headers = {"Idempotency-Key": key} if key is not None else {}
    return client.post(
        f"/imperium/missions/{mission_id}/fail",
        headers=headers,
        json=payload,
    )


def _post_start(client: TestClient, *, key: str, payload: dict):
    return client.post(
        "/imperium/missions/start",
        headers={"Idempotency-Key": key},
        json=payload,
    )


def test_start_route_returns_409_when_active_mission_exists() -> None:
    current_user = _user()
    active = _mission(current_user.id, title="Existing active mission")
    db = FakeDb(scalar_results=[None, active])

    response = _post_start(
        _client(db, current_user),
        key="start-active-conflict",
        payload={"title": "Second active mission"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "An active mission already exists for this user."
    assert db.rolled_back is True
    assert db.added == []


def test_complete_active_mission_with_completed_outcome_sets_safe_summary() -> None:
    current_user = _user()
    started_at = datetime(2026, 5, 25, 8, 0, tzinfo=UTC)
    mission = _mission(current_user.id, started_at=started_at)
    db = FakeDb(scalar_results=[None, mission])

    response = _post_complete(
        _client(db, current_user),
        mission.id,
        key="complete-completed",
        payload={"outcome": "completed"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mission"]["id"] == str(mission.id)
    assert body["mission"]["status"] == "completed"
    assert body["mission"]["started_at"] == started_at.isoformat().replace("+00:00", "Z")
    assert body["mission"]["ended_at"] is not None
    assert body["completion_summary"] == {
        "status": "completed",
        "guardrails_checked": [
            "OWNERSHIP_CONFIRMED",
            "MISSION_WAS_ACTIVE",
            "OUTCOME_VALIDATED",
            "IDEMPOTENCY_KEY_ACCEPTED",
        ],
        "safe_explanation": "Mission completed using deterministic backend guardrails only.",
    }
    assert mission.status == "completed"
    assert mission.started_at == started_at
    assert mission.ended_at is not None
    assert any(isinstance(item, Event) and item.event_type == "mission.completed" for item in db.added)
    assert any(isinstance(item, IdempotencyKey) for item in db.added)


def test_complete_failed_without_reason_returns_422() -> None:
    response = _post_complete(
        _client(FakeDb(), _user()),
        uuid4(),
        key="complete-failed-missing-reason",
        payload={"outcome": "failed"},
    )

    assert response.status_code == 422


def test_complete_abandoned_without_reason_returns_422() -> None:
    response = _post_complete(
        _client(FakeDb(), _user()),
        uuid4(),
        key="complete-abandoned-missing-reason",
        payload={"outcome": "abandoned", "reason": "   "},
    )

    assert response.status_code == 422


def test_complete_requires_idempotency_key() -> None:
    response = _client(FakeDb(), _user()).post(
        f"/imperium/missions/{uuid4()}/complete",
        json={"outcome": "completed"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing Idempotency-Key header."


def test_complete_rejects_client_supplied_score_fields() -> None:
    response = _post_complete(
        _client(FakeDb(), _user()),
        uuid4(),
        key="complete-reject-score",
        payload={"outcome": "completed", "weighted_score": 999},
    )

    assert response.status_code == 422


def test_complete_failed_with_reason_succeeds() -> None:
    current_user = _user()
    mission = _mission(current_user.id)
    db = FakeDb(scalar_results=[None, mission])

    response = _post_complete(
        _client(db, current_user),
        mission.id,
        key="complete-failed",
        payload={"outcome": "failed", "reason": "blocked by external dependency"},
    )

    assert response.status_code == 200
    assert response.json()["mission"]["status"] == "failed"
    assert response.json()["mission"]["failure_reason"] == "blocked by external dependency"
    assert mission.status == "failed"
    assert mission.failure_reason == "blocked by external dependency"


def test_complete_abandoned_with_reason_succeeds() -> None:
    current_user = _user()
    mission = _mission(current_user.id)
    db = FakeDb(scalar_results=[None, mission])

    response = _post_complete(
        _client(db, current_user),
        mission.id,
        key="complete-abandoned",
        payload={"outcome": "abandoned", "reason": "mission no longer matters"},
    )

    assert response.status_code == 200
    assert response.json()["mission"]["status"] == "abandoned"
    assert response.json()["mission"]["failure_reason"] == "mission no longer matters"
    assert mission.status == "abandoned"
    assert mission.failure_reason == "mission no longer matters"


def test_complete_missing_or_non_owned_mission_returns_404() -> None:
    current_user = _user()
    db = FakeDb(scalar_results=[None, None])

    response = _post_complete(
        _client(db, current_user),
        uuid4(),
        key="complete-not-found",
        payload={"outcome": "completed"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Mission not found."


def test_complete_non_active_mission_returns_409() -> None:
    current_user = _user()
    mission = _mission(current_user.id, status="backlog")
    db = FakeDb(scalar_results=[None, mission])

    response = _post_complete(
        _client(db, current_user),
        mission.id,
        key="complete-backlog",
        payload={"outcome": "completed"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Mission is not active."
    assert db.added == []


def test_complete_replays_same_idempotency_key_without_second_transition() -> None:
    current_user = _user()
    mission_id = uuid4()
    started_at = datetime(2026, 5, 25, 8, 0, tzinfo=UTC)
    ended_at = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    payload = {"outcome": "completed", "reason": None}
    cached_response = {
        "mission": {
            "id": str(mission_id),
            "status": "completed",
            "title": "Replay completion",
            "category": None,
            "domain": "business",
            "priority_level": 3,
            "mission_type_category": None,
            "planned_start_at": None,
            "planned_end_at": None,
            "started_at": started_at.isoformat().replace("+00:00", "Z"),
            "ended_at": ended_at.isoformat().replace("+00:00", "Z"),
            "completion_note": None,
            "failure_reason": None,
            "user_reported_signals": None,
            "ai_usable_reason": None,
        },
        "completion_summary": {
            "status": "completed",
            "guardrails_checked": [
                "OWNERSHIP_CONFIRMED",
                "MISSION_WAS_ACTIVE",
                "OUTCOME_VALIDATED",
                "IDEMPOTENCY_KEY_ACCEPTED",
            ],
            "safe_explanation": "Mission completed using deterministic backend guardrails only.",
        },
    }
    existing_key = IdempotencyKey(
        user_id=current_user.id,
        idempotency_key="complete-replay",
        request_method="POST",
        request_path=f"/imperium/missions/{mission_id}/complete",
        request_hash=_hash_request(
            "mission.completion_guardrails",
            {"mission_id": str(mission_id), "payload": payload},
        ),
        status=IdempotencyStatus.completed,
        response_status_code=200,
        response_body=cached_response,
    )
    db = FakeDb(scalar_results=[existing_key])

    response = _post_complete(
        _client(db, current_user),
        mission_id,
        key="complete-replay",
        payload={"outcome": "completed"},
    )

    assert response.status_code == 200
    assert response.json() == cached_response
    assert db.added == []
    assert db.committed is False


def test_complete_same_idempotency_key_with_different_payload_returns_409() -> None:
    current_user = _user()
    mission_id = uuid4()
    existing_key = IdempotencyKey(
        user_id=current_user.id,
        idempotency_key="complete-conflict",
        request_method="POST",
        request_path=f"/imperium/missions/{mission_id}/complete",
        request_hash=_hash_request(
            "mission.completion_guardrails",
            {"mission_id": str(mission_id), "payload": {"outcome": "completed", "reason": None}},
        ),
        status=IdempotencyStatus.completed,
        response_status_code=200,
        response_body={"mission": {}, "completion_summary": {}},
    )
    db = FakeDb(scalar_results=[existing_key])

    response = _post_complete(
        _client(db, current_user),
        mission_id,
        key="complete-conflict",
        payload={"outcome": "failed", "reason": "blocked"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Idempotency key already used with different payload."
    assert db.added == []
    assert db.committed is False


def test_complete_different_idempotency_key_after_completion_returns_409() -> None:
    current_user = _user()
    mission = _mission(current_user.id)
    db = FakeDb(scalar_results=[None, mission, None, mission])
    client = _client(db, current_user)

    first_response = _post_complete(
        client,
        mission.id,
        key="complete-first",
        payload={"outcome": "completed"},
    )
    second_response = _post_complete(
        client,
        mission.id,
        key="complete-second",
        payload={"outcome": "completed"},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "Mission is not active."
    assert sum(isinstance(item, Event) and item.event_type == "mission.completed" for item in db.added) == 1


def test_complete_response_does_not_expose_coefficients_or_weighted_scores() -> None:
    current_user = _user()
    mission = _mission(current_user.id)
    response = _post_complete(
        _client(FakeDb(scalar_results=[None, mission]), current_user),
        mission.id,
        key="complete-no-score-exposure",
        payload={"outcome": "completed"},
    )

    assert response.status_code == 200
    for forbidden in ("domain_coefficient", "weighted_score", "final_weighted_score", "coefficient"):
        assert forbidden not in response.text


def test_complete_guardrails_have_no_ai_n8n_pgvector_embedding_memory_or_calendar_side_effects() -> None:
    from pathlib import Path

    service_source = Path("app/services/imperium/missions.py").read_text(encoding="utf-8")
    route_source = Path("app/api/v1/routes/imperium.py").read_text(encoding="utf-8")
    schema_source = Path("app/schemas/imperium.py").read_text(encoding="utf-8")
    complete_service_section = service_source.split("def complete_mission", maxsplit=1)[1].split(
        "def fail_mission",
        maxsplit=1,
    )[0]
    complete_route_section = route_source.split('@router.post("/missions/{mission_id}/complete"', maxsplit=1)[
        1
    ].split('@router.post("/missions/{mission_id}/fail"', maxsplit=1)[0]
    complete_schema_section = schema_source.split("class CompleteMissionRequest", maxsplit=1)[1].split(
        "class FailMissionRequest",
        maxsplit=1,
    )[0]
    complete_text = "\n".join([complete_service_section, complete_route_section, complete_schema_section])
    lowered = complete_text.lower()

    assert "QwenClient" not in complete_text
    assert "providers" not in complete_text
    assert "openai" not in lowered
    assert "anthropic" not in lowered
    assert "gemini" not in lowered
    assert "claude" not in lowered
    assert "n8n" not in lowered
    assert "pgvector" not in lowered
    assert "embedding" not in lowered
    assert "ai_memories" not in complete_text
    assert "memory" not in lowered
    assert "calendar" not in lowered
    assert "domain_coefficient" not in complete_schema_section
    assert "weighted_score" not in complete_schema_section
    assert "final_weighted_score" not in complete_schema_section


def test_fail_active_mission_stores_reason_signals_and_event() -> None:
    current_user = _user()
    mission = _mission(current_user.id)
    db = FakeDb(scalar_results=[None, mission])

    response = _post_fail(
        _client(db, current_user),
        mission.id,
        key="fail-active",
        payload={
            "failure_reason": "fatigue was too high",
            "user_reported_signals": {"fatigue_level": 9},
            "ai_usable_reason": False,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["mission"]["id"] == str(mission.id)
    assert body["mission"]["status"] == "failed"
    assert body["mission"]["failure_reason"] == "fatigue was too high"
    assert body["mission"]["user_reported_signals"] == {"fatigue_level": 9}
    assert body["mission"]["ai_usable_reason"] is False
    assert body["status"] == "failed"
    assert mission.status == "failed"
    assert mission.failure_reason == "fatigue was too high"
    assert mission.user_reported_signals == {"fatigue_level": 9}
    assert mission.ai_usable_reason is False
    assert any(isinstance(item, Event) and item.event_type == "mission.failed" for item in db.added)
    assert any(isinstance(item, IdempotencyKey) for item in db.added)
    assert db.committed is True


def test_fail_requires_idempotency_key() -> None:
    response = _post_fail(
        _client(FakeDb(), _user()),
        uuid4(),
        key=None,
        payload={"failure_reason": "blocked"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing Idempotency-Key header."


def test_fail_missing_or_non_owned_mission_returns_404() -> None:
    current_user = _user()
    db = FakeDb(scalar_results=[None, None])

    response = _post_fail(
        _client(db, current_user),
        uuid4(),
        key="fail-not-found",
        payload={"failure_reason": "blocked"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Mission not found."
    assert db.rolled_back is True


def test_fail_non_active_mission_returns_409() -> None:
    current_user = _user()
    mission = _mission(current_user.id, status="completed")
    db = FakeDb(scalar_results=[None, mission])

    response = _post_fail(
        _client(db, current_user),
        mission.id,
        key="fail-completed",
        payload={"failure_reason": "blocked"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Mission is not active."
    assert db.added == []
    assert db.rolled_back is True
