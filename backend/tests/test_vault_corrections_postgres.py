"""PostgreSQL : correction d'une transaction Vault (VAU-08) — écriture inverse + corrigée, registre en ajout seul."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("vault corrections DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_vault  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.vault import ImperiumVaultTransaction  # noqa: E402

BASE = "/api/imperium/vault/transactions"


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
        {"id": str(user_id), "email": f"correct-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_vault.router, prefix="/api/imperium/vault")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def _create(client, **extra) -> dict:
    payload = {"transaction_type": "expense", "amount_cents": 4500, "occurred_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
               "timezone": "Europe/Paris", "category": "courses", "note": "Marché", "external_ref": "receipt:abc", **extra}
    response = client.post(BASE, headers=_key(), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_correction_reverses_and_appends_in_one_write(db) -> None:
    user = _user(db)
    client = _client(db, user)
    original = _create(client)
    key = _key()
    corrected = client.post(f"{BASE}/{original['id']}/correct", headers=key,
                            json={"reason": "Montant mal saisi", "amount_cents": 5400, "category": "Restaurant"})
    assert corrected.status_code == 201, corrected.text
    body = corrected.json()
    assert (body["reversal"]["transaction_type"], body["reversal"]["amount_cents"], body["reversal"]["reversal_reason"]) == (
        "income", 4500, "Montant mal saisi",
    )
    new = body["corrected"]
    assert (new["amount_cents"], new["category"], new["note"], new["external_ref"], body["original_transaction_id"]) == (
        5400, "restaurant", "Marché", "receipt:abc", original["id"],
    )
    assert str(db.get(ImperiumVaultTransaction, new["id"]).corrects_transaction_id) == original["id"]
    assert (new["local_date"], new["occurred_at"]) == (original["local_date"], original["occurred_at"])
    assert client.post(f"{BASE}/{original['id']}/correct", headers=key,
                       json={"reason": "Montant mal saisi", "amount_cents": 5400, "category": "Restaurant"}).json() == body
    rows = list(db.scalars(select(ImperiumVaultTransaction).where(ImperiumVaultTransaction.user_id == user.id)))
    assert len(rows) == 3
    net = sum(r.amount_cents if r.transaction_type == "income" else -r.amount_cents for r in rows)
    assert net == -5400
    created = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "finance.transaction.created",
                                            Event.payload["corrects_transaction_id"].astext == original["id"]))
    assert created is not None


def test_cannot_correct_twice_or_a_reversal(db) -> None:
    client = _client(db, _user(db))
    original = _create(client)
    body = client.post(f"{BASE}/{original['id']}/correct", headers=_key(), json={"reason": "Erreur", "amount_cents": 100}).json()
    again = client.post(f"{BASE}/{original['id']}/correct", headers=_key(), json={"reason": "Encore", "amount_cents": 200})
    assert again.status_code == 409
    assert client.post(f"{BASE}/{body['reversal']['id']}/correct", headers=_key(), json={"reason": "Non", "amount_cents": 1}).status_code == 409
    second = client.post(f"{BASE}/{body['corrected']['id']}/correct", headers=_key(), json={"reason": "Re-corriger", "amount_cents": 300})
    assert second.status_code == 201  # la corrigée se corrige à son tour
    assert client.post(f"{BASE}/{body['corrected']['id']}/reverse", headers=_key(), json={"reason": "x"}).status_code == 409


def test_correction_needs_a_change_and_a_reason(db) -> None:
    client = _client(db, _user(db))
    original = _create(client)
    assert client.post(f"{BASE}/{original['id']}/correct", headers=_key(), json={"reason": "Rien", "amount_cents": 4500}).status_code == 409
    assert client.post(f"{BASE}/{original['id']}/correct", headers=_key(), json={"amount_cents": 10}).status_code == 422
    assert client.post(f"{BASE}/{uuid4()}/correct", headers=_key(), json={"reason": "Inconnue", "amount_cents": 1}).status_code == 404
    moved = client.post(f"{BASE}/{original['id']}/correct", headers=_key(),
                        json={"reason": "Mauvais jour", "occurred_at": "2026-10-01T12:00:00+02:00", "note": ""}).json()
    assert (moved["corrected"]["local_date"], moved["corrected"]["note"]) == ("2026-10-01", None)


def test_sadaqa_expense_is_corrected_from_path(db) -> None:
    client = _client(db, _user(db))
    original = _create(client, source="path_sadaqa", category="sadaqa", external_ref="sadaqa:x")
    refused = client.post(f"{BASE}/{original['id']}/correct", headers=_key(), json={"reason": "Montant", "amount_cents": 1})
    assert (refused.status_code, refused.json()["detail"]) == (409, "Corrige ce don depuis Path (sadaqa).")
