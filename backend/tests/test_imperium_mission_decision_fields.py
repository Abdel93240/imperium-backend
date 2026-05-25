from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.event import Event
from app.models.enums import IdempotencyStatus
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumMission, ImperiumMissionScore, ImperiumUserPriority
from app.schemas.imperium import MissionResponse, StartMissionRequest
from app.services.imperium.decision_framework import get_domain_coefficient
from app.services.imperium.missions import _hash_request, get_mission_decision_score, start_mission


class FakeDb:
    def __init__(self, *, scalar_result=None, scalar_results=None, scalars_result=None) -> None:
        self.scalar_result = scalar_result
        self.scalar_results = list(scalar_results) if scalar_results is not None else None
        self.scalars_result = scalars_result or []
        self.added = []
        self.flushed = False
        self.committed = False

    def add(self, obj) -> None:
        self._prepare(obj)
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed = True
        for item in self.added:
            self._prepare(item)

    def commit(self) -> None:
        self.committed = True

    def scalar(self, _query):
        if self.scalar_results is not None:
            if self.scalar_results:
                return self.scalar_results.pop(0)
            return self.scalar_result
        return self.scalar_result

    def scalars(self, _query):
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


def _priority(user_id, *, domain: str, position: int) -> ImperiumUserPriority:
    now = datetime.now(UTC)
    return ImperiumUserPriority(
        id=uuid4(),
        user_id=user_id,
        domain=domain,
        position=position,
        coefficient=get_domain_coefficient(position),
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def test_imperium_mission_accepts_decision_framework_fields() -> None:
    now = datetime.now(UTC)
    mission = ImperiumMission(
        id=uuid4(),
        user_id=uuid4(),
        title="Prepare tax file",
        category="admin",
        domain="finance",
        priority_level=7,
        mission_type_category="cat_b",
        status="active",
        started_at=now,
        created_at=now,
        updated_at=now,
    )

    response = MissionResponse.model_validate(mission)

    assert response.domain == "finance"
    assert response.priority_level == 7
    assert response.mission_type_category == "cat_b"


@pytest.mark.parametrize("domain", ["religious", "business", "finance", "health"])
def test_mission_domain_validation_accepts_supported_domains(domain: str) -> None:
    payload = StartMissionRequest(title="Mission", domain=domain)

    assert payload.domain == domain


def test_mission_domain_validation_rejects_unknown_domain() -> None:
    with pytest.raises(ValueError):
        StartMissionRequest(title="Mission", domain="family")


def test_mission_priority_level_validation_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        StartMissionRequest(title="Mission", priority_level=11)


def test_mission_type_category_validation_rejects_unknown_category() -> None:
    with pytest.raises(ValueError):
        StartMissionRequest(title="Mission", mission_type_category="cat_z")


def test_start_mission_with_decision_fields_persists_them() -> None:
    db = FakeDb()
    current_user = _user()
    payload = StartMissionRequest(
        title="Prepare rent transfer",
        category="admin",
        domain="finance",
        priority_level=6,
        mission_type_category="cat_b",
    )

    response, duplicate = start_mission(
        db,
        current_user=current_user,
        payload=payload,
        idempotency_key="mission-decision-fields-1",
        request_method="POST",
        request_path="/api/imperium/missions/start",
    )

    mission = next(item for item in db.added if isinstance(item, ImperiumMission))
    assert duplicate is False
    assert mission.domain == "finance"
    assert mission.priority_level == 6
    assert mission.mission_type_category == "cat_b"
    assert response.mission.domain == "finance"
    assert response.mission.priority_level == 6
    assert response.mission.mission_type_category == "cat_b"
    assert response.score_created is True
    assert response.decision_score is not None
    assert response.decision_score.source == "decision_framework_v1"
    assert any(isinstance(item, Event) for item in db.added)
    assert any(isinstance(item, IdempotencyKey) for item in db.added)
    assert any(isinstance(item, ImperiumMissionScore) for item in db.added)
    assert db.committed is True


def test_start_mission_without_decision_fields_still_works() -> None:
    db = FakeDb()
    current_user = _user()
    payload = StartMissionRequest(title="Simple mission")

    response, duplicate = start_mission(
        db,
        current_user=current_user,
        payload=payload,
        idempotency_key="mission-no-decision-fields",
        request_method="POST",
        request_path="/api/imperium/missions/start",
    )

    assert duplicate is False
    assert response.mission.domain is None
    assert response.mission.priority_level is None
    assert response.mission.mission_type_category is None
    assert response.mission.status == "active"
    assert response.score_created is False
    assert response.decision_score is None


def test_start_mission_with_domain_and_scoring_inputs_creates_mission_score() -> None:
    db = FakeDb()
    payload = StartMissionRequest(
        title="Prepare monthly invoice",
        domain="business",
        deadline_at=datetime.now(UTC) + timedelta(days=2),
        impact="critical",
        mission_type="cat_e",
        dependency=True,
        recurrence="monthly",
    )

    response, duplicate = start_mission(
        db,
        current_user=_user(),
        payload=payload,
        idempotency_key="mission-score-write",
        request_method="POST",
        request_path="/api/imperium/missions/start",
    )

    score = next(item for item in db.added if isinstance(item, ImperiumMissionScore))
    assert duplicate is False
    assert score.domain == "business"
    assert score.source == "decision_framework_v1"
    assert score.explanation["mission_type_points"] == 10
    assert score.explanation["recurrence_points"] == 5
    assert response.score_created is True
    assert response.decision_score is not None
    assert response.decision_score.priority_bucket >= 1


def test_start_mission_without_domain_does_not_create_mission_score() -> None:
    db = FakeDb()
    payload = StartMissionRequest(
        title="Prepare monthly invoice",
        impact="critical",
        mission_type="cat_e",
    )

    response, _duplicate = start_mission(
        db,
        current_user=_user(),
        payload=payload,
        idempotency_key="mission-no-domain-score",
        request_method="POST",
        request_path="/api/imperium/missions/start",
    )

    assert response.score_created is False
    assert response.decision_score is None
    assert not any(isinstance(item, ImperiumMissionScore) for item in db.added)


def test_start_mission_without_scoring_signals_does_not_create_mission_score() -> None:
    db = FakeDb()
    payload = StartMissionRequest(
        title="Prepare monthly invoice",
        domain="business",
        priority_level=5,
    )

    response, _duplicate = start_mission(
        db,
        current_user=_user(),
        payload=payload,
        idempotency_key="mission-no-scoring-signals",
        request_method="POST",
        request_path="/api/imperium/missions/start",
    )

    assert response.score_created is False
    assert response.decision_score is None
    assert not any(isinstance(item, ImperiumMissionScore) for item in db.added)


def test_start_mission_uses_mission_type_category_as_scoring_input_when_mission_type_missing() -> None:
    db = FakeDb()
    payload = StartMissionRequest(
        title="Prepare monthly invoice",
        domain="business",
        mission_type_category="cat_e",
    )

    start_mission(
        db,
        current_user=_user(),
        payload=payload,
        idempotency_key="mission-category-score",
        request_method="POST",
        request_path="/api/imperium/missions/start",
    )

    score = next(item for item in db.added if isinstance(item, ImperiumMissionScore))
    assert score.explanation["mission_type_points"] == 10


def test_start_mission_rejects_conflicting_mission_type_and_category() -> None:
    with pytest.raises(ValueError):
        StartMissionRequest(
            title="Prepare monthly invoice",
            domain="business",
            mission_type="cat_a",
            mission_type_category="cat_b",
        )


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
def test_start_mission_rejects_client_supplied_score_fields(field_name: str) -> None:
    with pytest.raises(ValueError):
        StartMissionRequest.model_validate({"title": "Mission", field_name: 10})


def test_mission_score_uses_user_active_priority_order() -> None:
    current_user = _user()
    priorities = [
        _priority(current_user.id, domain="health", position=1),
        _priority(current_user.id, domain="finance", position=2),
        _priority(current_user.id, domain="business", position=3),
        _priority(current_user.id, domain="religious", position=4),
    ]
    db = FakeDb(scalars_result=priorities)
    payload = StartMissionRequest(
        title="Health appointment",
        domain="health",
        mission_type_category="cat_c",
    )

    start_mission(
        db,
        current_user=current_user,
        payload=payload,
        idempotency_key="mission-priority-score",
        request_method="POST",
        request_path="/api/imperium/missions/start",
    )

    score = next(item for item in db.added if isinstance(item, ImperiumMissionScore))
    assert score.domain_coefficient == 10
    assert score.explanation["priority_bucket"] >= 1


def test_mission_score_response_does_not_expose_coefficient_or_weighted_score() -> None:
    db = FakeDb()
    payload = StartMissionRequest(
        title="Prepare monthly invoice",
        domain="business",
        mission_type_category="cat_e",
    )

    response, _duplicate = start_mission(
        db,
        current_user=_user(),
        payload=payload,
        idempotency_key="mission-public-score-summary",
        request_method="POST",
        request_path="/api/imperium/missions/start",
    )

    serialized = response.model_dump_json()
    assert "decision_score" in serialized
    assert "priority_bucket" in serialized
    assert "domain_coefficient" not in serialized
    assert "weighted_score" not in serialized
    assert "final_weighted_score" not in serialized


def test_idempotent_start_mission_does_not_duplicate_mission_score() -> None:
    payload = StartMissionRequest(
        title="Prepare monthly invoice",
        domain="business",
        mission_type_category="cat_e",
    )
    cached_response = {
        "mission": {
            "id": str(uuid4()),
            "status": "active",
            "title": payload.title,
            "category": None,
            "domain": "business",
            "priority_level": None,
            "mission_type_category": "cat_e",
            "planned_start_at": None,
            "planned_end_at": None,
            "started_at": datetime.now(UTC).isoformat(),
            "ended_at": None,
            "completion_note": None,
            "failure_reason": None,
            "user_reported_signals": None,
            "ai_usable_reason": None,
            "event_id": "evt_cached",
            "idempotency_key": "mission-idempotent-score",
        },
        "event_id": "evt_cached",
        "idempotency_key": "mission-idempotent-score",
        "status": "started",
        "score_created": True,
        "decision_score": {
            "intrinsic_score": 10,
            "priority_bucket": 4,
            "score_status": "partial",
            "missing_fields": ["deadline_at", "impact", "dependency", "recurrence"],
            "source": "decision_framework_v1",
        },
    }
    existing_key = IdempotencyKey(
        user_id=uuid4(),
        idempotency_key="mission-idempotent-score",
        request_method="POST",
        request_path="/api/imperium/missions/start",
        request_hash=_hash_request("mission.started", payload.model_dump(mode="json")),
        status=IdempotencyStatus.completed,
        response_status_code=201,
        response_body=cached_response,
    )
    db = FakeDb(scalar_results=[existing_key])

    response, duplicate = start_mission(
        db,
        current_user=_user(existing_key.user_id),
        payload=payload,
        idempotency_key="mission-idempotent-score",
        request_method="POST",
        request_path="/api/imperium/missions/start",
    )

    assert duplicate is True
    assert response.score_created is True
    assert not any(isinstance(item, ImperiumMissionScore) for item in db.added)


def test_mission_decision_score_read_does_not_expose_coefficient_or_weighted_score() -> None:
    user_id = uuid4()
    mission_id = uuid4()
    now = datetime.now(UTC)
    mission = ImperiumMission(
        id=mission_id,
        user_id=user_id,
        title="Prepare monthly invoice",
        status="active",
        started_at=now,
        created_at=now,
        updated_at=now,
    )
    score = ImperiumMissionScore(
        id=uuid4(),
        user_id=user_id,
        mission_id=mission_id,
        domain="business",
        intrinsic_score=10,
        domain_coefficient=8,
        weighted_score=80,
        explanation={
            "deadline_points": 0,
            "impact_points": 0,
            "mission_type_points": 10,
            "dependency_points": 0,
            "recurrence_points": 0,
            "missing_fields": ["deadline_at", "impact", "dependency", "recurrence"],
            "final_intrinsic_score": 10,
            "flags": [],
            "priority_bucket": 3,
            "score_status": "partial",
            "source": "decision_framework_v1",
        },
        source="decision_framework_v1",
        created_at=now,
        updated_at=now,
    )
    db = FakeDb(scalar_results=[mission, score])

    response = get_mission_decision_score(db, current_user=_user(user_id), mission_id=mission_id)
    serialized = response.model_dump_json()

    assert response.priority_bucket == 3
    assert response.score_summary.label == "medium"
    assert "domain_coefficient" not in serialized
    assert "weighted_score" not in serialized
    assert "final_weighted_score" not in serialized
