"""PostgreSQL : régénération choc du plan en essai à blanc (spec WR §8.1, §13.6, carte ACT-WR-20)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("wr plan shock DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import wr  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.wr import PlanDelta, PlanVersion  # noqa: E402
from app.schemas.wr import PlanInitialRequest, PlanShockRequest  # noqa: E402
from app.services.wr import plan  # noqa: E402

START = date(2026, 10, 19)
NOW = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)


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
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"shock-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _active_plan(db, user):
    request = PlanInitialRequest.model_validate({
        "horizon_start": START.isoformat(), "horizon_end": (START + timedelta(days=27)).isoformat(),
        "rationale_fr": "Plan saisi.",
        "plan": {"items": [{"ref": "mission:permis", "title_fr": "Dossier permis", "week": 1},
                           {"ref": "objective:epargne", "title_fr": "Épargne", "week": 3}]}})
    proposed = plan.create_initial(db, current_user=user, request=request, idempotency_key=uuid4().hex,
                                   request_path="/api/wr/plan/initial")
    return plan.activate(db, current_user=user, version_id=proposed.id)


def _shock(db, user, reason="disabling_injury", key=None):
    return plan.request_shock(db, current_user=user, request=PlanShockRequest(reason_code=reason),
                              idempotency_key=key or uuid4().hex, request_path="/api/wr/plan/shock", now=NOW)


def test_seeded_taxonomy_and_switch(db) -> None:
    assert set(plan.shock_taxonomy(db)) == {
        "vehicle_accident", "immobilizing_breakdown", "major_family_event", "income_source_loss",
        "disabling_injury", "housing_disaster"}
    assert plan.shock_enabled(db) is False


def test_shock_proposes_a_dry_run_regeneration_never_activated(db) -> None:
    user = _user(db)
    active = _active_plan(db, user)
    db.add(PlanDelta(user_id=user.id, plan_version_id=active.id, origin="user_request", status="applied",
                     applied_at=datetime.now(UTC),
                     operations=[{"op": "move", "target_ref": "mission:permis", "params": {"to_week": 2}}]))
    db.commit()
    proposed = _shock(db, user)
    assert (proposed.status, proposed.origin, proposed.model_used) == ("proposed", "shock_regen", "dry_run")
    assert (proposed.horizon_start, proposed.horizon_end) == (date(2026, 11, 2), date(2026, 11, 29))
    assert proposed.rationale_fr.startswith("[essai] Régénération choc (Blessure invalidante)")
    # Copie du plan courant : le delta appliqué est intégré.
    assert [(i["ref"], i["week"]) for i in proposed.plan["items"]] == [("mission:permis", 2), ("objective:epargne", 3)]
    # Jamais auto-appliquée : le plan actif reste celui de l'utilisateur.
    assert plan.current_plan(db, current_user=user).plan_version_id == active.id
    shock = db.get(Event, proposed.origin_ref)
    assert (shock.event_type, shock.payload) == ("planning.plan.shock_requested",
                                                 {"reason_code": "disabling_injury", "active_plan_version_id": str(active.id)})
    regenerated = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "planning.plan.regenerated"))
    assert regenerated.causation_id == shock.event_id
    assert (regenerated.payload["plan_version_id"], regenerated.payload["origin_ref"], regenerated.payload["dry_run"]) == (
        str(proposed.id), str(shock.id), True)

    with pytest.raises(plan.PlanStateError) as pending:
        _shock(db, user, reason="vehicle_accident")
    assert pending.value.code == "PLAN_REGEN_PENDING"
    db.rollback()
    # Validation par l'utilisateur : active, l'ancienne superseded et toujours interrogeable.
    plan.activate(db, current_user=user, version_id=proposed.id)
    statuses = {row.id: row.status for row in db.scalars(select(PlanVersion).where(PlanVersion.user_id == user.id))}
    assert statuses == {active.id: "superseded", proposed.id: "active"}
    assert plan.current_plan(db, current_user=user).applied_delta_ids == []


def test_shock_refusals(db, monkeypatch) -> None:
    user = _user(db)
    with pytest.raises(plan.PlanStateError) as no_plan:
        _shock(db, user)
    assert no_plan.value.code == "PLAN_NOT_ACTIVE"
    db.rollback()
    with pytest.raises(plan.PlanShockReasonError):
        _shock(db, user, reason="mauvaise_humeur")
    db.rollback()
    _active_plan(db, user)
    monkeypatch.setattr(get_settings(), "real_ai_enabled", True)
    with pytest.raises(plan.PlanStateError) as real:
        _shock(db, user)
    assert real.value.code == "PLAN_REGEN_NOT_CODED"
    db.rollback()
    assert db.scalar(select(Event.id).where(Event.user_id == user.id,
                                            Event.event_type == "planning.plan.shock_requested")) is None


def test_shock_route(db, monkeypatch) -> None:
    user = _user(db)
    _active_plan(db, user)
    app = FastAPI()
    app.include_router(wr.router, prefix="/api/wr")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    body = {"reason_code": "housing_disaster"}
    assert client.post("/api/wr/plan/shock", json=body).status_code == 400  # sans Idempotency-Key
    monkeypatch.setattr(plan, "plan_enabled", lambda db: True)
    off = client.post("/api/wr/plan/shock", json=body, headers={"Idempotency-Key": uuid4().hex})
    assert (off.status_code, off.json()["code"]) == (409, "PLAN_SHOCK_DISABLED")  # route coupée au seed
    monkeypatch.setattr(plan, "shock_enabled", lambda db: True)
    unknown = client.post("/api/wr/plan/shock", json={"reason_code": "x"}, headers={"Idempotency-Key": uuid4().hex})
    assert (unknown.status_code, unknown.json()["code"]) == (422, "SHOCK_REASON_UNKNOWN")
    key = uuid4().hex
    created = client.post("/api/wr/plan/shock", json=body, headers={"Idempotency-Key": key})
    replay = client.post("/api/wr/plan/shock", json=body, headers={"Idempotency-Key": key})
    assert (created.status_code, created.json()["status"], replay.json()["id"]) == (201, "proposed", created.json()["id"])
    again = client.post("/api/wr/plan/shock", json=body, headers={"Idempotency-Key": uuid4().hex})
    assert (again.status_code, again.json()["code"]) == (409, "PLAN_REGEN_PENDING")
