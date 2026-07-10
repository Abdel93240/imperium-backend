from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium_vault
from app.models.vault import ImperiumVaultTransaction


class FakeDb:
    def __init__(self, *, scalar_result=None) -> None:
        self.scalar_result = scalar_result
        self.added = []
        self.queries = []
        self.flushed = False
        self.committed = False
        self.rolled_back = False

    def add(self, obj) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed = True

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def scalar(self, query):
        self.queries.append(query)
        return self.scalar_result


def _user(user_id=None) -> SimpleNamespace:
    return SimpleNamespace(id=user_id or uuid4())


def _client(db: FakeDb, current_user: SimpleNamespace) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_vault.router, prefix="/imperium/vault")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _transaction(user_id, **overrides) -> ImperiumVaultTransaction:
    now = datetime.now(UTC)
    occurred_at = overrides.pop("occurred_at", now)
    return ImperiumVaultTransaction(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        transaction_type=overrides.pop("transaction_type", "income"),
        amount_cents=overrides.pop("amount_cents", 1234),
        currency=overrides.pop("currency", "EUR"),
        wallet=overrides.pop("wallet", "cash"),
        occurred_at=occurred_at,
        local_date=overrides.pop("local_date", occurred_at.date()),
        timezone=overrides.pop("timezone", "UTC"),
        category=overrides.pop("category", "vtc"),
        source=overrides.pop("source", "manual"),
        note=overrides.pop("note", "ok"),
        external_ref=overrides.pop("external_ref", "ext-1"),
        created_at=overrides.pop("created_at", now),
        updated_at=overrides.pop("updated_at", now),
    )


def test_get_transaction_detail_returns_current_user_transaction() -> None:
    current_user = _user()
    own = _transaction(current_user.id)
    db = FakeDb(scalar_result=own)

    response = _client(db, current_user).get(f"/imperium/vault/transactions/{own.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["transaction"]["id"] == str(own.id)
    assert body["transaction"]["amount_cents"] == own.amount_cents
    assert body["transaction"]["wallet"] == "cash"
    assert body["transaction"]["local_date"] == own.local_date.isoformat()
    assert body["transaction"]["timezone"] == "UTC"
    assert body["safe_explanation"] == "Vault transaction detail for current user."
    assert "user_id" not in body["transaction"]


def test_get_transaction_detail_not_found_returns_404() -> None:
    response = _client(FakeDb(scalar_result=None), _user()).get(f"/imperium/vault/transactions/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Vault transaction not found."


def test_get_transaction_detail_non_owned_returns_404() -> None:
    current_user = _user()
    other = _user()
    foreign = _transaction(other.id)
    response = _client(FakeDb(scalar_result=None), current_user).get(f"/imperium/vault/transactions/{foreign.id}")

    assert response.status_code == 404


def test_get_transaction_detail_does_not_require_idempotency_key() -> None:
    current_user = _user()
    own = _transaction(current_user.id)
    db = FakeDb(scalar_result=own)

    response = _client(db, current_user).get(f"/imperium/vault/transactions/{own.id}")

    assert response.status_code == 200


def test_get_transaction_detail_is_read_only() -> None:
    current_user = _user()
    own = _transaction(current_user.id)
    db = FakeDb(scalar_result=own)

    response = _client(db, current_user).get(f"/imperium/vault/transactions/{own.id}")

    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False
    assert db.rolled_back is False
