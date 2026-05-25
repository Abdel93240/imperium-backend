from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium_vault
from app.models.vault import ImperiumVaultTransaction


BACKEND_ROOT = Path(__file__).resolve().parents[1]


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
    occurred_at = overrides.pop("occurred_at", now)
    return ImperiumVaultTransaction(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        transaction_type=overrides.pop("transaction_type", "income"),
        amount_cents=overrides.pop("amount_cents", 1000),
        currency=overrides.pop("currency", "EUR"),
        occurred_at=occurred_at,
        local_date=overrides.pop("local_date", occurred_at.date()),
        timezone=overrides.pop("timezone", "UTC"),
        category=overrides.pop("category", "fuel"),
        source=overrides.pop("source", "manual"),
        note=overrides.pop("note", None),
        external_ref=overrides.pop("external_ref", None),
        created_at=overrides.pop("created_at", now),
        updated_at=overrides.pop("updated_at", now),
    )


def test_get_vault_category_summary_empty_returns_items_list_and_count_zero() -> None:
    current_user = _user()
    db = FakeDb(scalars_results=[[]])

    response = _client(db, current_user).get("/imperium/vault/summary/categories")

    assert response.status_code == 200
    assert response.json() == {
        "currency": "EUR",
        "items": [],
        "count": 0,
        "safe_explanation": "Vault category summary computed from current user's ledger transactions.",
    }


def test_get_vault_category_summary_groups_income_and_expense_by_category() -> None:
    current_user = _user()
    db = FakeDb(
        scalars_results=[
            [
                _transaction(current_user.id, transaction_type="income", amount_cents=12000, category="rides"),
                _transaction(current_user.id, transaction_type="expense", amount_cents=2500, category="rides"),
                _transaction(current_user.id, transaction_type="expense", amount_cents=900, category="fuel"),
            ]
        ]
    )

    response = _client(db, current_user).get("/imperium/vault/summary/categories")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["items"][0] == {
        "category": "rides",
        "total_income_cents": 12000,
        "total_expense_cents": 2500,
        "net_cents": 9500,
        "transaction_count": 2,
        "income_count": 1,
        "expense_count": 1,
    }
    assert body["items"][1] == {
        "category": "fuel",
        "total_income_cents": 0,
        "total_expense_cents": 900,
        "net_cents": -900,
        "transaction_count": 1,
        "income_count": 0,
        "expense_count": 1,
    }


def test_get_vault_category_summary_maps_null_or_empty_category_to_uncategorized() -> None:
    current_user = _user()
    db = FakeDb(
        scalars_results=[
            [
                _transaction(current_user.id, transaction_type="income", amount_cents=4000, category=None),
                _transaction(current_user.id, transaction_type="expense", amount_cents=1250, category=" "),
            ]
        ]
    )

    response = _client(db, current_user).get("/imperium/vault/summary/categories")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"] == [
        {
            "category": "uncategorized",
            "total_income_cents": 4000,
            "total_expense_cents": 1250,
            "net_cents": 2750,
            "transaction_count": 2,
            "income_count": 1,
            "expense_count": 1,
        }
    ]


def test_get_vault_category_summary_calculates_net_correctly() -> None:
    current_user = _user()
    db = FakeDb(
        scalars_results=[
            [
                _transaction(current_user.id, transaction_type="income", amount_cents=6000, category="fuel"),
                _transaction(current_user.id, transaction_type="expense", amount_cents=1250, category="fuel"),
                _transaction(current_user.id, transaction_type="expense", amount_cents=750, category="fuel"),
            ]
        ]
    )

    response = _client(db, current_user).get("/imperium/vault/summary/categories")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["net_cents"] == 4000
    assert body["items"][0]["total_income_cents"] == 6000
    assert body["items"][0]["total_expense_cents"] == 2000


def test_get_vault_category_summary_is_strictly_user_scoped() -> None:
    current_user = _user()
    db = FakeDb(
        scalars_results=[
            [
                _transaction(current_user.id, transaction_type="income", amount_cents=3000, category="fuel"),
            ]
        ]
    )

    response = _client(db, current_user).get("/imperium/vault/summary/categories")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["transaction_count"] == 1
    assert body["items"][0]["total_income_cents"] == 3000
    assert body["items"][0]["total_expense_cents"] == 0
    assert "imperium_vault_transactions.user_id" in str(db.queries[0])


def test_get_vault_category_summary_filters_currency() -> None:
    current_user = _user()
    db = FakeDb(
        scalars_results=[
            [
                _transaction(current_user.id, transaction_type="expense", amount_cents=2300, currency="USD", category="fuel"),
            ]
        ]
    )

    response = _client(db, current_user).get("/imperium/vault/summary/categories?currency=usd")

    assert response.status_code == 200
    body = response.json()
    assert body["currency"] == "USD"
    assert body["count"] == 1
    assert body["items"][0]["total_income_cents"] == 0
    assert body["items"][0]["total_expense_cents"] == 2300
    assert "imperium_vault_transactions.currency" in str(db.queries[0])


def test_get_vault_category_summary_filters_transaction_type_income() -> None:
    current_user = _user()
    db = FakeDb(
        scalars_results=[
            [
                _transaction(current_user.id, transaction_type="income", amount_cents=4500, category="fuel"),
                _transaction(current_user.id, transaction_type="income", amount_cents=1800, category="rides"),
            ]
        ]
    )

    response = _client(db, current_user).get("/imperium/vault/summary/categories?transaction_type=income")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["items"][0] == {
        "category": "fuel",
        "total_income_cents": 4500,
        "total_expense_cents": 0,
        "net_cents": 4500,
        "transaction_count": 1,
        "income_count": 1,
        "expense_count": 0,
    }
    assert body["items"][1] == {
        "category": "rides",
        "total_income_cents": 1800,
        "total_expense_cents": 0,
        "net_cents": 1800,
        "transaction_count": 1,
        "income_count": 1,
        "expense_count": 0,
    }


def test_get_vault_category_summary_filters_transaction_type_expense() -> None:
    current_user = _user()
    db = FakeDb(
        scalars_results=[
            [
                _transaction(current_user.id, transaction_type="expense", amount_cents=1200, category="fuel"),
                _transaction(current_user.id, transaction_type="expense", amount_cents=1800, category="rides"),
            ]
        ]
    )

    response = _client(db, current_user).get("/imperium/vault/summary/categories?transaction_type=expense")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["items"][0] == {
        "category": "rides",
        "total_income_cents": 0,
        "total_expense_cents": 1800,
        "net_cents": -1800,
        "transaction_count": 1,
        "income_count": 0,
        "expense_count": 1,
    }
    assert body["items"][1] == {
        "category": "fuel",
        "total_income_cents": 0,
        "total_expense_cents": 1200,
        "net_cents": -1200,
        "transaction_count": 1,
        "income_count": 0,
        "expense_count": 1,
    }


def test_get_vault_category_summary_filters_occurred_from() -> None:
    current_user = _user()
    newer = datetime(2026, 5, 25, 8, 0, tzinfo=UTC)
    occurred_from = datetime(2026, 5, 25, 0, 0, tzinfo=UTC)
    db = FakeDb(
        scalars_results=[
            [
                _transaction(current_user.id, transaction_type="expense", amount_cents=1000, category="fuel", occurred_at=newer),
            ]
        ]
    )

    response = _client(db, current_user).get(
        f"/imperium/vault/summary/categories?occurred_from={occurred_from.isoformat().replace('+00:00', 'Z')}"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["transaction_count"] == 1
    assert body["items"][0]["total_income_cents"] == 0
    assert body["items"][0]["total_expense_cents"] == 1000


def test_get_vault_category_summary_filters_occurred_to() -> None:
    current_user = _user()
    older = datetime(2026, 5, 24, 8, 0, tzinfo=UTC)
    occurred_to = datetime(2026, 5, 24, 23, 59, tzinfo=UTC)
    db = FakeDb(
        scalars_results=[
            [
                _transaction(current_user.id, transaction_type="income", amount_cents=4000, category="fuel", occurred_at=older),
            ]
        ]
    )

    response = _client(db, current_user).get(
        f"/imperium/vault/summary/categories?occurred_to={occurred_to.isoformat().replace('+00:00', 'Z')}"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["transaction_count"] == 1
    assert body["items"][0]["total_income_cents"] == 4000
    assert body["items"][0]["total_expense_cents"] == 0


def test_get_vault_category_summary_sorts_deterministically() -> None:
    current_user = _user()
    db = FakeDb(
        scalars_results=[
            [
                _transaction(current_user.id, transaction_type="income", amount_cents=1100, category="beta"),
                _transaction(current_user.id, transaction_type="expense", amount_cents=200, category="beta"),
                _transaction(current_user.id, transaction_type="expense", amount_cents=200, category="beta"),
                _transaction(current_user.id, transaction_type="income", amount_cents=2500, category="delta"),
                _transaction(current_user.id, transaction_type="expense", amount_cents=500, category="delta"),
                _transaction(current_user.id, transaction_type="expense", amount_cents=400, category="delta"),
                _transaction(current_user.id, transaction_type="income", amount_cents=1000, category="alpha"),
                _transaction(current_user.id, transaction_type="expense", amount_cents=200, category="alpha"),
                _transaction(current_user.id, transaction_type="expense", amount_cents=100, category="alpha"),
                _transaction(current_user.id, transaction_type="income", amount_cents=900, category="gamma"),
                _transaction(current_user.id, transaction_type="expense", amount_cents=200, category="gamma"),
            ]
        ]
    )

    response = _client(db, current_user).get("/imperium/vault/summary/categories")

    assert response.status_code == 200
    assert [item["category"] for item in response.json()["items"]] == ["delta", "alpha", "beta", "gamma"]


def test_get_vault_category_summary_does_not_require_idempotency_key() -> None:
    response = _client(FakeDb(scalars_results=[[]]), _user()).get("/imperium/vault/summary/categories")

    assert response.status_code == 200
    assert response.json()["count"] == 0


def test_get_vault_category_summary_is_read_only_and_has_no_ai_n8n_or_persistent_wallet_side_effects() -> None:
    current_user = _user()
    db = FakeDb(
        scalars_results=[
            [
                _transaction(current_user.id, transaction_type="income", amount_cents=1000, category="fuel"),
            ]
        ]
    )

    response = _client(db, current_user).get("/imperium/vault/summary/categories")

    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False
    assert db.rolled_back is False

    route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_vault.py").read_text(encoding="utf-8")
    service_text = (BACKEND_ROOT / "app" / "services" / "imperium" / "vault.py").read_text(encoding="utf-8")
    lowered = "\n".join([route_text, service_text]).lower()

    assert "qwenclient" not in lowered
    assert "n8n" not in lowered
    assert "pgvector" not in lowered
    assert "embedding" not in lowered
    assert "memory" not in lowered
    assert "calendar" not in lowered
    assert "ocr" not in lowered
    assert "sadaqa" not in lowered
    assert "wallet" not in lowered
    assert "balance" not in lowered
    assert "db.add(" not in route_text
    assert "db.flush" not in route_text
    assert "db.commit" not in route_text
    assert "db.add(" not in service_text
    assert "db.flush" not in service_text
    assert "db.commit" not in service_text


def test_get_vault_category_summary_rejects_naive_occurred_from() -> None:
    response = _client(FakeDb(scalars_results=[[]]), _user()).get(
        "/imperium/vault/summary/categories?occurred_from=2026-01-01T00:00:00"
    )

    assert response.status_code == 422
