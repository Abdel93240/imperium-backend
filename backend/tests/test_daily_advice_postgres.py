"""PostgreSQL : conseil du jour du Dashboard — règles immédiates, réécriture locale, signature de l'état."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("daily advice DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_advice  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.imperium import ImperiumMission, ImperiumWeeklyReviewState  # noqa: E402
from app.schemas.imperium import StartPlanningDayRequest  # noqa: E402
from app.services.ai import local_executor  # noqa: E402
from app.services.imperium import advice  # noqa: E402
from app.services.imperium.planning_days import get_current_planning_day, start_planning_day  # noqa: E402
from app.services.imperium.weekly_review_state import reviewable_weeks  # noqa: E402
from app.services.params import set_parameter  # noqa: E402


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture()
def local(monkeypatch):
    outputs, prompts, hooks = [], [], []

    def post(url, payload, timeout):
        prompts.append(payload["messages"][1]["content"])
        while hooks:
            hooks.pop(0)()
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(outputs.pop(0))}}], "usage": {}}

    monkeypatch.setattr(local_executor, "_http_post", post)
    monkeypatch.setattr(local_executor, "get_settings", lambda: SimpleNamespace(
        local_executor_url="http://127.0.0.1:8081", local_executor_timeout_seconds=5))
    monkeypatch.setattr(local_executor.call_log, "record", lambda **row: None)
    return SimpleNamespace(outputs=outputs, prompts=prompts, hooks=hooks)


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"adv-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _start(db, user) -> None:
    start_planning_day(db, current_user=user, payload=StartPlanningDayRequest(felt_energy=3, idempotency_key=str(uuid4())),
                       request_method="POST", request_path="/api/imperium/day/start")


def _mission(db, user, title, **fields) -> ImperiumMission:
    mission = ImperiumMission(user_id=user.id, title=title, status="backlog", started_at=datetime.now(UTC), **fields)
    db.add(mission)
    db.commit()
    return mission


def test_rules_follow_the_state_of_the_day(db) -> None:
    user = _user(db)
    assert advice.current(db, current_user=user) == (None, False)  # pas de journée ouverte
    _start(db, user)
    first, rewrite = advice.current(db, current_user=user)
    assert (first["title"], first["source"], rewrite) == ("Journée libre", "rules", False)  # slot local éteint
    assert advice.current(db, current_user=user)[0]["at"] == first["at"]  # même état : rien n'est recalculé

    _mission(db, user, "Formulaire CAF", deadline_at=datetime.now(UTC) + timedelta(days=2))
    assert advice.current(db, current_user=user)[0]["title"] == "À anticiper"
    _mission(db, user, "Passer à la mairie", deadline_at=datetime.now(UTC) + timedelta(minutes=5))
    due = advice.current(db, current_user=user)[0]
    assert due["title"] == "Échéance aujourd'hui" and "« Passer à la mairie »" in due["body"]
    db.add(ImperiumWeeklyReviewState(user_id=user.id, week_start=reviewable_weeks(db)[0], ready=True,
                                     ready_at=datetime.now(UTC)))
    db.commit()
    assert advice.current(db, current_user=user)[0]["title"] == "Weekly Review en attente"


def test_local_model_rewrites_the_advice_unless_the_state_moved(db, local) -> None:
    set_parameter(db, code="ai.local_slot_modes", value={"imperium.advice": "live"}, origin="user", rationale_fr="Test.")
    db.commit()
    user = _user(db)
    _start(db, user)
    _mission(db, user, "Rapport", deadline_at=datetime.now(UTC) + timedelta(days=1))
    rules, rewrite = advice.current(db, current_user=user)
    assert rewrite and rules["title"] == "À anticiper"
    local.outputs.append({"title_fr": "Prépare le rapport", "body_fr": "Bloque une heure ce matin pour le rapport de demain."})
    written = advice.rewrite(db, current_user=user)
    assert (written["title"], written["source"]) == ("Prépare le rapport", "local")
    assert '"echeances_proches": [{"titre": "Rapport"' in local.prompts[0] and "santé" not in local.prompts[0]
    assert advice.current(db, current_user=user) == (written, False)  # même état : la version locale reste

    _mission(db, user, "Mairie", deadline_at=datetime.now(UTC) + timedelta(hours=1))
    moved, _rewrite = advice.current(db, current_user=user)

    def state_moves() -> None:  # l'état bouge pendant que le modèle écrit
        day = get_current_planning_day(db, current_user=user)
        day.advice = {**moved, "signature": "autre-etat"}
        db.commit()

    local.hooks.append(state_moves)
    local.outputs.append({"title_fr": "Trop tard", "body_fr": "Ce conseil ne doit pas être gardé."})
    assert advice.rewrite(db, current_user=user) is None


def test_route_returns_null_without_an_open_day(db) -> None:
    user = _user(db)
    app = FastAPI()
    app.include_router(imperium_advice.router, prefix="/api/imperium")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    assert client.get("/api/imperium/dashboard/advice").json() is None
    _start(db, user)
    body = client.get("/api/imperium/dashboard/advice").json()
    assert body["title"] == "Journée libre" and body["source"] == "rules"
