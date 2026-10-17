"""PostgreSQL : consentement santé et relevé corporel Pulse (doc 40 §14, doc 05 garde-fous santé)."""
from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("pulse body DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_pulse_health as routes  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402

P = "/api/imperium/pulse"
BODY = f"{P}/body-snapshots"


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
        {"id": str(user_id), "email": f"body-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/imperium/pulse")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def _consent(client, domain="body") -> dict:
    version = next(c for c in client.get(f"{P}/consents").json()["items"] if c["domain"] == domain)["text_version"]
    response = client.post(f"{P}/consents/{domain}", json={"text_version": version})
    assert response.status_code == 200, response.text
    return response.json()


def test_consents_start_absent_with_a_readable_text(db) -> None:
    items = _client(db, _user(db)).get(f"{P}/consents").json()["items"]
    assert [c["domain"] for c in items] == ["body", "pain", "medical"]
    assert all(c["granted"] is False and c["granted_at"] is None for c in items)
    assert all(c["text_fr"] and c["text_version"] for c in items)


def test_writing_without_consent_is_refused(db) -> None:
    client = _client(db, _user(db))
    refused = client.post(BODY, headers=_key(), json={"measured_at": "2026-10-17T07:00:00+00:00", "weight_kg": 80})
    assert refused.status_code == 403
    assert refused.json()["code"] == "CONSENT_REQUIRED" and refused.json()["domain"] == "body"


def test_consent_requires_the_current_text_version(db) -> None:
    client = _client(db, _user(db))
    assert client.post(f"{P}/consents/body", json={"text_version": "ancienne"}).status_code == 409
    assert client.post(f"{P}/consents/inconnu", json={"text_version": "x"}).status_code == 422


def test_snapshot_with_consent_then_list(db) -> None:
    user = _user(db)
    client = _client(db, user)
    granted = _consent(client)
    assert granted["granted"] is True and granted["granted_at"] is not None
    assert _consent(client)["granted_at"] == granted["granted_at"]  # déjà donné : inchangé
    first = client.post(BODY, headers=_key(), json={"measured_at": "2026-10-10T07:00:00+00:00", "weight_kg": 82.4,
                                                    "waist_cm": 90.5, "notes": "À jeun"})
    assert first.status_code == 201, first.text
    client.post(BODY, headers=_key(), json={"measured_at": "2026-10-17T07:00:00+00:00", "weight_kg": 81.1})
    listed = client.get(BODY).json()
    assert [s["weight_kg"] for s in listed["items"]] == ["81.10", "82.40"]
    assert listed["weight_change_kg"] == "-1.30"
    event = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "pulse.body_snapshot.created"))
    assert set(event.payload) == {"snapshot_id"}  # aucune mesure dans le journal d'événements
    assert event.privacy_level == "high"


@pytest.mark.parametrize("payload", [
    {"measured_at": "2026-10-17T07:00:00+00:00"},  # aucune mesure
    {"measured_at": "2026-10-17T07:00:00+00:00", "weight_kg": 0},
    {"measured_at": "2026-10-17T07:00:00+00:00", "weight_kg": 80, "photo_uri": "file:///x.jpg"},  # photo refusée
    {"measured_at": "2026-10-17T07:00:00+00:00", "body_fat_percent": 80},
])
def test_invalid_snapshots_are_rejected(db, payload) -> None:
    client = _client(db, _user(db))
    _consent(client)
    assert client.post(BODY, headers=_key(), json=payload).status_code == 422


def test_idempotency(db) -> None:
    client = _client(db, _user(db))
    _consent(client)
    payload = {"measured_at": "2026-10-17T07:00:00+00:00", "weight_kg": 80}
    assert client.post(BODY, json=payload).status_code == 400
    first = client.post(BODY, headers={"Idempotency-Key": "b1"}, json=payload)
    again = client.post(BODY, headers={"Idempotency-Key": "b1"}, json=payload)
    other = client.post(BODY, headers={"Idempotency-Key": "b1"}, json={**payload, "weight_kg": 81})
    assert first.status_code == 201 and again.status_code == 200 and again.json()["id"] == first.json()["id"]
    assert other.status_code == 409


def test_revoking_blocks_writes_but_keeps_access_and_deletion(db) -> None:
    client = _client(db, _user(db))
    _consent(client)
    snap = client.post(BODY, headers=_key(), json={"measured_at": "2026-10-17T07:00:00+00:00", "weight_kg": 80}).json()
    revoked = client.delete(f"{P}/consents/body")
    assert revoked.status_code == 200 and revoked.json()["granted"] is False and revoked.json()["revoked_at"] is not None
    assert client.post(BODY, headers=_key(), json={"measured_at": "2026-10-18T07:00:00+00:00", "weight_kg": 79}).status_code == 403
    assert len(client.get(BODY).json()["items"]) == 1  # l'accès à ses données reste ouvert
    assert client.delete(f"{BODY}/{snap['id']}").status_code == 204
    assert client.get(BODY).json()["items"] == []
    assert client.delete(f"{BODY}/{snap['id']}").status_code == 404


def test_delete_everything_needs_confirmation_and_really_deletes(db) -> None:
    from app.models.imperium import PulseBodySnapshot

    user = _user(db)
    client = _client(db, user)
    _consent(client)
    for day in ("10", "17"):
        client.post(BODY, headers=_key(), json={"measured_at": f"2026-10-{day}T07:00:00+00:00", "weight_kg": 80})
    assert client.delete(BODY).status_code == 422
    deleted = client.delete(BODY, params={"confirm": True})
    assert deleted.status_code == 200 and deleted.json() == {"deleted": 2}
    db.expire_all()
    assert db.scalars(select(PulseBodySnapshot).where(PulseBodySnapshot.user_id == user.id)).all() == []
    event = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "pulse.body_snapshot.deleted"))
    assert event.payload == {"deleted": 2, "scope": "all"}


def test_other_users_cannot_read_or_delete(db) -> None:
    owner, other = _user(db), _user(db)
    client = _client(db, owner)
    _consent(client)
    snap = client.post(BODY, headers=_key(), json={"measured_at": "2026-10-17T07:00:00+00:00", "weight_kg": 80}).json()
    stranger = _client(db, other)
    assert stranger.get(BODY).json()["items"] == []
    assert stranger.delete(f"{BODY}/{snap['id']}").status_code == 404
