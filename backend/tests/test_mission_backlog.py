from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium
from app.models.enums import IdempotencyStatus
from app.models.event import Event
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumMission, ImperiumMissionScore
from app.schemas.imperium import BacklogMissionCreateRequest
from app.services.imperium.missions import (
    _hash_request,
    create_backlog_mission,
    get_backlog_decision_preview,
    get_mission_decision_score,
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

    def add_all(self, objs) -> None:
        for obj in objs:
            self.add(obj)

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
        domain=overrides.pop("domain", "business"),
        priority_level=overrides.pop("priority_level", None),
        mission_type_category=overrides.pop("mission_type_category", None),
        status=overrides.pop("status", "backlog"),
        started_at=overrides.pop("started_at", now),
        planned_start_at=overrides.pop("planned_start_at", None),
        planned_end_at=overrides.pop("planned_end_at", None),
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


def test_create_backlog_mission() -> None:
    current_user = _user()
    db = FakeDb()

    response = _client(db, current_user).post(
        "/imperium/missions/backlog",
        headers={"Idempotency-Key": "backlog-create-basic"},
        json={"title": "Prepare invoice", "domain": "business", "priority_level": 4},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["mission"]["title"] == "Prepare invoice"
    assert body["mission"]["status"] == "backlog"
    assert body["mission"]["domain"] == "business"
    assert body["mission"]["priority_level"] == 4
    assert body["status"] == "created"
    assert any(isinstance(item, ImperiumMission) for item in db.added)
    assert any(isinstance(item, Event) and item.event_type == "planning.mission.created" for item in db.added)
    assert any(isinstance(item, IdempotencyKey) for item in db.added)


def test_create_backlog_mission_requires_idempotency() -> None:
    response = _client(FakeDb(), _user()).post(
        "/imperium/missions/backlog",
        json={"title": "Prepare invoice"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing Idempotency-Key header."


def test_create_backlog_mission_with_score_creates_mission_score() -> None:
    payload = BacklogMissionCreateRequest(
        title="Submit urgent paperwork",
        domain="business",
        priority_level=3,
        mission_type_category="cat_b",
        deadline_at=datetime.now(UTC) + timedelta(days=1),
        impact="critical",
        dependency=True,
        recurrence="yearly",
    )
    db = FakeDb()

    response, duplicate = create_backlog_mission(
        db,
        current_user=_user(),
        payload=payload,
        idempotency_key="backlog-score",
        request_method="POST",
        request_path="/imperium/missions/backlog",
    )

    assert duplicate is False
    assert response.score_created is True
    assert response.mission.decision_score is not None
    assert any(isinstance(item, ImperiumMissionScore) for item in db.added)


def test_create_backlog_mission_without_domain_does_not_create_score() -> None:
    payload = BacklogMissionCreateRequest(
        title="Quick errand",
        mission_type_category="cat_h",
        impact="quality_of_life",
    )
    db = FakeDb()

    response, _duplicate = create_backlog_mission(
        db,
        current_user=_user(),
        payload=payload,
        idempotency_key="backlog-no-domain-score",
        request_method="POST",
        request_path="/imperium/missions/backlog",
    )

    assert response.score_created is False
    assert response.mission.decision_score is None
    assert not any(isinstance(item, ImperiumMissionScore) for item in db.added)


def test_list_backlog_missions_user_scoped() -> None:
    current_user = _user()
    matching = _mission(current_user.id, title="Matching", domain="business", priority_level=5)
    db = FakeDb(scalars_results=[[matching], []])

    response = _client(db, current_user).get(
        "/imperium/missions/backlog?limit=10&offset=0&domain=business&priority_level=5"
    )

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["items"][0]["title"] == "Matching"
    query_text = str(db.queries[0])
    assert "imperium_missions.user_id" in query_text
    assert "imperium_missions.status" in query_text
    assert "imperium_missions.domain" in query_text
    assert "imperium_missions.priority_level" in query_text


def test_list_backlog_missions_sorted_by_score_then_priority_level() -> None:
    current_user = _user()
    now = datetime.now(UTC)
    high_score_low_manual_priority = _mission(
        current_user.id,
        title="High score",
        priority_level=10,
        created_at=now,
    )
    low_score_high_manual_priority = _mission(
        current_user.id,
        title="Low score",
        priority_level=1,
        created_at=now,
    )
    no_score_priority_one = _mission(
        current_user.id,
        title="Manual priority one",
        priority_level=1,
        created_at=now,
    )
    no_score_priority_three = _mission(
        current_user.id,
        title="Manual priority three",
        priority_level=3,
        created_at=now,
    )
    db = FakeDb(
        scalars_results=[
            [no_score_priority_three, low_score_high_manual_priority, high_score_low_manual_priority, no_score_priority_one],
            [
                _score(current_user.id, low_score_high_manual_priority.id, bucket=2),
                _score(current_user.id, high_score_low_manual_priority.id, bucket=8),
            ],
        ]
    )

    response = list_backlog_missions(db, current_user=current_user, limit=10, offset=0)

    assert [item.title for item in response.items] == [
        "High score",
        "Low score",
        "Manual priority one",
        "Manual priority three",
    ]


def test_backlog_decision_preview_recommends_first_sorted_candidate() -> None:
    current_user = _user()
    now = datetime.now(UTC)
    high_bucket = _mission(current_user.id, title="High bucket", priority_level=10, created_at=now)
    low_bucket = _mission(current_user.id, title="Low bucket", priority_level=1, created_at=now)
    fifo = _mission(
        current_user.id,
        title="FIFO",
        priority_level=2,
        created_at=now - timedelta(hours=1),
    )
    db = FakeDb(
        scalars_results=[
            [low_bucket, fifo, high_bucket],
            [
                _score(current_user.id, low_bucket.id, bucket=2),
                _score(current_user.id, high_bucket.id, bucket=4),
                _score(current_user.id, fifo.id, bucket=4),
            ],
        ]
    )

    response = get_backlog_decision_preview(db, current_user=current_user, limit=10)

    assert response.recommended_mission_id == fifo.id
    assert [candidate.title for candidate in response.candidates] == ["FIFO", "High bucket", "Low bucket"]
    assert response.candidates[0].score_summary.label == "high"
    assert response.candidates[0].score_summary.reason_codes == [
        "HIGH_PRIORITY_BUCKET",
        "LOW_PRIORITY_LEVEL",
        "FIFO_BACKLOG",
    ]


def test_backlog_preview_and_decision_score_share_public_score_mapping() -> None:
    current_user = _user()
    cases = [(1, "low"), (2, "medium"), (4, "high")]

    for bucket, expected_label in cases:
        mission = _mission(current_user.id, priority_level=3)
        preview = get_backlog_decision_preview(
            FakeDb(scalars_results=[[mission], [_score(current_user.id, mission.id, bucket=bucket)]]),
            current_user=current_user,
        )
        decision_score = get_mission_decision_score(
            FakeDb(scalar_results=[mission, _score(current_user.id, mission.id, bucket=bucket)]),
            current_user=current_user,
            mission_id=mission.id,
        )

        preview_summary = preview.candidates[0].score_summary
        decision_summary = decision_score.score_summary
        assert preview_summary.label == expected_label
        assert decision_summary.label == expected_label
        assert preview_summary.reason_codes is not None
        assert decision_summary.reason_codes is not None
        assert preview_summary.reason_codes[0] == decision_summary.reason_codes[0]


def test_backlog_decision_preview_is_user_scoped() -> None:
    current_user = _user()
    own = _mission(current_user.id, title="Own")
    db = FakeDb(scalars_results=[[own], []])

    response = _client(db, current_user).get("/imperium/missions/backlog/decision-preview")

    assert response.status_code == 200
    assert response.json()["candidate_count"] == 1
    assert response.json()["candidates"][0]["title"] == "Own"
    query_text = str(db.queries[0])
    assert "imperium_missions.user_id" in query_text
    assert "imperium_missions.status" in query_text


def test_backlog_decision_preview_respects_domain_filter() -> None:
    current_user = _user()
    mission = _mission(current_user.id, title="Business", domain="business")
    db = FakeDb(scalars_results=[[mission], []])

    response = _client(db, current_user).get("/imperium/missions/backlog/decision-preview?domain=business")

    assert response.status_code == 200
    assert response.json()["candidates"][0]["domain"] == "business"
    assert "imperium_missions.domain" in str(db.queries[0])


def test_backlog_decision_preview_respects_priority_level_filter() -> None:
    current_user = _user()
    mission = _mission(current_user.id, title="Priority one", priority_level=1)
    db = FakeDb(scalars_results=[[mission], []])

    response = _client(db, current_user).get("/imperium/missions/backlog/decision-preview?priority_level=1")

    assert response.status_code == 200
    assert response.json()["candidates"][0]["priority_level"] == 1
    assert "imperium_missions.priority_level" in str(db.queries[0])


def test_backlog_decision_preview_respects_limit() -> None:
    current_user = _user()
    first = _mission(current_user.id, title="First", created_at=datetime(2026, 5, 1, tzinfo=UTC))
    second = _mission(current_user.id, title="Second", created_at=datetime(2026, 5, 2, tzinfo=UTC))
    db = FakeDb(scalars_results=[[first, second], []])

    response = _client(db, current_user).get("/imperium/missions/backlog/decision-preview?limit=1")

    assert response.status_code == 200
    assert response.json()["candidate_count"] == 1
    assert [candidate["title"] for candidate in response.json()["candidates"]] == ["First"]


def test_backlog_decision_preview_does_not_change_mission_status() -> None:
    current_user = _user()
    mission = _mission(current_user.id, status="backlog")
    db = FakeDb(scalars_results=[[mission], []])

    response = get_backlog_decision_preview(db, current_user=current_user, limit=10)

    assert response.recommended_mission_id == mission.id
    assert mission.status == "backlog"
    assert db.added == []
    assert db.committed is False
    assert db.flushed is False


def test_backlog_decision_preview_does_not_expose_started_or_ended_at() -> None:
    current_user = _user()
    mission = _mission(current_user.id)
    db = FakeDb(scalars_results=[[mission], []])

    response = _client(db, current_user).get("/imperium/missions/backlog/decision-preview")

    assert response.status_code == 200
    body_text = response.text
    assert "started_at" not in body_text
    assert "ended_at" not in body_text


def test_backlog_decision_preview_does_not_expose_internal_coefficients() -> None:
    current_user = _user()
    mission = _mission(current_user.id)
    db = FakeDb(scalars_results=[[mission], [_score(current_user.id, mission.id, bucket=4)]])

    response = _client(db, current_user).get("/imperium/missions/backlog/decision-preview")

    assert response.status_code == 200
    body_text = response.text
    for forbidden in (
        "domain_coefficient",
        "weighted_score",
        "final_weighted_score",
        "position_to_coefficient",
        "intrinsic_score",
    ):
        assert forbidden not in body_text


def test_backlog_decision_preview_include_reasons_false_hides_reason_codes() -> None:
    current_user = _user()
    mission = _mission(current_user.id)
    db = FakeDb(scalars_results=[[mission], [_score(current_user.id, mission.id, bucket=2)]])

    response = _client(db, current_user).get("/imperium/missions/backlog/decision-preview?include_reasons=false")

    assert response.status_code == 200
    score_summary = response.json()["candidates"][0]["score_summary"]
    assert score_summary == {"label": "medium"}


def test_backlog_decision_preview_route_does_not_require_idempotency_key() -> None:
    current_user = _user()
    mission = _mission(current_user.id)
    db = FakeDb(scalars_results=[[mission], []])

    response = _client(db, current_user).get("/imperium/missions/backlog/decision-preview")

    assert response.status_code == 200
    assert response.json()["recommended_mission_id"] == str(mission.id)


def test_promote_backlog_mission_to_active() -> None:
    current_user = _user()
    original_started_at = datetime(2026, 5, 1, 8, 0, tzinfo=UTC)
    mission = _mission(
        current_user.id,
        started_at=original_started_at,
        ended_at=datetime(2026, 5, 1, 9, 0, tzinfo=UTC),
    )
    db = FakeDb(scalar_results=[None, mission, None, None])

    response, duplicate = promote_backlog_mission(
        db,
        current_user=current_user,
        mission_id=mission.id,
        idempotency_key="backlog-promote",
        request_method="POST",
        request_path=f"/imperium/missions/backlog/{mission.id}/promote",
    )

    assert duplicate is False
    assert mission.status == "active"
    assert mission.started_at != original_started_at
    assert mission.ended_at is None
    assert response.status == "promoted"
    assert response.mission.status == "active"
    assert response.mission.started_at == mission.started_at
    assert response.promotion_summary.status == "promoted"
    assert response.promotion_summary.guardrails_checked == [
        "OWNERSHIP_CONFIRMED",
        "MISSION_WAS_BACKLOG",
        "NO_ACTIVE_MISSION_FOUND",
        "IDEMPOTENCY_KEY_ACCEPTED",
    ]
    assert any(isinstance(item, Event) and item.event_type == "planning.mission.started" for item in db.added)


def test_promote_backlog_route_returns_safe_public_summary() -> None:
    current_user = _user()
    mission = _mission(current_user.id, ended_at=datetime(2026, 5, 1, 9, 0, tzinfo=UTC))
    db = FakeDb(scalar_results=[None, mission, None, _score(current_user.id, mission.id, bucket=4)])

    response = _client(db, current_user).post(
        f"/imperium/missions/backlog/{mission.id}/promote",
        headers={"Idempotency-Key": "backlog-promote-summary"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["promotion_summary"]["status"] == "promoted"
    assert body["promotion_summary"]["guardrails_checked"] == [
        "OWNERSHIP_CONFIRMED",
        "MISSION_WAS_BACKLOG",
        "NO_ACTIVE_MISSION_FOUND",
        "IDEMPOTENCY_KEY_ACCEPTED",
    ]
    assert body["promotion_summary"]["safe_explanation"] == (
        "Mission promoted from backlog using deterministic backend guardrails only."
    )
    assert body["mission"]["status"] == "active"
    assert body["mission"]["started_at"] is not None
    assert mission.ended_at is None
    for forbidden in ("ended_at", "domain_coefficient", "weighted_score", "final_weighted_score", "coefficient"):
        assert forbidden not in response.text


def test_promote_backlog_mission_fails_if_active_mission_exists() -> None:
    current_user = _user()
    mission = _mission(current_user.id)
    active = _mission(current_user.id, status="active")
    db = FakeDb(scalar_results=[None, mission, active])

    response = _client(db, current_user).post(
        f"/imperium/missions/backlog/{mission.id}/promote",
        headers={"Idempotency-Key": "backlog-promote-conflict"},
    )

    assert response.status_code == 409
    assert "active mission" in response.json()["detail"]


def test_promote_non_backlog_mission_returns_409() -> None:
    current_user = _user()
    mission = _mission(current_user.id, status="completed")
    db = FakeDb(scalar_results=[None, mission])

    response = _client(db, current_user).post(
        f"/imperium/missions/backlog/{mission.id}/promote",
        headers={"Idempotency-Key": "backlog-promote-non-backlog"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Mission is not in backlog."
    assert db.added == []


def test_promote_foreign_backlog_mission_not_found() -> None:
    current_user = _user()
    db = FakeDb(scalar_results=[None, None])

    response = _client(db, current_user).post(
        f"/imperium/missions/backlog/{uuid4()}/promote",
        headers={"Idempotency-Key": "backlog-promote-foreign"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Mission not found."


def test_backlog_promote_replays_same_idempotency_key_without_second_write() -> None:
    current_user = _user()
    mission_id = uuid4()
    now = datetime.now(UTC).isoformat()
    cached_response = {
        "mission": {
            "id": str(mission_id),
            "status": "active",
            "title": "Replay promoted",
            "category": None,
            "domain": "business",
            "priority_level": 1,
            "mission_type_category": None,
            "planned_start_at": None,
            "planned_end_at": None,
            "started_at": now,
            "created_at": now,
            "updated_at": now,
            "decision_score": None,
        },
        "promotion_summary": {
            "status": "promoted",
            "guardrails_checked": [
                "OWNERSHIP_CONFIRMED",
                "MISSION_WAS_BACKLOG",
                "NO_ACTIVE_MISSION_FOUND",
                "IDEMPOTENCY_KEY_ACCEPTED",
            ],
            "safe_explanation": "Mission promoted from backlog using deterministic backend guardrails only.",
        },
        "event_id": "evt_cached_promote",
        "idempotency_key": "backlog-promote-replay",
        "status": "promoted",
        "decision_score": None,
    }
    existing_key = IdempotencyKey(
        user_id=current_user.id,
        idempotency_key="backlog-promote-replay",
        request_method="POST",
        request_path=f"/imperium/missions/backlog/{mission_id}/promote",
        request_hash=_hash_request("mission.backlog.promoted", {"mission_id": str(mission_id)}),
        status=IdempotencyStatus.completed,
        response_status_code=200,
        response_body=cached_response,
    )
    db = FakeDb(scalar_results=[existing_key])

    response, duplicate = promote_backlog_mission(
        db,
        current_user=current_user,
        mission_id=mission_id,
        idempotency_key="backlog-promote-replay",
        request_method="POST",
        request_path=f"/imperium/missions/backlog/{mission_id}/promote",
    )

    assert duplicate is True
    assert response.mission.id == mission_id
    assert response.promotion_summary.status == "promoted"
    assert db.added == []
    assert db.committed is False


def test_backlog_promote_different_idempotency_key_after_promotion_returns_409() -> None:
    current_user = _user()
    mission = _mission(current_user.id)
    db = FakeDb(scalar_results=[None, mission, None, None, None, mission])
    client = _client(db, current_user)

    first_response = client.post(
        f"/imperium/missions/backlog/{mission.id}/promote",
        headers={"Idempotency-Key": "backlog-promote-first"},
    )
    second_response = client.post(
        f"/imperium/missions/backlog/{mission.id}/promote",
        headers={"Idempotency-Key": "backlog-promote-second"},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "Mission is not in backlog."
    assert mission.status == "active"
    assert sum(isinstance(item, Event) and item.event_type == "planning.mission.started" for item in db.added) == 1


def test_backlog_public_response_does_not_expose_coefficient_or_weighted_score() -> None:
    response = _client(FakeDb(), _user()).post(
        "/imperium/missions/backlog",
        headers={"Idempotency-Key": "backlog-public-shape"},
        json={
            "title": "Scored mission",
            "domain": "business",
            "mission_type_category": "cat_e",
            "impact": "critical",
        },
    )

    assert response.status_code == 201
    body_text = response.text
    for forbidden in ("domain_coefficient", "weighted_score", "final_weighted_score", "position_to_coefficient"):
        assert forbidden not in body_text
    mission = response.json()["mission"]
    assert set(mission) <= {
        "id",
        "title",
        "status",
        "category",
        "domain",
        "priority_level",
        "mission_type_category",
        "planned_start_at",
        "planned_end_at",
        "created_at",
        "updated_at",
        "decision_score",
    }


def test_backlog_create_rejects_client_supplied_score_fields() -> None:
    response = _client(FakeDb(), _user()).post(
        "/imperium/missions/backlog",
        headers={"Idempotency-Key": "backlog-reject-score"},
        json={"title": "Injected score", "domain": "business", "weighted_score": 999},
    )

    assert response.status_code == 422
    assert "Client-supplied score fields are not accepted" in response.text


def test_backlog_idempotent_create_replay_does_not_duplicate_score() -> None:
    current_user = _user()
    mission_id = uuid4()
    now = datetime.now(UTC).isoformat()
    payload = BacklogMissionCreateRequest(
        title="Replay mission",
        domain="business",
        mission_type_category="cat_e",
        impact="critical",
    )
    cached_response = {
        "mission": {
            "id": str(mission_id),
            "status": "backlog",
            "title": payload.title,
            "category": None,
            "domain": "business",
            "priority_level": None,
            "mission_type_category": "cat_e",
            "planned_start_at": None,
            "planned_end_at": None,
            "created_at": now,
            "updated_at": now,
            "decision_score": {
                "priority_bucket": 5,
                "score_status": "partial",
                "missing_fields": ["deadline_at"],
                "source": "decision_framework_v1",
            },
        },
        "event_id": "evt_cached",
        "idempotency_key": "backlog-replay-score",
        "status": "created",
        "score_created": True,
    }
    existing_key = IdempotencyKey(
        user_id=current_user.id,
        idempotency_key="backlog-replay-score",
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
        idempotency_key="backlog-replay-score",
        request_method="POST",
        request_path="/imperium/missions/backlog",
    )

    assert duplicate is True
    assert response.score_created is True
    assert response.mission.id == mission_id
    assert db.added == []
    assert db.committed is False
