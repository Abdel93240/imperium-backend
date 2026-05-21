import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumMissionScore, ImperiumUserPriority
from app.schemas.imperium import DecisionFrameworkPrioritiesUpdateRequest, DecisionFrameworkScorePreviewRequest
from app.services.imperium import decision_framework
from app.services.imperium.decision_framework import (
    DecisionFrameworkValidationError,
    compute_intrinsic_score,
    compute_weighted_score,
    get_domain_coefficient,
    get_or_initialize_user_priorities,
    preview_decision_framework_score,
    preview_score_from_mission_like,
    replace_user_priorities,
)


class FakeDb:
    def __init__(self, *, scalars_result=None, scalar_result=None) -> None:
        self.scalars_result = scalars_result or []
        self.scalar_result = scalar_result
        self.added = []
        self.committed = False
        self.flushed = False
        self.rolled_back = False

    def add(self, obj) -> None:
        self._prepare(obj)
        self.added.append(obj)

    def add_all(self, items) -> None:
        for item in items:
            self.add(item)

    def flush(self) -> None:
        self.flushed = True
        for item in self.added:
            self._prepare(item)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def scalars(self, _query):
        return self.scalars_result

    def scalar(self, _query):
        return self.scalar_result

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


def _priority(user_id, *, domain: str, position: int, active: bool = True) -> ImperiumUserPriority:
    now = datetime.now(UTC)
    return ImperiumUserPriority(
        id=uuid4(),
        user_id=user_id,
        domain=domain,
        position=position,
        coefficient=get_domain_coefficient(position),
        is_active=active,
        created_at=now,
        updated_at=now,
    )


def test_default_priorities_created_and_read_correctly() -> None:
    db = FakeDb()
    current_user = _user()

    response = get_or_initialize_user_priorities(db, current_user=current_user)

    assert response.status == "ok"
    assert [item.domain for item in response.priorities] == ["religious", "business", "finance", "health"]
    assert [item.position for item in response.priorities] == [1, 2, 3, 4]
    assert all(item.is_active for item in response.priorities)
    assert len([item for item in db.added if isinstance(item, ImperiumUserPriority)]) == 4
    assert db.committed is True


def test_existing_priorities_are_not_silently_overwritten() -> None:
    current_user = _user()
    existing = [
        _priority(current_user.id, domain="finance", position=1),
        _priority(current_user.id, domain="religious", position=2),
        _priority(current_user.id, domain="business", position=3),
        _priority(current_user.id, domain="health", position=4),
    ]
    db = FakeDb(scalars_result=existing)

    response = get_or_initialize_user_priorities(db, current_user=current_user)

    assert [item.domain for item in response.priorities] == ["finance", "religious", "business", "health"]
    assert db.added == []
    assert db.committed is False


def test_reorder_validates_exact_four_domains_and_derives_coefficients() -> None:
    current_user = _user()
    old = [
        _priority(current_user.id, domain="religious", position=1),
        _priority(current_user.id, domain="business", position=2),
        _priority(current_user.id, domain="finance", position=3),
        _priority(current_user.id, domain="health", position=4),
    ]
    db = FakeDb(scalars_result=old)

    response, duplicate = replace_user_priorities(
        db,
        current_user=current_user,
        payload=DecisionFrameworkPrioritiesUpdateRequest(domains=["health", "finance", "business", "religious"]),
        idempotency_key="decision-priorities-1",
        request_method="POST",
        request_path="/api/imperium/decision-framework/priorities",
    )

    assert duplicate is False
    assert [item.domain for item in response.priorities] == ["health", "finance", "business", "religious"]
    new_priorities = [item for item in db.added if isinstance(item, ImperiumUserPriority)]
    assert [(item.domain, item.position, item.coefficient) for item in new_priorities] == [
        ("health", 1, 10),
        ("finance", 2, 8),
        ("business", 3, 5),
        ("religious", 4, 4),
    ]
    assert all(not item.is_active for item in old)
    assert any(isinstance(item, IdempotencyKey) for item in db.added)
    assert db.committed is True


@pytest.mark.parametrize(
    "domains",
    [
        ["religious", "business", "finance", "finance"],
        ["religious", "business", "finance", "unknown"],
    ],
)
def test_reorder_rejects_duplicate_or_unknown_domains(domains: list[str]) -> None:
    with pytest.raises(DecisionFrameworkValidationError):
        replace_user_priorities(
            FakeDb(),
            current_user=_user(),
            payload=DecisionFrameworkPrioritiesUpdateRequest(domains=domains),
            idempotency_key="decision-priorities-bad",
            request_method="POST",
            request_path="/api/imperium/decision-framework/priorities",
        )


def test_reorder_requires_exactly_four_domains_schema_validation() -> None:
    with pytest.raises(ValueError):
        DecisionFrameworkPrioritiesUpdateRequest(domains=["religious", "business", "finance"])


def test_get_domain_coefficient_uses_internal_mapping() -> None:
    assert [get_domain_coefficient(position) for position in range(1, 5)] == [10, 8, 5, 4]


def test_scoring_clamps_intrinsic_and_uses_coefficient() -> None:
    payload = DecisionFrameworkScorePreviewRequest(
        domain="religious",
        title="Critical mission",
        deadline_at=datetime.now(UTC) - timedelta(days=1),
        impact=30,
        mission_type=20,
        dependency=10,
        recurrence="exceptional",
    )

    preview = preview_decision_framework_score(payload)

    assert preview.intrinsic_score == 100
    assert preview.priority_bucket == 10
    assert preview.score_status == "complete"
    assert preview.domain_position == 1
    assert preview.display_title == "Critical mission"
    assert len(preview.breakdown) == 5
    assert preview.explanation.deadline_points == 30
    assert preview.explanation.mission_type_points == 20
    assert preview.explanation.recurrence_points == 10
    assert "deadline_past" in preview.explanation.flags


def test_score_explanation_uses_canonical_mission_type_and_recurrence_keys() -> None:
    preview = preview_decision_framework_score(
        DecisionFrameworkScorePreviewRequest(
            domain="business",
            impact="critical",
            mission_type="cat_b",
            dependency="some",
            recurrence="monthly",
        )
    )

    explanation = preview.explanation.model_dump()

    assert "mission_type_points" in explanation
    assert "recurrence_points" in explanation
    assert "effort_points" not in explanation
    assert "alignment_points" not in explanation


def test_scoring_reports_missing_fields_instead_of_guessing() -> None:
    preview = preview_decision_framework_score(DecisionFrameworkScorePreviewRequest(domain="health"))

    assert preview.storage_enabled is False
    assert preview.score_status == "empty"
    assert preview.intrinsic_score == 0
    assert set(preview.missing_fields) == {
        "deadline_at",
        "impact",
        "mission_type",
        "dependency",
        "recurrence",
    }
    assert "Aucun signal" in preview.display_summary


def test_compute_helpers_are_deterministic() -> None:
    candidate = {
        "domain": "business",
        "deadline_at": datetime.now(UTC) + timedelta(days=5),
        "impact": 15,
        "mission_type": 10,
        "dependency": "multiple",
        "recurrence": "monthly",
    }

    intrinsic = compute_intrinsic_score(candidate)

    assert intrinsic == 60
    assert compute_weighted_score(intrinsic, 8) == 480


def test_score_preview_endpoint_requires_auth() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    client = TestClient(app)

    response = client.post("/imperium/decision-framework/score-preview", json={"domain": "business"})

    assert response.status_code == 401


def test_score_preview_endpoint_does_not_write_score_rows() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.post(
        "/imperium/decision-framework/score-preview",
        json={"domain": "business", "impact": 10},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["storage_enabled"] is False
    assert body["domain"] == "business"
    assert body["score_status"] == "partial"
    assert "breakdown" in body
    assert "priority_bucket" in body
    assert "final_weighted_score" not in body["explanation"]


def test_score_preview_invalid_domain_returns_422() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.post("/imperium/decision-framework/score-preview", json={"domain": "unknown"})

    assert response.status_code == 422


def test_score_preview_invalid_controlled_score_value_returns_422() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.post(
        "/imperium/decision-framework/score-preview",
        json={"domain": "business", "mission_type": "totally_unknown"},
    )

    assert response.status_code == 422


def test_score_preview_rejects_ambiguous_legacy_fields() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.post(
        "/imperium/decision-framework/score-preview",
        json={"domain": "business", "importance": 10, "urgency": 10, "risk": 10},
    )

    assert response.status_code == 422


def test_score_preview_warns_and_sanitizes_unsafe_payload_fields() -> None:
    response = preview_decision_framework_score(
        DecisionFrameworkScorePreviewRequest(
            domain="finance",
            impact=10,
            payload={"secret_prompt": "DO_NOT_EXPOSE", "raw_payload": {"x": 1}, "safe": "ok"},
        )
    )

    serialized = response.model_dump_json()
    assert "sanitized_payload_field" in response.warnings
    assert "DO_NOT_EXPOSE" not in serialized
    assert "raw_payload" not in serialized


def test_user_priorities_affect_public_priority_bucket_without_exposing_coefficient() -> None:
    current_user = _user()
    priorities = [
        _priority(current_user.id, domain="health", position=1),
        _priority(current_user.id, domain="finance", position=2),
        _priority(current_user.id, domain="business", position=3),
        _priority(current_user.id, domain="religious", position=4),
    ]
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: FakeDb(scalars_result=priorities)
    client = TestClient(app)

    response = client.post(
        "/imperium/decision-framework/score-preview",
        json={"domain": "health", "impact": 10, "mission_type": 5},
    )

    assert response.status_code == 200
    body = response.json()
    serialized = json.dumps(body)
    assert body["domain_position"] == 1
    assert body["priority_bucket"] == 4
    assert "domain_coefficient" not in serialized
    assert "weighted_score" not in serialized


def test_legacy_aliases_effort_and_alignment_still_accepted_with_warnings() -> None:
    preview = preview_decision_framework_score(
        DecisionFrameworkScorePreviewRequest(
            domain="business",
            impact=10,
            effort="cat_g",
            dependency="some",
            alignment="monthly",
        )
    )

    explanation = preview.explanation.model_dump()
    assert "canonical_alias:effort_used_for_mission_type" in preview.warnings
    assert "canonical_alias:alignment_used_for_recurrence" in preview.warnings
    assert "mission_type_points" in explanation
    assert "recurrence_points" in explanation
    assert "effort_points" not in explanation
    assert "alignment_points" not in explanation
    assert preview.intrinsic_score == 25


def test_legacy_points_fields_are_explicitly_marked_as_warnings() -> None:
    preview = preview_decision_framework_score(
        DecisionFrameworkScorePreviewRequest(
            domain="business",
            impact_points=10,
            effort_points=5,
            dependency_points=5,
            alignment_points=3,
        )
    )

    assert "legacy_field:impact_points" in preview.warnings
    assert "legacy_field:effort_points" in preview.warnings
    assert "legacy_field:alignment_points" in preview.warnings
    assert preview.intrinsic_score == 23


def test_score_preview_does_not_expose_domain_coefficient() -> None:
    preview = preview_decision_framework_score(
        DecisionFrameworkScorePreviewRequest(domain="religious", impact=30, mission_type=20)
    )

    serialized = preview.model_dump_json()

    assert "domain_coefficient" not in serialized


def test_score_preview_does_not_expose_weighted_score() -> None:
    preview = preview_decision_framework_score(
        DecisionFrameworkScorePreviewRequest(domain="religious", impact=30, mission_type=20)
    )
    body = preview.model_dump()

    assert "weighted_score" not in body
    assert "final_weighted_score" not in body["explanation"]


def test_score_preview_includes_priority_bucket() -> None:
    preview = preview_decision_framework_score(
        DecisionFrameworkScorePreviewRequest(domain="religious", impact=30, mission_type=20)
    )

    assert isinstance(preview.priority_bucket, int)
    assert 1 <= preview.priority_bucket <= 10


def test_mission_like_preview_helper_is_read_only_and_partial() -> None:
    priorities = [
        _priority(uuid4(), domain="finance", position=1),
        _priority(uuid4(), domain="religious", position=2),
        _priority(uuid4(), domain="business", position=3),
        _priority(uuid4(), domain="health", position=4),
    ]

    preview = preview_score_from_mission_like(
        {
            "title": "Pay tax document",
            "category": "finance",
            "planned_end_at": datetime.now(UTC) + timedelta(days=2),
            "impact": "critical",
            "mission_type": "cat_b",
        },
        priorities=priorities,
    )

    assert preview.domain == "finance"
    assert preview.display_title == "Pay tax document"
    assert preview.domain_position == 1
    assert preview.priority_bucket >= 1
    assert preview.score_status == "partial"
    assert "dependency" in preview.missing_fields
    assert preview.storage_enabled is False


def test_priority_update_route_is_scoped_to_current_user(monkeypatch) -> None:
    current_user = _user()
    seen = {}

    def fake_replace(_db, *, current_user, payload, idempotency_key, request_method, request_path):
        seen["current_user_id"] = current_user.id
        priorities = [
            _priority(current_user.id, domain=domain, position=position)
            for position, domain in enumerate(payload.domains, start=1)
        ]
        return decision_framework._priorities_response(priorities, status="updated", idempotency_key=idempotency_key), False

    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: FakeDb()
    monkeypatch.setattr(imperium, "replace_user_priorities", fake_replace)
    client = TestClient(app)

    response = client.post(
        "/imperium/decision-framework/priorities",
        json={"domains": ["religious", "business", "finance", "health"]},
        headers={"Idempotency-Key": "priority-route-key"},
    )

    assert response.status_code == 200
    assert seen["current_user_id"] == current_user.id


def test_schema_endpoint_documents_disabled_ai_and_embeddings() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_current_user] = _user
    client = TestClient(app)

    response = client.get("/imperium/decision-framework/schema")

    assert response.status_code == 200
    body = response.json()
    assert body["scoring_enabled"] is True
    assert body["monthly_planning_enabled"] is False
    assert body["daily_adaptation_enabled"] is False
    assert body["real_ai_enabled"] is False
    assert body["embeddings_enabled"] is False
    assert body["supported_domains"] == ["religious", "business", "finance", "health"]


def test_schema_endpoint_does_not_expose_position_to_coefficient_mapping() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_current_user] = _user
    client = TestClient(app)

    response = client.get("/imperium/decision-framework/schema")

    assert response.status_code == 200
    body = response.json()
    serialized = json.dumps(body)
    assert body["coefficient_policy"]["visibility"] == "internal"
    assert "position_to_coefficient" not in body["coefficient_policy"]
    assert "position_to_coefficient" not in serialized
    assert "10" not in json.dumps(body["coefficient_policy"])
    assert "8" not in json.dumps(body["coefficient_policy"])
    assert "5" not in json.dumps(body["coefficient_policy"])
    assert "4" not in json.dumps(body["coefficient_policy"])


def test_decision_framework_models_have_no_vector_or_embedding_columns() -> None:
    priority_columns = set(ImperiumUserPriority.__table__.columns.keys())
    score_columns = set(ImperiumMissionScore.__table__.columns.keys())

    assert "embedding" not in priority_columns
    assert "vector" not in priority_columns
    assert "embedding" not in score_columns
    assert "vector" not in score_columns
