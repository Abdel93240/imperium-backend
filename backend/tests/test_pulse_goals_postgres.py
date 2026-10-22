"""PostgreSQL : objectifs Pulse — écrits et classés par l'utilisateur, lus par le programme et la diète."""
from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("pulse goals DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_pulse_goals, imperium_pulse_training  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.pulse import PulseDietPlan  # noqa: E402
from app.services.params import set_parameter  # noqa: E402
from app.services.pulse import diet_planner, goals, program_design  # noqa: E402

P = "/api/imperium/pulse"


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
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"goals-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_pulse_goals.router, prefix=P)
    app.include_router(imperium_pulse_training.router, prefix=P)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _add(client, title, notes=None) -> dict:
    response = client.post(f"{P}/goals", headers={"Idempotency-Key": uuid4().hex}, json={"title": title, "notes": notes})
    assert response.status_code == 201, response.text
    return response.json()


def test_goals_are_ranked_by_the_user(db):
    user = _user(db)
    client = _client(db, user)
    abs_ = _add(client, "Abdos visibles")
    pulls = _add(client, "25 tractions d'affilée", "sans élan")
    back = _add(client, "Dos droit")
    assert [g["rank"] for g in client.get(f"{P}/goals").json()["items"]] == [1, 2, 3]
    key = {"Idempotency-Key": "same"}
    assert client.post(f"{P}/goals", headers=key, json={"title": "Souplesse"}).status_code == 201
    assert client.post(f"{P}/goals", headers=key, json={"title": "Souplesse"}).status_code == 200  # rejouer
    flex = client.get(f"{P}/goals").json()["items"][3]

    # Nouvel ordre : tout le classement, une fois chacun.
    assert client.put(f"{P}/goals/order", json={"ids": [back["id"], abs_["id"]]}).status_code == 409
    ordered = client.put(f"{P}/goals/order", json={"ids": [pulls["id"], abs_["id"], back["id"], flex["id"]]}).json()
    assert [g["title"] for g in ordered["items"]] == ["25 tractions d'affilée", "Abdos visibles", "Dos droit", "Souplesse"]
    assert goals.ranked_lines(db, user)[0] == "1. 25 tractions d'affilée (sans élan)"

    # Atteint : sort du classement, les rangs se resserrent ; remis en cours : à la fin.
    client.patch(f"{P}/goals/{abs_['id']}", json={"status": "achieved"})
    listed = client.get(f"{P}/goals").json()
    assert [(g["title"], g["rank"]) for g in listed["items"]] == [("25 tractions d'affilée", 1), ("Dos droit", 2), ("Souplesse", 3)]
    assert [g["title"] for g in listed["achieved"]] == ["Abdos visibles"]
    reopened = client.patch(f"{P}/goals/{abs_['id']}", json={"status": "active", "title": "Abdos bien visibles"}).json()
    assert (reopened["rank"], reopened["title"]) == (4, "Abdos bien visibles")

    # Retiré : disparaît, rangs resserrés.
    assert client.delete(f"{P}/goals/{back['id']}").status_code == 204
    assert [g["rank"] for g in client.get(f"{P}/goals").json()["items"]] == [1, 2, 3]
    assert client.patch(f"{P}/goals/{back['id']}", json={"title": "x"}).status_code == 404
    assert client.post(f"{P}/goals", headers={"Idempotency-Key": "blank"}, json={"title": "  "}).status_code == 422


def test_program_and_diet_are_built_on_the_ranked_goals(db):
    user = _user(db)
    client = _client(db, user)
    set_parameter(db, code="pulse.programs_enabled", value=True, origin="user", rationale_fr="Test.")
    db.commit()
    try:
        body = {"level": "beginner", "days": ["MO"], "session_minutes": 30, "preferred_time": "18:00"}
        refused = client.post(f"{P}/programs/requests", headers={"Idempotency-Key": uuid4().hex}, json=body)
        assert refused.status_code == 409 and "objectif" in refused.json()["detail"]
        _add(client, "Abdos visibles")
        _add(client, "25 tractions d'affilée")
        requested = client.post(f"{P}/programs/requests", headers={"Idempotency-Key": uuid4().hex}, json=body)
        assert requested.status_code == 202 and requested.json()["inputs"]["goals"] == ["1. Abdos visibles",
                                                                                      "2. 25 tractions d'affilée"]
        prompts = []
        program_design.generate(db, UUID(requested.json()["id"]),
                                call=lambda s, p, sc: (prompts.append(p), (None, "cloud", {}))[1])
        assert "1. Abdos visibles\n2. 25 tractions d'affilée" in prompts[0]
    finally:
        set_parameter(db, code="pulse.programs_enabled", value=False, origin="user", rationale_fr="Test.")
        db.commit()
    plan = PulseDietPlan(user_id=user.id, week_start=date(2026, 10, 26), status="generating", idempotency_key="k",
                         request_hash="h")
    prompt = diet_planner.build_prompt(db, user, plan, [date(2026, 10, 26)], {}, {})
    assert prompt.startswith("## Objectifs de l'utilisateur") and "1. Abdos visibles" in prompt
