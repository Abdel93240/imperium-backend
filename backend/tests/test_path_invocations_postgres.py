"""PostgreSQL : invocations à lire (doc 41 §11-bis) — bibliothèque, favoris, matin et soir."""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("path invocations DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_path_invocations  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.services.path.fasting import paris_today  # noqa: E402

BASE = "/api/imperium/path/invocations"


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
        {"id": str(user_id), "email": f"invoc-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_path_invocations.router, prefix="/api/imperium/path")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def _create(client, **extra) -> dict:
    payload = {"situation": "voyage", "arabic_text": "نص تجريبي", "translation_fr": "Texte de test",
               "source": "Livre de référence, p. 12", **extra}
    response = client.post(BASE, headers=_key(), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_library_by_situation_and_favorites(db) -> None:
    user = _user(db)
    client = _client(db, user)
    key = _key()
    payload = {"situation": "voyage", "arabic_text": " نص ", "translation_fr": " Pour le voyage ", "source": " Réf. A "}
    created = client.post(BASE, headers=key, json=payload)
    assert created.status_code == 201, created.text
    first = created.json()
    assert (first["arabic_text"], first["translation_fr"], first["source"], first["is_favorite"]) == ("نص", "Pour le voyage", "Réf. A", False)
    assert client.post(BASE, headers=key, json=payload).status_code == 200
    assert client.post(BASE, headers=key, json={**payload, "source": "Autre"}).status_code == 409
    _create(client, situation="maladie")
    assert [i["situation"] for i in client.get(BASE).json()["items"]] == ["maladie", "voyage"]
    assert len(client.get(BASE, params={"situation": "voyage"}).json()["items"]) == 1
    fav = client.patch(f"{BASE}/{first['id']}/favorite", json={"is_favorite": True}).json()
    assert (fav["is_favorite"], fav["version"]) == (True, 2)
    assert client.patch(f"{BASE}/{first['id']}/favorite", json={"is_favorite": True}).json()["version"] == 2
    assert [i["id"] for i in client.get(BASE, params={"favorites": "true"}).json()["items"]] == [first["id"]]
    events = list(db.scalars(select(Event).where(Event.user_id == user.id, Event.event_type == "path.invocation.updated")))
    assert sorted(e.payload["action"] for e in events) == ["added", "added", "favorite"]
    assert all("Pour le voyage" not in str(e.payload) for e in events)


def test_inputs_and_versions(db) -> None:
    client = _client(db, _user(db))
    base = {"situation": "voyage", "arabic_text": "نص", "translation_fr": "Texte", "source": "Réf."}
    assert client.post(BASE, headers=_key(), json={**base, "source": "  "}).status_code == 422
    assert client.post(BASE, headers=_key(), json={**base, "situation": "autre"}).status_code == 422
    assert client.post(BASE, headers=_key(), json={**base, "audio_url": "http://x"}).status_code == 422
    assert client.post(BASE, headers=_key(), json={**base, "daily_period": "morning"}).status_code == 422
    assert client.post(BASE, json=base).status_code == 400
    row = _create(client)
    edited = client.patch(f"{BASE}/{row['id']}", json={"version": 1, "translation_fr": "Nouvelle traduction",
                                                         "daily_period": "evening", "daily_order": 2})
    assert (edited.json()["translation_fr"], edited.json()["daily_period"], edited.json()["version"]) == ("Nouvelle traduction", "evening", 2)
    stale = client.patch(f"{BASE}/{row['id']}", json={"version": 1, "source": "x"})
    assert (stale.status_code, stale.json()["code"]) == (409, "INVOCATION_VERSION_CONFLICT")
    assert client.patch(f"{BASE}/{row['id']}", json={"version": 2, "daily_period": None}).status_code == 422
    assert client.patch(f"{BASE}/{row['id']}", json={"version": 2, "source": " "}).status_code == 422
    other = _client(db, _user(db))
    assert other.patch(f"{BASE}/{row['id']}/favorite", json={"is_favorite": True}).status_code == 404


def test_morning_and_evening_checklist(db) -> None:
    client = _client(db, _user(db))
    m1 = _create(client, situation="quotidien", daily_period="morning", daily_order=2)
    m2 = _create(client, situation="quotidien", daily_period="morning", daily_order=1)
    e1 = _create(client, situation="protection", daily_period="evening", daily_order=1)
    library_only = _create(client)
    today = client.get(f"{BASE}/daily").json()
    assert ([i["invocation"]["id"] for i in today["morning"]["items"]], today["morning"]["done"], today["morning"]["total"]) == (
        [m2["id"], m1["id"]], 0, 2,
    )
    after = client.post(f"{BASE}/{m1['id']}/check", json={}).json()
    assert (after["morning"]["done"], after["evening"]["done"], after["day"]) == (1, 0, paris_today().isoformat())
    assert client.post(f"{BASE}/{m1['id']}/check", json={}).json()["morning"]["done"] == 1  # idempotent
    client.post(f"{BASE}/{e1['id']}/check", json={})
    undone = client.post(f"{BASE}/{m1['id']}/check", json={"checked": False}).json()
    assert (undone["morning"]["done"], undone["evening"]["done"]) == (0, 1)
    yesterday = (paris_today() - timedelta(days=1)).isoformat()
    past = client.post(f"{BASE}/{m2['id']}/check", json={"day": yesterday}).json()
    assert (past["day"], past["morning"]["done"]) == (yesterday, 1)
    assert client.get(f"{BASE}/daily").json()["morning"]["done"] == 0
    future = (date.today() + timedelta(days=2)).isoformat()
    assert client.post(f"{BASE}/{m2['id']}/check", json={"day": future}).status_code == 422
    assert client.post(f"{BASE}/{library_only['id']}/check", json={}).status_code == 422
    assert client.delete(f"{BASE}/{e1['id']}").status_code == 204
    assert client.get(f"{BASE}/daily").json()["evening"]["total"] == 0
