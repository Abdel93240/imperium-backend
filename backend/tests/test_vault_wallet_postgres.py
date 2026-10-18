"""PostgreSQL : soldes réels du Vault (VAU-10, doc 42 §8) et échéances payées (VAU-11, doc 42 §10)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("vault wallet DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import vault as vault_routes  # noqa: E402
from app.models.auth import User  # noqa: E402
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
        {"id": str(user_id), "email": f"wallet-{user_id}@example.test"},
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


def _tx(db, user, kind, cents, wallet="cash", at=None) -> None:
    vault_transactions.create_vault_transaction(
        db, current_user=user,
        payload=ImperiumVaultTransactionCreate(transaction_type=kind, amount_cents=cents, wallet=wallet,
                                               occurred_at=at or datetime.now(UTC), timezone="Europe/Paris", category="courses"),
        idempotency_key=uuid4().hex, request_method="POST", request_path="/t",
    )


def test_wallet_without_snapshot_asks_for_one(db) -> None:
    client = _client(db, _user(db))
    body = client.get(f"{BASE}/wallet").json()
    assert (body["snapshot"], body["message"]) == (None, "Saisis tes soldes réels pour suivre ton wallet.")


def test_snapshot_then_predicted_balance(db) -> None:
    user = _user(db)
    client = _client(db, user)
    _tx(db, user, "income", 99999, at=datetime.now(UTC) - timedelta(days=3))  # avant le relevé : ignoré
    key = _key()
    recorded_at = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    payload = {"cash_cents": 10000, "bank_cents": -5000, "crypto_cents": 20000, "recorded_at": recorded_at}
    created = client.post(f"{BASE}/wallet/snapshots", headers=key, json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["snapshot"]["total_cents"] == 25000
    assert client.post(f"{BASE}/wallet/snapshots", headers=key, json=payload).status_code == 200
    assert client.post(f"{BASE}/wallet/snapshots", headers=key, json={**payload, "cash_cents": 1}).status_code == 409
    _tx(db, user, "expense", 500, "cash")
    _tx(db, user, "income", 700, "bank")
    _tx(db, user, "income", 4000, "bolt")
    state = client.get(f"{BASE}/wallet").json()
    assert (state["predicted_cash_cents"], state["predicted_bank_cents"], state["predicted_crypto_cents"]) == (9500, -4300, 20000)
    assert (state["predicted_total_cents"], state["transactions_since"], state["other_wallets_cents"]) == (25200, 3, {"bolt": 4000})
    assert (state["check_suggested"], state["message"]) == (False, None)
    _tx(db, user, "expense", 3000, "bank")
    drift = client.get(f"{BASE}/wallet").json()
    assert (drift["check_suggested"], drift["message"]) == (True, "Vérifier ton solde réel ?")
    assert len(client.get(f"{BASE}/wallet/snapshots").json()) == 1


def test_snapshot_input_checks(db) -> None:
    client = _client(db, _user(db))
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    assert client.post(f"{BASE}/wallet/snapshots", headers=_key(), json={"cash_cents": 1, "bank_cents": 1, "recorded_at": future}).status_code == 422
    assert client.post(f"{BASE}/wallet/snapshots", headers=_key(), json={"cash_cents": -1, "bank_cents": 0}).status_code == 422
    assert client.post(f"{BASE}/wallet/snapshots", json={"cash_cents": 1, "bank_cents": 0}).status_code == 400


def test_pressure_reads_the_latest_snapshot(db) -> None:
    user = _user(db)
    client = _client(db, user)
    _tx(db, user, "income", 500000, "bank", at=datetime.now(UTC) - timedelta(days=10))
    now = datetime.now(UTC)
    before = load_pressure_inputs(db, current_user=user, today=now.date(), now=now)
    assert before.available_liquidity == Decimal("5000.00")
    client.post(f"{BASE}/wallet/snapshots", headers=_key(),
                json={"cash_cents": 2000, "bank_cents": 8000, "crypto_cents": 50000,
                      "recorded_at": (now - timedelta(hours=1)).isoformat()})
    _tx(db, user, "expense", 1500, "cash")
    later = datetime.now(UTC)
    after = load_pressure_inputs(db, current_user=user, today=later.date(), now=later)
    assert after.available_liquidity == Decimal("85.00")  # 20 + 80 − 15 ; la crypto ne compte pas


def test_mark_paid_writes_the_expense_and_rolls_the_recurrence(db) -> None:
    user = _user(db)
    client = _client(db, user)
    created = client.post(f"{BASE}/upcoming-expenses", json={
        "label_fr": "Loyer", "amount": "650.00", "due_date": date(2026, 10, 31).isoformat(), "recurrence": "monthly",
        "category": "loyer", "wallet": "bank",
    }).json()
    key = _key()
    paid = client.post(f"{BASE}/upcoming-expenses/{created['id']}/mark-paid", headers=key, json={})
    assert paid.status_code == 200, paid.text
    body = paid.json()
    assert (body["expense"]["active"], body["expense"]["paid_transaction_id"]) == (False, body["transaction"]["id"])
    assert (body["transaction"]["amount_cents"], body["transaction"]["wallet"], body["transaction"]["category"]) == (65000, "bank", "loyer")
    assert (body["next_occurrence"]["due_date"], body["next_occurrence"]["active"]) == ("2026-11-30", True)
    assert client.post(f"{BASE}/upcoming-expenses/{created['id']}/mark-paid", headers=key, json={}).json()["transaction"]["id"] == body["transaction"]["id"]
    assert client.post(f"{BASE}/upcoming-expenses/{created['id']}/mark-paid", headers=_key(), json={}).status_code == 409
    transactions = list(db.scalars(select(ImperiumVaultTransaction).where(ImperiumVaultTransaction.user_id == user.id)))
    assert [(t.source, t.note) for t in transactions] == [("upcoming_expense", "Loyer")]
    pending = [e for e in db.scalars(select(UpcomingExpense).where(UpcomingExpense.user_id == user.id)) if e.active]
    assert [e.due_date for e in pending] == [date(2026, 11, 30)]


def test_mark_paid_one_off_with_another_amount(db) -> None:
    client = _client(db, _user(db))
    created = client.post(f"{BASE}/upcoming-expenses", json={
        "label_fr": "Contrôle technique", "amount": "80.00", "due_date": "2026-11-05", "category": "entretien",
    }).json()
    paid = client.post(f"{BASE}/upcoming-expenses/{created['id']}/mark-paid", headers=_key(), json={"amount_cents": 7800}).json()
    assert (paid["transaction"]["amount_cents"], paid["transaction"]["wallet"], paid["next_occurrence"]) == (7800, "cash", None)
    assert client.post(f"{BASE}/upcoming-expenses/{uuid4()}/mark-paid", headers=_key(), json={}).status_code == 404
