"""PostgreSQL : bloc 1 Pulse — recette par Nexus et par Nourrir l'IA, estimation d'un repas « Autre »,
« Adapter à mon état » sur une séance."""
from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("pulse block 1 DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_pulse_meals, imperium_pulse_signals, knowledge_inbox as inbox_routes  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.imperium import PulseWorkout  # noqa: E402
from app.models.pulse import PulseRecipe  # noqa: E402
from app.schemas.knowledge_inbox import InboxItemCreate  # noqa: E402
from app.services.ai import knowledge_inbox as inbox  # noqa: E402
from app.services.ai import knowledge_inbox_runner as runner  # noqa: E402
from app.services.ai import local_executor  # noqa: E402
from app.services.chat import engine  # noqa: E402
from app.services.params import set_parameter  # noqa: E402
from app.services.pulse import meal_estimate  # noqa: E402

P = "/api/imperium/pulse"
INBOX = "/api/ai/knowledge-inbox"
RECIPE_TEXT = b"""Recette du dahl de lentilles (4 personnes)
Ingredients : 300 g de lentilles corail, 1 oignon, 40 cl de lait de coco
Preparation : faire revenir l'oignon, ajouter les lentilles, laisser mijoter 20 minutes, melanger."""


@pytest.fixture(scope="module")
def engine_db():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine_db):
    with Session(engine_db) as session:
        yield session
        session.rollback()


@pytest.fixture(autouse=True)
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(inbox, "storage_root", lambda: tmp_path)


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"b1-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    for module, prefix in ((imperium_pulse_meals, P), (imperium_pulse_signals, P), (inbox_routes, INBOX)):
        app.include_router(module.router, prefix=prefix)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _local(monkeypatch, outputs: dict, prompts: list | None = None):
    """Modèle local simulé : slot → sortie ; les prompts reçus sont gardés."""
    monkeypatch.setattr(local_executor, "slot_mode", lambda db, slot: "live" if slot in outputs else "off")

    def structured(*, slot_code, user, **kwargs):
        if prompts is not None:
            prompts.append(user)
        return SimpleNamespace(output=outputs[slot_code], prompt_tokens=None, output_tokens=None, latency_ms=1)
    monkeypatch.setattr(local_executor, "structured", structured)


def test_nexus_adds_a_recipe_to_the_catalogue(db):
    user = _user(db)
    params = {"title": "Dahl de lentilles", "servings": 4, "steps": ["Cuire 20 min."], "packaging": ["Bocaux stérilisés."],
              "shelf_life_days": 5, "ingredients": [{"name": "Lentilles corail", "quantity": 300, "unit": "g"}]}
    proposal = {"action": "add_recipe", "summary_fr": "Ajouter le dahl.", "params": params}
    assert engine._check(proposal, set(), engine.requirements(db)) == ([], [])
    errors, missing = engine._check({**proposal, "params": {**params, "ingredients": []}}, set(), engine.requirements(db))
    assert missing == ["les ingrédients avec leurs quantités"]
    result = engine._execute(db, user, "add_recipe", params, f"chat-{uuid4()}")
    recipe = db.get(PulseRecipe, result["recipe_id"])
    assert (recipe.title, recipe.source, recipe.servings, recipe.calories) == ("Dahl de lentilles", "chatbot", 4, None)
    assert "add_recipe" in engine.agent_sheet(db, "general")["actions"]


def test_other_meal_is_estimated_and_marked(db, monkeypatch):
    user = _user(db)
    client = _client(db, user)
    body = {"description": "Un kebab frites au resto", "estimate": True}
    plain = client.post(f"{P}/meals/drafts", headers={"Idempotency-Key": uuid4().hex}, json=body).json()
    assert plain["calories"] is None and not plain["macros_estimated"]  # slot éteint : rien d'inventé
    _local(monkeypatch, {"pulse.meal_estimate": {"calories": 950, "protein_g": 38, "carbs_g": 90, "fat_g": 48,
                                                 "confidence": "medium", "assumptions_fr": "portion de frites moyenne"}})
    draft = client.post(f"{P}/meals/drafts", headers={"Idempotency-Key": uuid4().hex}, json=body).json()
    assert (draft["calories"], draft["macros_estimated"], draft["confidence"]) == ("950.0", True, 0.6)
    assert draft["warnings"][0].startswith("Apports estimés") and "frites moyenne" in draft["warnings"][0]
    confirmed = client.post(f"{P}/meals/{draft['id']}/confirm", headers={"Idempotency-Key": uuid4().hex},
                            json={"stock_lines": [], "calories": 900}).json()
    assert confirmed["calories"] == "900.0"  # corrigé par l'utilisateur
    assert meal_estimate.parse({"calories": 99999, "protein_g": 1, "carbs_g": 1, "fat_g": 1, "confidence": "high",
                                "assumptions_fr": ""}) is None


def test_recipe_deposited_in_the_inbox_lands_in_the_catalogue(db, monkeypatch):
    user = _user(db)
    client = _client(db, user)
    recipe = {"title": "Dahl de lentilles", "servings": 4, "steps": ["Faire revenir l'oignon.", "Mijoter 20 min."],
              "packaging": [], "shelf_life_days": None,
              "ingredients": [{"name": "Lentilles corail", "quantity": 300, "unit": "g"},
                              {"name": "Oignon", "quantity": 1, "unit": "piece"}]}
    _local(monkeypatch, {"pulse.recipe_extract": recipe})
    item = inbox.create_item(db, current_user=user, payload=InboxItemCreate(context_text=None, entry_app="pulse"),
                             idempotency_key=f"i-{uuid4().hex}")
    inbox.add_source(db, current_user=user, item_id=item.id, filename="dahl.txt", content_type="text/plain",
                     stream=io.BytesIO(RECIPE_TEXT))
    inbox.request_analysis(db, current_user=user, item_id=item.id)
    runner.process_inbox(SimpleNamespace(db=db, items_in=None, items_out=None, detail={}), call_model=None,
                         embed_texts=None, recognize_file=None)
    db.commit()
    draft = client.get(f"{INBOX}/items/{item.id}").json()["extraction_draft"]
    assert draft["proposed_destination"] == "recipe" and draft["recipe"]["title"] == "Dahl de lentilles"
    broken = client.patch(f"{INBOX}/items/{item.id}/extraction", json={"recipe": {**draft["recipe"], "steps": []}})
    assert broken.status_code == 200
    assert client.post(f"{INBOX}/items/{item.id}/validate", json={"destination": "recipe"}).status_code == 409
    client.patch(f"{INBOX}/items/{item.id}/extraction", json={"recipe": {**draft["recipe"], "servings": 6}})
    assert client.post(f"{INBOX}/items/{item.id}/validate", json={"destination": "recipe"}).status_code == 200
    saved = db.scalar(select(PulseRecipe).where(PulseRecipe.user_id == user.id))
    assert (saved.title, saved.servings, saved.source) == ("Dahl de lentilles", 6, "inbox")


def test_adapt_to_my_state_proposes_a_legal_move(db, monkeypatch):
    user = _user(db)
    client = _client(db, user)
    workout = PulseWorkout(user_id=user.id, title="Dos", status="planned", planned_at=datetime.now(UTC) + timedelta(days=2),
                           duration_minutes=40, intensity="medium", idempotency_key=uuid4().hex, request_hash="h")
    db.add(workout)
    db.commit()
    off = client.post(f"{P}/workouts/{workout.id}/adapt", json={"reason": "fatigue"})
    assert off.status_code == 409 and off.json()["code"] == "PULSE_ADAPT_UNAVAILABLE"
    set_parameter(db, code="pulse.proposals_enabled", value=True, origin="user", rationale_fr="Test.")
    db.execute(text("UPDATE pulse_procedures SET active = true WHERE code = 'adapt_training_session'"))
    db.commit()
    try:
        assert "pas branché" in client.post(f"{P}/workouts/{workout.id}/adapt", json={"reason": "fatigue"}).json()["detail"]
        prompts = []
        _local(monkeypatch, {"pulse.p1.choose_move": {"move_code": "maintain", "parameters": {}, "fallback_move_code": None,
                                                      "condition_fr": None, "rationale_fr": "Séance légère, à garder.",
                                                      "confidence": "medium"}}, prompts)
        adapted = client.post(f"{P}/workouts/{workout.id}/adapt", json={"reason": "fatigue"}).json()
        assert adapted["outcome"] == "proposed" and adapted["proposal"]["payload"]["move_code"] == "maintain"
        assert "demande : fatigue déclarée" in prompts[0]
        assert [p["id"] for p in client.get(f"{P}/proposals").json()["items"]] == [adapted["proposal"]["id"]]
        decided = client.post(f"{P}/proposals/{adapted['proposal']['id']}/decision", json={"decision": "accepted"})
        assert decided.status_code == 200 and decided.json()["decision"] == "accepted"
    finally:
        set_parameter(db, code="pulse.proposals_enabled", value=False, origin="user", rationale_fr="Test.")
        db.execute(text("UPDATE pulse_procedures SET active = false WHERE code = 'adapt_training_session'"))
        db.commit()
