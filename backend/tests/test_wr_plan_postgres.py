"""PostgreSQL : plan initial, v_plan_current, activation et retour arrière (spec WR §3.5, carte ACT-WR-18)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("wr plan DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.exc import DBAPIError, IntegrityError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import wr  # noqa: E402
from app.models import ai  # noqa: E402,F401 - FK de la session WR vers ai_tasks
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.imperium import ImperiumWeeklyReviewSession  # noqa: E402
from app.models.wr import PlanDelta, PlanVersion  # noqa: E402
from app.schemas.wr import PlanInitialRequest  # noqa: E402
from app.services.wr import digest, plan  # noqa: E402

START = date(2026, 10, 19)


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
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"plan-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _enable(db, value: bool = True) -> None:
    version = db.scalar(text("SELECT coalesce(max(version), 0) + 1 FROM parameters WHERE code = 'wr.plan_enabled'"))
    db.execute(text("INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version) "
                    "VALUES (gen_random_uuid(), 'wr.plan_enabled', 'wr', CAST(:v AS jsonb), 'bool', 'test', 'user', :n)"),
               {"v": "true" if value else "false", "n": version})


def _request(**overrides) -> PlanInitialRequest:
    body = {"horizon_start": START.isoformat(), "horizon_end": (START + timedelta(days=27)).isoformat(),
            "rationale_fr": "Plan saisi.",
            "plan": {"items": [{"ref": "mission:permis", "title_fr": "Dossier permis", "week": 1},
                               {"ref": "objective:epargne", "title_fr": "Épargne", "week": 3}]}}
    return PlanInitialRequest.model_validate({**body, **overrides})


def _create(db, user, **overrides):
    return plan.create_initial(db, current_user=user, request=_request(**overrides),
                               idempotency_key=uuid4().hex, request_path="/api/wr/plan/initial")


def test_initial_plan_is_proposed_then_activated_by_the_user(db) -> None:
    user = _user(db)
    proposed = _create(db, user)
    assert (proposed.status, proposed.origin, plan.current_plan(db, current_user=user)) == ("proposed", "initial", None)
    active = plan.activate(db, current_user=user, version_id=proposed.id)
    assert active.status == "active" and plan.activate(db, current_user=user, version_id=proposed.id).activated_at == active.activated_at
    current = plan.current_plan(db, current_user=user)
    assert (current.plan_version_id, current.applied_delta_ids, len(current.plan["items"])) == (proposed.id, [], 2)
    with pytest.raises(plan.PlanStateError) as again:
        _create(db, user)
    assert again.value.code == "PLAN_ALREADY_ACTIVE"
    events = db.scalars(select(Event.event_type).where(Event.user_id == user.id).order_by(Event.occurred_at)).all()
    assert events == ["planning.plan.proposed", "planning.plan.activated"]


def test_view_applies_only_applied_deltas_in_order(db) -> None:
    user = _user(db)
    version = plan.activate(db, current_user=user, version_id=_create(db, user).id)
    now = datetime.now(UTC)
    for offset, status, operations in (
        (1, "applied", [{"op": "move", "target_ref": "mission:permis", "params": {"to_week": 2}}]),
        (2, "proposed", [{"op": "remove", "target_ref": "objective:epargne"}]),
        (3, "applied", [{"op": "modify", "target_ref": "mission:permis", "params": {"title_fr": "Permis D"}}]),
    ):
        db.add(PlanDelta(user_id=user.id, plan_version_id=version.id, operations=operations, origin="user_request",
                         status=status, applied_at=now + timedelta(minutes=offset) if status == "applied" else None))
    db.commit()
    current = plan.current_plan(db, current_user=user)
    assert len(current.applied_delta_ids) == 2
    assert [(item["ref"], item["title_fr"], item["week"]) for item in current.plan["items"]] == [
        ("mission:permis", "Permis D", 2), ("objective:epargne", "Épargne", 3)]


def test_supersede_is_the_rollback_and_delete_is_forbidden(db) -> None:
    user = _user(db)
    first = plan.activate(db, current_user=user, version_id=_create(db, user).id)
    gone = plan.supersede(db, current_user=user, version_id=first.id, reason_fr="Plan faux.")
    assert (gone.status, gone.superseded_reason_fr, plan.current_plan(db, current_user=user)) == ("superseded", "Plan faux.", None)
    with pytest.raises(plan.PlanStateError) as revived:
        plan.activate(db, current_user=user, version_id=first.id)
    assert revived.value.code == "PLAN_SUPERSEDED"
    second = _create(db, user)
    third = _create(db, user)
    plan.activate(db, current_user=user, version_id=second.id)
    plan.activate(db, current_user=user, version_id=third.id)  # la version active précédente passe superseded
    statuses = {row.id: row.status for row in db.scalars(select(PlanVersion).where(PlanVersion.user_id == user.id))}
    assert statuses == {first.id: "superseded", second.id: "superseded", third.id: "active"}
    with pytest.raises(DBAPIError):
        db.execute(text("DELETE FROM plan_versions WHERE id = :id"), {"id": first.id})
    db.rollback()
    with pytest.raises(IntegrityError):  # une seule version active
        db.execute(text("UPDATE plan_versions SET status = 'active', activated_at = now() WHERE id = :id"), {"id": second.id})
    db.rollback()


def test_digest_carries_plan_state_only_when_enabled(db) -> None:
    user = _user(db)
    week_start = date.today() - timedelta(days=date.today().weekday())
    db.add(ImperiumWeeklyReviewSession(user_id=user.id, week_start=week_start, week_end=week_start + timedelta(days=6),
                                       status="conversation_active", launched_at=datetime.now(UTC)))
    db.commit()
    version = plan.activate(db, current_user=user, version_id=_create(db, user).id)
    _enable(db, False)
    first, _ = digest.assemble_digest(db, current_user=user)
    assert "plan_state" not in first.digest and first.digest["unavailable"] == ["plan_state"]
    db.delete(first)
    db.commit()
    _enable(db, True)
    second, _ = digest.assemble_digest(db, current_user=user)
    state = second.digest["plan_state"]
    assert (state["plan_version_id"], state["applied_deltas"], second.digest["unavailable"]) == (str(version.id), 0, [])
    assert [item["ref"] for item in state["plan"]["items"]] == ["mission:permis", "objective:epargne"]


def test_plan_routes(db) -> None:
    user = _user(db)
    app = FastAPI()
    app.include_router(wr.router, prefix="/api/wr")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    _enable(db, False)
    db.commit()
    assert client.get("/api/wr/plan/current").json()["code"] == "PLAN_DISABLED"
    _enable(db, True)
    db.commit()
    assert client.get("/api/wr/plan/current").status_code == 404
    body = _request().model_dump(mode="json")
    assert client.post("/api/wr/plan/initial", json=body).status_code == 400  # sans Idempotency-Key
    beyond = {**body, "plan": {"items": [{"ref": "mission:x", "title_fr": "X", "week": 5}]}}
    assert client.post("/api/wr/plan/initial", json=beyond, headers={"Idempotency-Key": uuid4().hex}).status_code == 422
    key = uuid4().hex
    created = client.post("/api/wr/plan/initial", json=body, headers={"Idempotency-Key": key})
    replay = client.post("/api/wr/plan/initial", json=body, headers={"Idempotency-Key": key})
    assert (created.status_code, replay.json()["id"]) == (201, created.json()["id"])
    version_id = created.json()["id"]
    assert client.post(f"/api/wr/plan/versions/{version_id}/activate").json()["status"] == "active"
    assert client.get("/api/wr/plan/current").json()["plan_version_id"] == version_id
    assert client.post(f"/api/wr/plan/versions/{uuid4()}/activate").status_code == 404
    assert client.post(f"/api/wr/plan/versions/{version_id}/supersede", json={}).status_code == 422
    assert client.post(f"/api/wr/plan/versions/{version_id}/supersede", json={"reason_fr": "Non."}).json()["status"] == "superseded"
    assert [v["status"] for v in client.get("/api/wr/plan/versions").json()["versions"]] == ["superseded"]
