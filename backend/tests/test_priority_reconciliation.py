from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium
from app.models.imperium import ImperiumDailyPlan, ImperiumUserPriority
from app.schemas.imperium import CreateDailyPlanRequest, PriorityRuleInput, ReplacePriorityRulesRequest
from app.services.imperium.dashboard import get_dashboard_snapshot
from app.services.imperium.daily_plans import _collect_plan_sources, create_daily_plan
from app.services.imperium.decision_framework import get_canonical_priority_order, get_domain_coefficient


class QueueFakeDb:
    def __init__(
        self,
        *,
        scalar_results: list | None = None,
        scalars_results: list[list] | None = None,
    ) -> None:
        self.scalar_results = list(scalar_results or [])
        self.scalars_results = list(scalars_results or [])
        self.added = []
        self.flushed = False
        self.committed = False
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

    def scalar(self, _query):
        if self.scalar_results:
            return self.scalar_results.pop(0)
        return None

    def scalars(self, _query):
        if self.scalars_results:
            return self.scalars_results.pop(0)
        return []

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


def _canonical_priorities(user_id) -> list[ImperiumUserPriority]:
    return [
        _priority(user_id, domain="health", position=1),
        _priority(user_id, domain="finance", position=2),
        _priority(user_id, domain="business", position=3),
        _priority(user_id, domain="religious", position=4),
    ]


def test_canonical_priority_helper_returns_expected_order() -> None:
    current_user = _user()
    priorities = [
        _priority(current_user.id, domain="business", position=3),
        _priority(current_user.id, domain="health", position=1),
        _priority(current_user.id, domain="religious", position=4),
        _priority(current_user.id, domain="finance", position=2),
    ]
    db = QueueFakeDb(scalars_results=[priorities])

    ordered = get_canonical_priority_order(db, current_user=current_user)

    assert [priority.domain for priority in ordered] == ["health", "finance", "business", "religious"]
    assert [priority.position for priority in ordered] == [1, 2, 3, 4]
    assert db.added == []
    assert db.committed is False


def test_dashboard_uses_decision_framework_priorities() -> None:
    current_user = _user()
    priorities = _canonical_priorities(current_user.id)
    db = QueueFakeDb(
        scalar_results=[None, None, None, None],
        scalars_results=[[], priorities, [], []],
    )

    snapshot = get_dashboard_snapshot(db, current_user=current_user)

    assert [priority.priority_key for priority in snapshot.priorities] == [
        "health",
        "finance",
        "business",
        "religious",
    ]
    assert [priority.rank_order for priority in snapshot.priorities] == [1, 2, 3, 4]
    assert all(priority.importance_score is None for priority in snapshot.priorities)


def test_daily_plan_uses_decision_framework_priorities() -> None:
    current_user = _user()
    priorities = _canonical_priorities(current_user.id)
    db = QueueFakeDb(
        scalar_results=[None, None, None],
        scalars_results=[[], priorities],
    )

    response, duplicate = create_daily_plan(
        db,
        current_user=current_user,
        payload=CreateDailyPlanRequest(local_date=date(2026, 5, 24), title="Patch 7G plan"),
        idempotency_key="daily-plan-df-priorities",
        request_method="POST",
        request_path="/api/imperium/day/plan",
    )

    plan = next(item for item in db.added if isinstance(item, ImperiumDailyPlan))
    priority_block = next(block for block in plan.plan_blocks if block["block_type"] == "priority_context")
    assert duplicate is False
    assert response.plan.generated_from["priority_source"] == "decision_framework"
    assert "priority_rule_ids" not in response.plan.generated_from
    assert priority_block["source"] == "decision_framework"
    assert [item["priority_key"] for item in priority_block["priorities"]] == [
        "health",
        "finance",
        "business",
        "religious",
    ]
    assert all(item["importance_score"] is None for item in priority_block["priorities"])


def test_legacy_priority_endpoint_marked_deprecated() -> None:
    current_user = _user()
    priorities = _canonical_priorities(current_user.id)
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: QueueFakeDb(scalars_results=[priorities])
    client = TestClient(app)

    response = client.get("/imperium/priorities")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "legacy_superseded"
    assert body["deprecated"] is True
    assert body["legacy"] is True
    assert body["canonical_source"] == "imperium_user_priorities"
    assert body["superseded_by"] == "/api/imperium/decision-framework/priorities"
    assert [priority["priority_key"] for priority in body["priorities"]] == [
        "health",
        "finance",
        "business",
        "religious",
    ]
    assert all(priority["importance_score"] is None for priority in body["priorities"])


def test_legacy_priority_write_returns_gone() -> None:
    with pytest.raises(HTTPException) as exc_info:
        imperium.replace_priorities_route(
            payload=ReplacePriorityRulesRequest(
                priorities=[PriorityRuleInput(priority_key="work", label="Work", rank_order=1)]
            ),
            request=SimpleNamespace(method="POST", url=SimpleNamespace(path="/api/imperium/priorities")),
            response=SimpleNamespace(status_code=None),
            current_user=_user(),
            db=QueueFakeDb(),
            idempotency_key="legacy-priority-write",
        )

    assert exc_info.value.status_code == 410
    assert exc_info.value.detail["canonical_source"] == "imperium_user_priorities"
    assert exc_info.value.detail["superseded_by"] == "/api/imperium/decision-framework/priorities"


def test_priority_order_consistent_across_dashboard_and_daily_plan() -> None:
    current_user = _user()
    priorities = _canonical_priorities(current_user.id)
    dashboard_db = QueueFakeDb(
        scalar_results=[None, None, None, None],
        scalars_results=[[], priorities, [], []],
    )
    plan_db = QueueFakeDb(
        scalar_results=[None, None],
        scalars_results=[[], priorities],
    )

    dashboard_snapshot = get_dashboard_snapshot(dashboard_db, current_user=current_user)
    plan_sources = _collect_plan_sources(plan_db, current_user=current_user, local_date=date(2026, 5, 24))

    dashboard_order = [priority.priority_key for priority in dashboard_snapshot.priorities]
    priority_block = next(block for block in plan_sources["plan_blocks"] if block["block_type"] == "priority_context")
    daily_plan_order = [priority["priority_key"] for priority in priority_block["priorities"]]

    assert dashboard_order == daily_plan_order == ["health", "finance", "business", "religious"]
