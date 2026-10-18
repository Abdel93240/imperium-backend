"""PostgreSQL : corrections manuelles de la pression (doc 11 « Manual Correction »)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("vault pressure corrections DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import vault as vault_routes  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.vault import ImperiumVaultTransaction, UpcomingExpense  # noqa: E402
from app.schemas.vault import ImperiumVaultTransactionCreate  # noqa: E402
from app.services.imperium import vault_transactions  # noqa: E402
from app.services.vault.pressure import load_pressure_inputs  # noqa: E402

BASE = "/api/vault"


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
        {"id": str(user_id), "email": f"pcorr-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(vault_routes.router, prefix=BASE)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def _expense(client, amount="900.00") -> dict:
    today = datetime.now(UTC).date()
    created = client.post(f"{BASE}/upcoming-expenses", json={"label_fr": "Leasing", "amount": amount,
                                                             "due_date": today.isoformat(), "category": "leasing"})
    assert created.status_code in (200, 201), created.text
    return created.json()


def _correct(client, **payload):
    return client.post(f"{BASE}/pressure/corrections", headers=_key(), json={"reason": "Réglé hier en espèces", **payload})


def test_handled_expense_leaves_the_pressure_and_is_explained(db) -> None:
    user = _user(db)
    client = _client(db, user)
    expense = _expense(client)
    before = client.get(f"{BASE}/pressure").json()["score"]
    key = _key()
    body = {"kind": "handled", "upcoming_expense_id": expense["id"], "reason": "Réglé hier en espèces"}
    created = client.post(f"{BASE}/pressure/corrections", headers=key, json=body)
    assert created.status_code == 201, created.text
    result = created.json()
    assert result["pressure"]["score"] < before
    assert client.post(f"{BASE}/pressure/corrections", headers=key, json=body).json()["correction"] == result["correction"]
    explain = client.get(f"{BASE}/pressure/explain").json()
    [applied] = explain["factors"]["manual_corrections"]
    assert (applied["kind"], applied["label"], applied["reason"]) == ("handled", "Leasing", "Réglé hier en espèces")
    assert db.get(UpcomingExpense, expense["id"]).active is True  # l'échéance d'origine reste intacte
    assert _correct(client, kind="postponed", upcoming_expense_id=expense["id"],
                    postponed_until=(datetime.now(UTC).date() + timedelta(days=9)).isoformat()).status_code == 409
    revoked = client.post(f"{BASE}/pressure/corrections/{result['correction']['id']}/revoke").json()
    assert revoked["correction"]["revoked_at"] is not None and revoked["pressure"]["score"] == before
    assert client.get(f"{BASE}/pressure/corrections").json() == []
    assert len(client.get(f"{BASE}/pressure/corrections", params={"include_revoked": "true"}).json()) == 1
    events = [e.payload["action"] for e in db.scalars(select(Event).where(
        Event.user_id == user.id, Event.event_type == "finance.pressure.corrected").order_by(Event.occurred_at))]
    assert events == ["created", "revoked"]


def test_postponed_expense_counts_at_its_new_date(db) -> None:
    client = _client(db, _user(db))
    expense = _expense(client)
    before = client.get(f"{BASE}/pressure").json()["score"]
    later = (datetime.now(UTC).date() + timedelta(days=8)).isoformat()  # toujours après la fin de semaine
    moved = _correct(client, kind="postponed", upcoming_expense_id=expense["id"], postponed_until=later, reason="Accord du bailleur")
    assert moved.status_code == 201, moved.text
    assert moved.json()["pressure"]["score"] < before
    assert db.get(UpcomingExpense, expense["id"]).due_date.isoformat() == expense["due_date"]
    too_early = _correct(client, kind="postponed", upcoming_expense_id=_expense(client)["id"],
                         postponed_until=expense["due_date"])
    assert too_early.status_code == 409


def test_exceptional_week_leaves_the_capacity(db) -> None:
    user = _user(db)
    client = _client(db, user)
    now = datetime.now(UTC)
    vault_transactions.create_vault_transaction(
        db, current_user=user,
        payload=ImperiumVaultTransactionCreate(transaction_type="income", amount_cents=100000, timezone="Europe/Paris",
                                               occurred_at=now - timedelta(minutes=1), category="vtc"),
        idempotency_key=uuid4().hex, request_method="POST", request_path="/t",
    )
    day = db.scalar(select(ImperiumVaultTransaction.local_date).where(ImperiumVaultTransaction.user_id == user.id))
    assert load_pressure_inputs(db, current_user=user, today=day, now=now).realistic_daily_capacity == Decimal("1000.00")
    monday = day - timedelta(days=day.weekday())
    assert _correct(client, kind="exceptional_week", week_start=monday.isoformat(), reason="Salon pro").status_code == 201
    assert load_pressure_inputs(db, current_user=user, today=day, now=now).realistic_daily_capacity == Decimal("220.00")
    assert _correct(client, kind="exceptional_week", week_start=monday.isoformat()).status_code == 409


def test_correction_inputs(db) -> None:
    client = _client(db, _user(db))
    expense = _expense(client)
    tuesday = (datetime.now(UTC).date() - timedelta(days=datetime.now(UTC).weekday() - 1)).isoformat()
    assert _correct(client, kind="exceptional_week", week_start=tuesday).status_code == 422
    assert _correct(client, kind="handled").status_code == 422
    assert _correct(client, kind="handled", upcoming_expense_id=expense["id"], reason="  ").status_code == 422
    assert _correct(client, kind="postponed", upcoming_expense_id=expense["id"]).status_code == 422
    assert _correct(client, kind="handled", upcoming_expense_id=str(uuid4())).status_code == 404
    assert client.post(f"{BASE}/pressure/corrections", json={"kind": "handled"}).status_code in (400, 422)
    other = _client(db, _user(db))
    assert other.post(f"{BASE}/pressure/corrections", headers=_key(),
                      json={"kind": "handled", "upcoming_expense_id": expense["id"], "reason": "x"}).status_code == 404
    assert other.post(f"{BASE}/pressure/corrections/{uuid4()}/revoke").status_code == 404
