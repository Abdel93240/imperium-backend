"""PostgreSQL : score /200 et escalade invisible de Nexus (doc 72 §3, doc 30 §5). CLI cloud et modèle local simulés."""
from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("escalation DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_chat  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.chat import ChatMessage  # noqa: E402
from app.services.ai import cloud, escalation, local_executor  # noqa: E402
from app.services.ai.advanced import update_thresholds  # noqa: E402
from app.schemas.ai_advanced import ThresholdBand, ThresholdsUpdate  # noqa: E402
from app.services.params import set_parameter  # noqa: E402

P = "/api/imperium/chat/sessions"
LOW = {"complexity": 2, "context_size": 2, "ambiguity": 1, "consequences": 2, "speed_tolerance": 3, "sensitivity": 2,
       "cost_justification": 1, "confidence": 0.9, "domain": "general", "expert_question": None}


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


class Fakes:
    def __init__(self) -> None:
        self.local: list = []
        self.cloud: list = []
        self.calls: list = []  # (rôle, question)

    def post(self, url, payload, timeout):
        item = self.local.pop(0)
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(item)}}], "usage": {}}

    def run(self, args, stdin, timeout, cwd):
        item = self.cloud.pop(0)
        if isinstance(item, Exception):
            raise item
        return json.dumps({"type": "result", "subtype": "success", "is_error": False, "structured_output": item,
                           "usage": {"input_tokens": 10, "output_tokens": 10}, "modelUsage": {args[3]: {}}})


@pytest.fixture()
def fakes(monkeypatch) -> Fakes:
    fake = Fakes()
    monkeypatch.setattr(local_executor, "_http_post", fake.post)
    monkeypatch.setattr(local_executor, "get_settings", lambda: SimpleNamespace(
        local_executor_url="http://127.0.0.1:8081", local_executor_timeout_seconds=5))
    monkeypatch.setattr(local_executor.call_log, "record", lambda **row: None)
    monkeypatch.setattr(cloud, "_run", fake.run)
    monkeypatch.setattr(cloud, "_binary", lambda name: "claude")
    monkeypatch.setattr(cloud.call_log, "record", lambda **row: None)

    def role(db, code):
        fake.calls.append(code)
        return SimpleNamespace(provider="anthropic", model_id=f"model-{code}", effort=None)

    monkeypatch.setattr(cloud, "resolve_role", role)
    return fake


def _a(**values) -> dict:
    return {**LOW, **values}


def test_score_bands_and_automatic_rules(db) -> None:
    assert escalation.score(LOW) == 10 + 6 + 3 + 4 + 6 + 6 + 2 == 37
    assert escalation.score({name: 10 for name in escalation.CRITERIA}) == 200
    assert escalation.decide(db, None).role == "local_executor"
    assert escalation.decide(db, LOW).role == "local_executor"
    first = escalation.decide(db, _a(complexity=9, context_size=6, cost_justification=6))  # 45+18+3+4+6+6+12 = 94
    assert (first.score, first.role) == (94, "local_executor")
    mid = _a(complexity=10, context_size=8, ambiguity=3, consequences=5, speed_tolerance=8, sensitivity=3,
             cost_justification=8)
    assert (escalation.decide(db, mid).score, escalation.decide(db, mid).role) == (134, "first_cloud_tier")
    assert escalation.decide(db, _a(**{k: v for k, v in mid.items() if k in escalation.CRITERIA},
                                    domain="health")).role == "health_specialist"
    deep = _a(complexity=10, context_size=10, ambiguity=6, consequences=8, speed_tolerance=8, sensitivity=4,
              cost_justification=8)  # 50+30+18+16+16+12+16 = 158
    assert escalation.decide(db, deep).role == "high_reasoning"
    critical = escalation.decide(db, {**{name: 10 for name in escalation.CRITERIA}, "confidence": 1, "domain": "general"})
    assert critical.role == "high_reasoning" and "critical_recheck_not_wired" in critical.reasons
    unsure = escalation.decide(db, _a(confidence=0.4))  # confiance basse : un cran au-dessus
    assert unsure.role == "first_cloud_tier" and "low_confidence" in unsure.reasons
    vague = escalation.decide(db, _a(consequences=8, ambiguity=7))
    assert vague.role == "first_cloud_tier" and "consequences_and_ambiguity" in vague.reasons
    grave = escalation.decide(db, _a(consequences=9, sensitivity=8, domain="finance"))
    assert grave.role == "finance_specialist" and "grave_and_sensitive" in grave.reasons
    update_thresholds(db, payload=ThresholdsUpdate(bands=[
        ThresholdBand(label="IA locale", start=0, end=30), ThresholdBand(label="Premier niveau cloud", start=31, end=139),
        ThresholdBand(label="Raisonnement poussé", start=140, end=179), ThresholdBand(label="Mécanique critique", start=180, end=200)]))
    assert escalation.decide(db, LOW).role == "first_cloud_tier"  # seuils réglables (doc 73)


def test_scrub_removes_identifiers() -> None:
    cleaned = escalation.scrub("Écris à jean.dupont@mail.fr ou au 06 12 34 56 78, IBAN FR76 3000 1007 9412 3456 7890 185, voir https://x.y/z")
    assert "@" not in cleaned and "06 12" not in cleaned and "FR76 3000" not in cleaned and "https" not in cleaned


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"esc-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_chat.router, prefix="/api/imperium")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


HEALTH = _a(complexity=10, context_size=8, ambiguity=3, consequences=5, speed_tolerance=8, sensitivity=3,
            cost_justification=8, domain="health",
            expert_question="Un homme de 35 ans fait 3 séances de musculation par semaine depuis un an et ne progresse "
                            "plus ; il dort 6 h. Que lui conseiller ?")


def _turn(assessment: dict, reply: str = "Je regarde.") -> dict:
    return {"comprehension": "Il stagne.", "assessment": assessment, "reply_fr": reply, "proposal": None, "switch": None}


def test_chat_escalates_invisibly_only_when_the_slot_is_live(db, fakes) -> None:
    set_parameter(db, code="chat.enabled", value=True, origin="user", rationale_fr="Test.")
    set_parameter(db, code="ai.local_slot_modes", value={"chat.converse": "live"}, origin="user", rationale_fr="Test.")
    db.commit()
    user = _user(db)
    client = _client(db, user)
    sid = client.post(P, json={}).json()["id"]

    fakes.local = [_turn(LOW, "Salut !")]
    turn = client.post(f"{P}/{sid}/messages", json={"text": "Salut"}).json()
    assert turn["assistant_message"]["content"] == "Salut !" and "routing" not in turn["assistant_message"]  # invisible
    row = db.scalar(select(ChatMessage).where(ChatMessage.session_id == sid, ChatMessage.role == "assistant"))
    assert (row.routing["role"], row.routing["escalated"], row.model_used) == ("local_executor", False, "local_executor")

    fakes.local = [_turn(HEALTH, "Je ne suis pas sûr.")]  # slot éteint : mode ombre, la réponse locale reste
    turn = client.post(f"{P}/{sid}/messages", json={"text": "Mon entraînement ne donne plus rien"}).json()
    assert turn["assistant_message"]["content"] == "Je ne suis pas sûr." and fakes.calls == []
    last = db.scalars(select(ChatMessage).where(ChatMessage.session_id == sid).order_by(ChatMessage.created_at.desc())).first()
    assert (last.routing["score"], last.routing["role"], last.routing["skipped"]) == (134, "health_specialist", "slot_off")

    set_parameter(db, code="ai.cloud_transport", value="subscription", origin="user", rationale_fr="Test.")
    set_parameter(db, code="ai.cloud_slot_modes", value={"nexus.escalation": "live"}, origin="user", rationale_fr="Test.")
    db.commit()
    fakes.local = [_turn(HEALTH, "Je ne suis pas sûr.")]
    fakes.cloud = [{"answer_fr": "Change de programme toutes les 6 semaines et dors 7 h au moins."}]
    turn = client.post(f"{P}/{sid}/messages", json={"text": "Et du coup ?"}).json()
    assert turn["assistant_message"]["content"] == "Change de programme toutes les 6 semaines et dors 7 h au moins."
    assert fakes.calls == ["health_specialist"]
    last = db.scalars(select(ChatMessage).where(ChatMessage.session_id == sid).order_by(ChatMessage.created_at.desc())).first()
    assert last.routing["escalated"] is True and last.model_used == "model-health_specialist"

    fakes.local = [_turn(HEALTH, "Réponse locale.")]
    fakes.cloud = [cloud.CloudQuotaError("Subscription quota reached", "17:00")]  # quota : la réponse locale reste
    turn = client.post(f"{P}/{sid}/messages", json={"text": "Encore ?"}).json()
    assert turn["assistant_message"]["content"] == "Réponse locale."
    last = db.scalars(select(ChatMessage).where(ChatMessage.session_id == sid).order_by(ChatMessage.created_at.desc())).first()
    assert last.routing["skipped"] == "cloud_error"


def test_routed_role_is_refused_on_fixed_slots(db, fakes) -> None:
    with pytest.raises(cloud.CloudError):
        set_parameter(db, code="ai.cloud_transport", value="subscription", origin="user", rationale_fr="Test.")
        set_parameter(db, code="ai.cloud_slot_modes", value={"wr.exit_audit": "live", "nexus.escalation": "live"},
                      origin="user", rationale_fr="Test.")
        db.commit()
        cloud.structured(db, slot_code="wr.exit_audit", app_name="imperium", system="s", user="u", schema={},
                         role_code="high_reasoning")
    with pytest.raises(cloud.CloudError, match="local only"):
        cloud.structured(db, slot_code="nexus.escalation", app_name="imperium", system="s", user="u", schema={},
                         role_code="local_executor")


def test_sensitive_domain_with_an_expert_question_escalates_even_with_a_low_score(db) -> None:
    low_health = _a(domain="health", expert_question="Que conseiller à un adulte qui stagne en musculation ?")
    decision = escalation.decide(db, low_health)
    assert decision.score == 37 and decision.role == "health_specialist" and "sensitive_domain" in decision.reasons
    assert escalation.decide(db, _a(domain="health")).role == "local_executor"  # sans question : il répond seul


def test_a_proposal_does_not_block_the_escalated_answer(db, fakes) -> None:
    set_parameter(db, code="chat.enabled", value=True, origin="user", rationale_fr="Test.")
    set_parameter(db, code="ai.local_slot_modes", value={"chat.converse": "live"}, origin="user", rationale_fr="Test.")
    set_parameter(db, code="ai.cloud_transport", value="subscription", origin="user", rationale_fr="Test.")
    set_parameter(db, code="ai.cloud_slot_modes", value={"nexus.escalation": "live"}, origin="user", rationale_fr="Test.")
    db.commit()
    client = _client(db, _user(db))
    sid = client.post(P, json={}).json()["id"]
    deep = _a(complexity=9, context_size=8, ambiguity=8, consequences=6, speed_tolerance=9, sensitivity=5,
              cost_justification=7, confidence=0.6,
              expert_question="Comment un adulte qui hésite entre plusieurs voies peut-il choisir une direction de vie ?")
    fakes.local = [{**_turn(deep, "Veux-tu créer un projet pour y réfléchir ?"), "proposal": {
        "action": "create_project", "summary_fr": "Créer le projet « Ma direction »",
        "params": {"title": "Ma direction", "description": "Clarifier la direction que je veux donner à ma vie",
                   "missions": [{"title": "Lister mes valeurs", "estimated_minutes": 30}]}}}]
    fakes.cloud = [{"answer_fr": "Commence par ce qui te donne de l'énergie, puis teste une piste pendant un mois."}]
    turn = client.post(f"{P}/{sid}/messages", json={"text": "Je ne sais pas quelle direction prendre dans ma vie"}).json()
    assert turn["assistant_message"]["content"].startswith("Commence par ce qui te donne de l'énergie")
    assert turn["proposal"]["action"] == "create_project" and fakes.calls == ["high_reasoning"]


def test_vital_emergency_goes_critical_and_always_starts_with_the_fixed_line(db, fakes, monkeypatch) -> None:
    # Le cas réel du 2026-10-21 : urgent et simple, le score sortait à 83 et partait au seul spécialiste santé.
    real = {"complexity": 2, "context_size": 1, "ambiguity": 0, "consequences": 10, "speed_tolerance": 0,
            "sensitivity": 10, "cost_justification": 10, "confidence": 0.1, "domain": "health",
            "expert_question": "J'ai des palpitations et je ne sens plus mon bras gauche, que dois-je faire ?"}
    assert escalation.decide(db, real).score == 83
    decision = escalation.decide(db, {**real, "vital_emergency": True})
    assert (decision.score, decision.role, decision.emergency) == (180, "high_reasoning", True)
    assert "vital_emergency" in decision.reasons

    set_parameter(db, code="chat.enabled", value=True, origin="user", rationale_fr="Test.")
    set_parameter(db, code="ai.local_slot_modes", value={"chat.converse": "live"}, origin="user", rationale_fr="Test.")
    db.commit()
    client = _client(db, _user(db))
    sid = client.post(P, json={}).json()["id"]
    fakes.local = [_turn({**real, "vital_emergency": True}, "Je regarde.")]  # cloud éteint : la ligne reste
    turn = client.post(f"{P}/{sid}/messages", json={"text": "J'ai des palpitations et je ne sens plus mon bras"}).json()
    assert turn["assistant_message"]["content"].startswith(escalation.EMERGENCY_LINE)

    set_parameter(db, code="ai.cloud_transport", value="subscription", origin="user", rationale_fr="Test.")
    set_parameter(db, code="ai.cloud_slot_modes", value={"nexus.escalation": "live"}, origin="user", rationale_fr="Test.")
    db.commit()
    systems = []
    original = cloud.structured
    monkeypatch.setattr(cloud, "structured", lambda db, **kw: systems.append(kw["system"]) or original(db, **kw))
    fakes.local = [_turn({**real, "vital_emergency": True}, "Je regarde.")]
    fakes.cloud = [{"answer_fr": "Assieds-toi tout de suite et dis au SAMU : palpitations et bras gauche engourdi."}]
    turn = client.post(f"{P}/{sid}/messages", json={"text": "Ça continue"}).json()
    content = turn["assistant_message"]["content"]
    assert content.startswith(escalation.EMERGENCY_LINE) and content.endswith("bras gauche engourdi.")
    assert fakes.calls[-1] == "high_reasoning" and "réponds-LUI directement" in systems[-1] and "URGENCE VITALE" in systems[-1]
    last = db.scalars(select(ChatMessage).where(ChatMessage.session_id == sid).order_by(ChatMessage.created_at.desc())).first()
    assert last.routing["vital_emergency"] is True and last.routing["expert_question"].startswith("J'ai des palpitations")
