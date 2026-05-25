from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium_vault
from app.models.vault import ImperiumVaultTransaction


class FakeDb:
    def __init__(self, *, scalars_results=None) -> None:
        self.scalars_results = [list(result) for result in scalars_results] if scalars_results is not None else None
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

    def scalars(self, query):
        self.queries.append(query)
        if self.scalars_results is not None:
            if self.scalars_results:
                return self.scalars_results.pop(0)
            return []
        return []


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
    return ImperiumVaultTransaction(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        transaction_type=overrides.pop("transaction_type", "income"),
        amount_cents=overrides.pop("amount_cents", 1000),
        currency=overrides.pop("currency", "EUR"),
        occurred_at=overrides.pop("occurred_at", now),
        category=overrides.pop("category", "vtc"),
        source=overrides.pop("source", "manual"),
        note=overrides.pop("note", None),
        external_ref=overrides.pop("external_ref", None),
        created_at=overrides.pop("created_at", now),
        updated_at=overrides.pop("updated_at", now),
    )


def test_get_vault_summary_empty_returns_zeros() -> None:
    current_user = _user()
    db = FakeDb(scalars_results=[[]])

    response = _client(db, current_user).get("/imperium/vault/summary")

    assert response.status_code == 200
    assert response.json() == {
        "currency": "EUR",
        "occurred_from": None,
        "occurred_to": None,
        "total_income_cents": 0,
        "total_expense_cents": 0,
        "net_cents": 0,
        "transaction_count": 0,
        "income_count": 0,
        "expense_count": 0,
        "safe_explanation": "Vault summary computed from current user's ledger transactions.",
    }


def test_get_vault_summary_calculates_income_expense_and_net() -> None:
    current_user = _user()
    db = FakeDb(
        scalars_results=[
            [
                _transaction(current_user.id, transaction_type="income", amount_cents=10000),
                _transaction(current_user.id, transaction_type="expense", amount_cents=2000),
                _transaction(current_user.id, transaction_type="expense", amount_cents=1500),
            ]
        ]
    )

    response = _client(db, current_user).get("/imperium/vault/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total_income_cents"] == 10000
    assert body["total_expense_cents"] == 3500
    assert body["net_cents"] == 6500
    assert body["transaction_count"] == 3
    assert body["income_count"] == 1
    assert body["expense_count"] == 2


def test_get_vault_summary_is_strictly_user_scoped() -> None:
    current_user = _user()
    other_user = _user()
    db = FakeDb(
        scalars_results=[
            [
                _transaction(current_user.id, transaction_type="income", amount_cents=4000),
                _transaction(other_user.id, transaction_type="expense", amount_cents=9000),
            ]
        ]
    )

    response = _client(db, current_user).get("/imperium/vault/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["transaction_count"] == 1
    assert body["total_income_cents"] == 4000
    assert body["total_expense_cents"] == 0
    assert "imperium_vault_transactions.user_id" in str(db.queries[0])


def test_get_vault_summary_filters_currency_and_normalizes_case() -> None:
    current_user = _user()
    db = FakeDb(
        scalars_results=[
            [
                _transaction(current_user.id, transaction_type="income", amount_cents=7000, currency="EUR"),
                _transaction(current_user.id, transaction_type="income", amount_cents=9000, currency="USD"),
                _transaction(current_user.id, transaction_type="expense", amount_cents=3000, currency="USD"),
            ]
        ]
    )

    response = _client(db, current_user).get("/imperium/vault/summary?currency=usd")

    assert response.status_code == 200
    body = response.json()
    assert body["currency"] == "USD"
    assert body["transaction_count"] == 2
    assert body["total_income_cents"] == 9000
    assert body["total_expense_cents"] == 3000
    assert "imperium_vault_transactions.currency" in str(db.queries[0])


def test_get_vault_summary_filters_occurred_from() -> None:
    current_user = _user()
    older = datetime(2026, 5, 24, 8, 0, tzinfo=UTC)
    newer = datetime(2026, 5, 25, 8, 0, tzinfo=UTC)
    occurred_from = datetime(2026, 5, 25, 0, 0, tzinfo=UTC)
    db = FakeDb(
        scalars_results=[
            [
                _transaction(current_user.id, transaction_type="income", amount_cents=4000, occurred_at=older),
                _transaction(current_user.id, transaction_type="expense", amount_cents=1000, occurred_at=newer),
            ]
        ]
    )

    response = _client(db, current_user).get(
        f"/imperium/vault/summary?occurred_from={occurred_from.isoformat().replace('+00:00', 'Z')}"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["occurred_from"] is not None
    assert body["transaction_count"] == 1
    assert body["total_income_cents"] == 0
    assert body["total_expense_cents"] == 1000


def test_get_vault_summary_filters_occurred_to() -> None:
    current_user = _user()
    older = datetime(2026, 5, 24, 8, 0, tzinfo=UTC)
    newer = datetime(2026, 5, 25, 8, 0, tzinfo=UTC)
    occurred_to = datetime(2026, 5, 24, 23, 59, tzinfo=UTC)
    db = FakeDb(
        scalars_results=[
            [
                _transaction(current_user.id, transaction_type="income", amount_cents=4000, occurred_at=older),
                _transaction(current_user.id, transaction_type="expense", amount_cents=1000, occurred_at=newer),
            ]
        ]
    )

    response = _client(db, current_user).get(
        f"/imperium/vault/summary?occurred_to={occurred_to.isoformat().replace('+00:00', 'Z')}"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["occurred_to"] is not None
    assert body["transaction_count"] == 1
    assert body["total_income_cents"] == 4000
    assert body["total_expense_cents"] == 0


def test_get_vault_summary_does_not_require_idempotency_key() -> None:
    response = _client(FakeDb(scalars_results=[[]]), _user()).get("/imperium/vault/summary")

    assert response.status_code == 200
    assert response.json()["safe_explanation"] == "Vault summary computed from current user's ledger transactions."


def test_get_vault_summary_is_read_only() -> None:
    current_user = _user()
    db = FakeDb(scalars_results=[[ _transaction(current_user.id) ]])

    response = _client(db, current_user).get("/imperium/vault/summary")

    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False
    assert db.rolled_back is False
