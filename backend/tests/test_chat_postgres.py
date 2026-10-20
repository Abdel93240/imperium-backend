"""PostgreSQL : chatbot V1 sur l'exécuteur local (doc 72) — propositions jamais exécutées sans validation,
mode dégradé explicite, contexte en liste blanche. Exécuteur simulé."""
from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("chat DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_chat  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.imperium import ImperiumMission, ImperiumProject  # noqa: E402
from app.schemas.operations import ProjectCreate  # noqa: E402
from app.services.ai import local_executor  # noqa: E402
from app.services.imperium import operations  # noqa: E402
from app.services.params import set_parameter  # noqa: E402

P = "/api/imperium/chat/sessions"
LOOPBACK = "http://127.0.0.1:8081"


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


class Fake:
    def __init__(self) -> None:
        self.outputs: list = []
        self.prompts: list[str] = []
        self.systems: list[str] = []

    def post(self, url, payload, timeout):
        self.systems.append(payload["messages"][0]["content"])
        self.prompts.append(payload["messages"][1]["content"])
        item = self.outputs.pop(0)
        if isinstance(item, Exception):
            raise item
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(item)}}], "usage": {}}


@pytest.fixture()
def fake(monkeypatch) -> Fake:
    executor = Fake()
    monkeypatch.setattr(local_executor, "_http_post", executor.post)
    monkeypatch.setattr(local_executor, "get_settings",
                        lambda: SimpleNamespace(local_executor_url=LOOPBACK, local_executor_timeout_seconds=5))
    monkeypatch.setattr(local_executor.call_log, "record", lambda **row: None)
    return executor


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"chat-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_chat.router, prefix="/api/imperium")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _enable(db, live: bool = True) -> None:
    set_parameter(db, code="chat.enabled", value=True, origin="user", rationale_fr="Test.")
    if live:
        set_parameter(db, code="ai.local_slot_modes", value={"chat.converse": "live"}, origin="user", rationale_fr="Test.")
    db.commit()


def _session(client) -> str:
    response = client.post(P, json={})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _say(client, sid: str, message: str) -> dict:
    response = client.post(f"{P}/{sid}/messages", json={"text": message})
    assert response.status_code == 200, response.text
    return response.json()


MISSIONS = [{"title": "Choisir l'hébergeur", "estimated_minutes": 30}, {"title": "Écrire la page d'accueil", "estimated_minutes": None}]


def _project(title="Lancer le site", description="Un site vitrine en ligne pour l'activité", missions=MISSIONS) -> dict:
    return {"reply_fr": "Je te propose de créer ce projet.", "proposal": {
        "action": "create_project", "summary_fr": f"Créer le projet « {title} »",
        "params": {"title": title, "description": description, "missions": missions}}}


def test_disabled_and_degraded_without_live_slot(db, fake) -> None:
    user = _user(db)
    client = _client(db, user)
    assert client.post(P, json={}).json()["code"] == "CHAT_DISABLED"
    _enable(db, live=False)
    sid = _session(client)
    turn = _say(client, sid, "Bonjour")
    assert turn["assistant_message"]["degraded"] is True and "indisponible" in turn["assistant_message"]["content"]
    assert turn["proposal"] is None and fake.prompts == []  # aucun appel au modèle


def test_proposal_is_never_executed_until_validated(db, fake) -> None:
    _enable(db)
    user = _user(db)
    client = _client(db, user)
    sid = _session(client)
    fake.outputs.append(_project("Lancer le site"))
    turn = _say(client, sid, "Crée un projet pour lancer mon site")
    proposal = turn["proposal"]
    assert proposal["status"] == "proposed" and proposal["action"] == "create_project"
    assert db.scalar(select(ImperiumProject).where(ImperiumProject.user_id == user.id)) is None  # rien d'écrit
    validated = client.post(f"{P}/{sid}/proposals/{proposal['id']}/validate").json()
    assert validated["status"] == "validated" and validated["result"]["title"] == "Lancer le site"
    project = db.scalar(select(ImperiumProject).where(ImperiumProject.user_id == user.id))
    assert (project.title, project.source, project.description) == ("Lancer le site", "chatbot", "Un site vitrine en ligne pour l'activité")
    # Projet complet en une seule validation : ses premières missions sont créées avec lui.
    missions = db.scalars(select(ImperiumMission).where(ImperiumMission.project_id == project.id)).all()
    assert sorted((m.title, m.estimated_minutes) for m in missions) == [("Choisir l'hébergeur", 30), ("Écrire la page d'accueil", None)]
    assert validated["result"]["missions"] == 2
    assert client.post(f"{P}/{sid}/proposals/{proposal['id']}/validate").status_code == 409
    session = client.get(f"{P}/{sid}").json()
    assert [m["role"] for m in session["messages"]] == ["user", "assistant"] and session["open_proposal"] is None

    # Le contexte transmis au modèle connaît le projet (liste blanche), et rien d'autre.
    fake.outputs.append({"reply_fr": "Voici.", "proposal": {"action": "add_project_mission", "summary_fr": "Ajouter « Maquette »",
                                                           "params": {"project_id": "P1", "title": "Maquette",
                                                                      "estimated_minutes": 90}}})
    turn = _say(client, sid, "Ajoute une mission maquette de 1 h 30")
    assert "P1 : projet actif « Lancer le site »" in fake.prompts[-1] and "Priorités :" in fake.prompts[-1]
    assert str(project.id) not in fake.prompts[-1]  # le modèle ne voit que des repères courts
    assert "Crée un projet pour lancer mon site" in fake.prompts[-1]  # historique de la session
    done = client.post(f"{P}/{sid}/proposals/{turn['proposal']['id']}/validate").json()
    assert turn["proposal"]["params"]["project_id"] == str(project.id)  # repère traduit avant d'être enregistré
    assert done["status"] == "validated" and done["result"]["title"] == "Maquette"


def test_invalid_proposals_retry_supersede_reject_and_close(db, fake) -> None:
    _enable(db)
    user = _user(db)
    client = _client(db, user)
    sid = _session(client)
    bad = {"reply_fr": "Ok.", "proposal": {"action": "add_project_mission", "summary_fr": "Ajouter",
                                           "params": {"project_id": "P9", "title": "X"}}}
    fake.outputs += [bad, _project("Bon projet")]
    turn = _say(client, sid, "Ajoute X")
    assert turn["proposal"]["params"] == _project("Bon projet")["proposal"]["params"] and "rappel" in fake.prompts[1]
    fake.outputs += [bad, bad]
    turn = _say(client, sid, "Ajoute encore X")
    assert turn["proposal"] is None and turn["assistant_message"]["content"].endswith("besoin de savoir : le projet concerné.")
    assert client.get(f"{P}/{sid}").json()["open_proposal"]["params"] == _project("Bon projet")["proposal"]["params"]

    fake.outputs.append(_project("Autre projet"))
    first = client.get(f"{P}/{sid}").json()["open_proposal"]["id"]
    second = _say(client, sid, "Plutôt un autre projet")["proposal"]
    assert client.post(f"{P}/{sid}/proposals/{first}/validate").status_code == 409  # remplacée
    assert client.post(f"{P}/{sid}/proposals/{second['id']}/reject").json()["status"] == "rejected"

    fake.outputs.append(_project("Dernier"))
    last = _say(client, sid, "Un dernier")["proposal"]
    closed = client.post(f"{P}/{sid}/close").json()
    assert closed["status"] == "closed" and closed["open_proposal"] is None
    assert client.post(f"{P}/{sid}/proposals/{last['id']}/validate").status_code == 409
    assert client.post(f"{P}/{sid}/messages", json={"text": "Encore ?"}).status_code == 409
    assert db.scalar(select(ImperiumProject).where(ImperiumProject.user_id == user.id)) is None


def test_executor_down_failed_action_isolation_and_deletion(db, fake) -> None:
    _enable(db)
    user = _user(db)
    client = _client(db, user)
    sid = _session(client)
    fake.outputs.append(local_executor.LocalExecutorError("down"))
    turn = _say(client, sid, "Bonjour")
    assert turn["assistant_message"]["degraded"] is True and turn["proposal"] is None
    # Le projet est supprimé entre la proposition et la validation : l'action échoue proprement.
    project = operations.create_project(db, current_user=user, idempotency_key=str(uuid4()), payload=ProjectCreate(title="Éphémère"))
    fake.outputs.append({"reply_fr": "Ok.", "proposal": {"action": "add_project_mission", "summary_fr": "Ajouter",
                                                         "params": {"project_id": "P1", "title": "Y"}}})
    proposal = _say(client, sid, "Ajoute Y")["proposal"]
    operations.delete_project(db, current_user=user, project_id=project.id)
    failed = client.post(f"{P}/{sid}/proposals/{proposal['id']}/validate").json()
    assert failed["status"] == "failed" and failed["result"]["error"]
    stranger = _client(db, _user(db))
    assert stranger.get(f"{P}/{sid}").status_code == 404
    assert stranger.post(f"{P}/{sid}/proposals/{proposal['id']}/reject").status_code == 404
    assert client.delete(f"{P}/{sid}").status_code == 204
    assert client.get(f"{P}/{sid}").status_code == 404


def test_incomplete_project_asks_questions_instead_of_proposing(db, fake) -> None:
    _enable(db)
    user = _user(db)
    client = _client(db, user)
    sid = _session(client)
    empty = _project("Nouveau projet", description="", missions=[])
    # Le modèle insiste deux fois avec un projet vide : rien n'est proposé, le code pose la question (fiche de l'action).
    fake.outputs += [empty, empty]
    turn = _say(client, sid, "Crée-moi un nouveau projet")
    assert turn["proposal"] is None
    content = turn["assistant_message"]["content"]
    assert "le résultat que tu vises" in content and "premières étapes" in content and "le nom du projet" not in content
    assert "pose la question" in fake.prompts[1]
    assert "il faut le nom du projet ; le résultat que tu vises" in fake.systems[0]  # règles de conduite + fiche

    # Objectif trop court et missions vides → refus, puis le modèle pose sa question lui-même.
    fake.outputs += [_project("Site", description="site", missions=[{"title": " ", "estimated_minutes": None}]),
                     {"reply_fr": "Quel résultat vises-tu, et quelles sont les premières étapes ?", "proposal": None}]
    turn = _say(client, sid, "Un site")
    assert turn["proposal"] is None and turn["assistant_message"]["content"].startswith("Quel résultat")

    # Trop de missions → refusé ; la fiche est une donnée éditable (paramètre).
    fake.outputs += [_project(missions=[{"title": f"M{i}", "estimated_minutes": None} for i in range(11)])] * 2
    turn = _say(client, sid, "Avec onze étapes")
    assert turn["proposal"] is None and "reformule" in turn["assistant_message"]["content"]
    set_parameter(db, code="chat.action_requirements", value={"create_project": {
        "required": [["title", "le nom du projet"]], "min_description_chars": 0, "min_missions": 0, "max_missions": 3}},
        origin="user", rationale_fr="Test.")
    db.commit()
    fake.outputs.append(_project("Simple", description=None, missions=[]))
    proposal = _say(client, sid, "Juste un nom")["proposal"]
    assert proposal["params"]["title"] == "Simple"
    assert client.post(f"{P}/{sid}/proposals/{proposal['id']}/validate").json()["result"]["missions"] == 0
