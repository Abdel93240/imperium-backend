"""PostgreSQL : versions du plan vivant (doc 43 §20, doc 05 D4) — on versionne, on n'écrase pas."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("plan versions DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium  # noqa: E402
from app.models import ai  # noqa: E402,F401 - tâche IA créée par le replan
from app.models.auth import User  # noqa: E402
from app.models.imperium import ImperiumDailyPlan, PlanningDay  # noqa: E402
from app.schemas.imperium import ReplanProposalAttachRequest, ReplanRequestCreate  # noqa: E402
from app.services.imperium.replan import accept_replan, attach_replan_proposal, request_hook_replan, request_replan  # noqa: E402

T0 = datetime(2026, 10, 17, 7, 24, tzinfo=UTC)
ORIGINAL = [{"block_type": "mission", "title": "Lecture"}]


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    with Session(engine) as session:
        yield session
        session.rollback()


def _user(db) -> User:
    user_id = uuid4()
    db.execute(
        text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) VALUES (:id, :email, FALSE, now(), now())"),
        {"id": str(user_id), "email": f"planver-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/api/imperium")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _setup(db):
    user = _user(db)
    db.add(PlanningDay(user_id=user.id, started_at=T0 - timedelta(hours=4), start_local_date=date(2026, 10, 17),
                       timezone="Europe/Paris", felt_energy=3, idempotency_key=uuid4().hex))
    plan = ImperiumDailyPlan(user_id=user.id, local_date=date(2026, 10, 17), timezone="Europe/Paris", plan_status="active",
                             generated_from={}, plan_blocks=ORIGINAL)
    db.add(plan)
    db.commit()
    return user, plan


def _accept(db, user, request_id, title, now):
    attach_replan_proposal(db, request_id=request_id, idempotency_key=uuid4().hex, payload=ReplanProposalAttachRequest(
        blocks=[{"block_type": "mission", "title": title, "change": "new"},
                {"block_type": "mission", "title": "Lecture", "change": "removed"}],
        rationale="Proposition de test."))
    accept_replan(db, current_user=user, replan_id=request_id, now=now)


def test_each_accepted_replan_adds_a_version(db) -> None:
    user, plan = _setup(db)
    client = _client(db, user)
    before = client.get(f"/api/imperium/day/plan/{plan.id}/versions").json()
    assert (before["current_version"], [(v["version"], v["is_current"]) for v in before["items"]]) == (0, [(0, True)])
    first, _ = request_replan(db, current_user=user, payload=ReplanRequestCreate(reason_category="fatigue", reason_detail="Nuit courte."),
                              idempotency_key=uuid4().hex, request_method="POST", request_path="/api/imperium/day/replan", now=T0)
    _accept(db, user, first.id, "Sieste", T0 + timedelta(minutes=1))
    second = request_hook_replan(db, current_user=user, hook_type="ghusl_required", now=T0 + timedelta(minutes=2))
    _accept(db, user, second.id, "Ghusl", T0 + timedelta(minutes=3))
    body = client.get(f"/api/imperium/day/plan/{plan.id}/versions").json()
    assert body["current_version"] == 2
    assert [(v["version"], v["reason"], v["trigger"], v["is_current"]) for v in body["items"]] == [
        (2, "ghusl_required", "hook", True), (1, "fatigue", "manual", False), (0, None, None, False),
    ]
    assert body["items"][2]["plan_blocks"] == ORIGINAL  # le plan d'origine est conservé
    assert [b["title"] for b in body["items"][0]["plan_blocks"]] == ["Ghusl"]
    assert body["items"][1]["source_replan_event_id"] == str(first.id)


def test_versions_are_private(db) -> None:
    _, plan = _setup(db)
    assert _client(db, _user(db)).get(f"/api/imperium/day/plan/{plan.id}/versions").status_code == 404
    assert _client(db, _user(db)).get(f"/api/imperium/day/plan/{uuid4()}/versions").status_code == 404
