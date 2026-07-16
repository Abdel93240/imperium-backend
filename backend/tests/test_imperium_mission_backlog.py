from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium
from app.models.event import Event
from app.models.enums import IdempotencyStatus
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumMission, ImperiumMissionScore
from app.schemas.imperium import BacklogMissionCreateRequest
from app.services.imperium.missions import (
    _hash_request,
    create_backlog_mission,
    list_backlog_missions,
    promote_backlog_mission,
)


class FakeDb:
    def __init__(self, *, scalar_results=None, scalars_results=None, scalars_result=None) -> None:
        self.scalar_results = list(scalar_results or [])
        self.scalars_results = [list(result) for result in scalars_results] if scalars_results is not None else None
        self.scalars_result = list(scalars_result or [])
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

    def scalars(self, query):
        self.queries.append(query)
        if self.scalars_results is not None:
            if self.scalars_results:
                return self.scalars_results.pop(0)
            return []
        return self.scalars_result

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
        title=overrides.pop("title", "Backlog mission"),
        category=overrides.pop("category", None),
        domain=overrides.pop("domain", None),
        priority_level=overrides.pop("priority_level", None),
        mission_type_category=overrides.pop("mission_type_category", None),
        status=overrides.pop("status", "backlog"),
        started_at=overrides.pop("started_at", now),
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
        },
        source="decision_framework_v1",
        created_at=now,
        updated_at=now,
    )


def test_backlog_create_request_reuses_decision_field_validation() -> None:
    payload = BacklogMissionCreateRequest(
        title="Prepare invoice",
        domain="business",
        priority_level=3,
        mission_type_category="cat_e",
    )

    assert payload.domain == "business"
    assert payload.priority_level == 3
    assert payload.mission_type_category == "cat_e"


@pytest.mark.parametrize(
    "field_name",
    [
        "intrinsic_score",
        "weighted_score",
        "domain_coefficient",
        "final_weighted_score",
        "coefficient",
        "score",
        "priority_bucket",
    ],
)
def test_backlog_create_request_rejects_client_supplied_score_fields(field_name: str) -> None:
    with pytest.raises(ValueError):
        BacklogMissionCreateRequest.model_validate({"title": "Mission", field_name: 10})


def test_create_backlog_mission_persists_backlog_status_and_score_when_signals_exist() -> None:
    db = FakeDb()
    current_user = _user()
    payload = BacklogMissionCreateRequest(
        title="Prepare monthly invoice",
        domain="business",
        priority_level=4,
        mission_type_category="cat_e",
        deadline_at=datetime.now(UTC) + timedelta(days=2),
        impact="critical",
        dependency=True,
        recurrence="monthly",
    )

    response, duplicate = create_backlog_mission(
        db,
        current_user=current_user,
        payload=payload,
        idempotency_key="backlog-create-1",
        request_method="POST",
        request_path="/imperium/missions/backlog",
    )

    mission = next(item for item in db.added if isinstance(item, ImperiumMission))
    assert duplicate is False
    assert mission.user_id == current_user.id
    assert mission.status == "backlog"
    assert mission.domain == "business"
    assert response.mission.status == "backlog"
    assert response.score_created is True
    assert response.mission.decision_score is not None
    assert any(isinstance(item, ImperiumMissionScore) for item in db.added)
    assert any(isinstance(item, Event) and item.event_type == "planning.mission.created" for item in db.added)
    assert any(isinstance(item, IdempotencyKey) for item in db.added)
    assert db.committed is True


def test_create_backlog_mission_without_scoring_signals_does_not_store_score() -> None:
    db = FakeDb()
    payload = BacklogMissionCreateRequest(title="Simple backlog mission", domain="business")

    response, _duplicate = create_backlog_mission(
        db,
        current_user=_user(),
        payload=payload,
        idempotency_key="backlog-no-score",
        request_method="POST",
        request_path="/imperium/missions/backlog",
    )

    assert response.score_created is False
    assert response.mission.decision_score is None
    assert not any(isinstance(item, ImperiumMissionScore) for item in db.added)


def test_list_backlog_missions_is_user_scoped_and_sorted_deterministically() -> None:
    current_user = _user()
    older = datetime(2026, 5, 1, 8, 0, tzinfo=UTC)
    newer = datetime(2026, 5, 2, 8, 0, tzinfo=UTC)
    low_bucket = _mission(current_user.id, title="Low bucket", priority_level=1, created_at=newer)
    high_bucket = _mission(current_user.id, title="High bucket", priority_level=9, created_at=newer)
    no_score_low_priority = _mission(current_user.id, title="Manual urgent", priority_level=1, created_at=newer)
    no_score_same_priority_old = _mission(current_user.id, title="Manual old", priority_level=5, created_at=older)
    no_score_same_priority_new = _mission(current_user.id, title="Manual new", priority_level=5, created_at=newer)
    scores = [
        _score(current_user.id, low_bucket.id, bucket=2),
        _score(current_user.id, high_bucket.id, bucket=8),
    ]
    db = FakeDb(
        scalars_results=[
            [low_bucket, no_score_same_priority_new, high_bucket, no_score_low_priority, no_score_same_priority_old],
            scores,
        ]
    )

    response = list_backlog_missions(db, current_user=current_user)

    assert [item.title for item in response.items] == [
        "High bucket",
        "Low bucket",
        "Manual urgent",
        "Manual old",
        "Manual new",
    ]
    assert response.count == 5
    assert "created_at ascending" in response.ordering
    query_text = str(db.queries[0])
    assert "imperium_missions.user_id" in query_text
    assert "imperium_missions.status" in query_text


def test_promote_backlog_mission_sets_active_and_started_event() -> None:
    current_user = _user()
    mission = _mission(current_user.id)
    score = _score(current_user.id, mission.id, bucket=4)
    db = FakeDb(scalar_results=[None, mission, None, score])

    response, duplicate = promote_backlog_mission(
        db,
        current_user=current_user,
        mission_id=mission.id,
        idempotency_key="backlog-promote-1",
        request_method="POST",
        request_path=f"/imperium/missions/backlog/{mission.id}/promote",
    )

    assert duplicate is False
    assert mission.status == "active"
    assert mission.created_by_event_id is not None
    assert response.mission.status == "active"
    assert response.status == "promoted"
    assert response.decision_score is not None
    assert any(isinstance(item, Event) and item.event_type == "planning.mission.started" for item in db.added)
    assert db.committed is True


def test_promote_backlog_mission_fails_when_active_mission_exists() -> None:
    current_user = _user()
    active = _mission(current_user.id, status="active")
    db = FakeDb(scalar_results=[None, _mission(current_user.id), active])

    with pytest.raises(ValueError, match="active mission"):
        promote_backlog_mission(
            db,
            current_user=current_user,
            mission_id=uuid4(),
            idempotency_key="backlog-promote-active-conflict",
            request_method="POST",
            request_path="/imperium/missions/backlog/mission/promote",
        )


def test_backlog_create_route_requires_idempotency() -> None:
    response = _client(FakeDb(), _user()).post("/imperium/missions/backlog", json={"title": "Mission"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing Idempotency-Key header."


def test_backlog_promote_route_returns_409_when_active_mission_exists() -> None:
    current_user = _user()
    mission = _mission(current_user.id)
    active = _mission(current_user.id, status="active")
    db = FakeDb(scalar_results=[None, mission, active])

    response = _client(db, current_user).post(
        f"/imperium/missions/backlog/{mission.id}/promote",
        headers={"Idempotency-Key": "promote-route-conflict"},
    )

    assert response.status_code == 409
    assert "active mission" in response.json()["detail"]


def test_idempotent_backlog_create_does_not_duplicate_mission() -> None:
    current_user = _user()
    payload = BacklogMissionCreateRequest(title="Cached backlog", domain="business")
    mission_id = uuid4()
    now = datetime.now(UTC).isoformat()
    cached_response = {
        "mission": {
            "id": str(mission_id),
            "status": "backlog",
            "title": payload.title,
            "category": None,
            "domain": "business",
            "priority_level": None,
            "mission_type_category": None,
            "planned_start_at": None,
            "planned_end_at": None,
            "started_at": now,
            "ended_at": None,
            "created_at": now,
            "updated_at": now,
            "decision_score": None,
        },
        "event_id": "evt_cached",
        "idempotency_key": "backlog-create-replay",
        "status": "created",
        "score_created": False,
    }
    existing_key = IdempotencyKey(
        user_id=current_user.id,
        idempotency_key="backlog-create-replay",
        request_method="POST",
        request_path="/imperium/missions/backlog",
        request_hash=_hash_request("mission.backlog.created", payload.model_dump(mode="json")),
        status=IdempotencyStatus.completed,
        response_status_code=201,
        response_body=cached_response,
    )
    db = FakeDb(scalar_results=[existing_key])

    response, duplicate = create_backlog_mission(
        db,
        current_user=current_user,
        payload=payload,
        idempotency_key="backlog-create-replay",
        request_method="POST",
        request_path="/imperium/missions/backlog",
    )

    assert duplicate is True
    assert response.mission.id == mission_id
    assert db.added == []
    assert db.committed is False
