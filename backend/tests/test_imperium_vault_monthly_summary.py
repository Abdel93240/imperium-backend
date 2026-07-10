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
DOCS_ROOT = BACKEND_ROOT.parent / "docs_master"


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
        category=overrides.pop("category", "vtc"),
        source=overrides.pop("source", "manual"),
        note=overrides.pop("note", None),
        external_ref=overrides.pop("external_ref", None),
        created_at=overrides.pop("created_at", now),
        updated_at=overrides.pop("updated_at", now),
    )


def test_get_vault_monthly_summary_empty_returns_items_list_and_count_zero() -> None:
    current_user = _user()
    db = FakeDb(scalars_results=[[]])

    response = _client(db, current_user).get("/imperium/vault/summary/monthly")

    assert response.status_code == 200
    assert response.json() == {
        "currency": "EUR",
        "items": [],
        "count": 0,
        "safe_explanation": "Vault monthly summary computed from current user's ledger transactions.",
    }


def test_get_vault_monthly_summary_groups_income_and_expense_by_month_and_calculates_net() -> None:
    current_user = _user()
    db = FakeDb(
        scalars_results=[
            [
                _transaction(
                    current_user.id,
                    transaction_type="income",
                    amount_cents=12000,
                    occurred_at=datetime(2026, 1, 5, 9, 0, tzinfo=UTC),
                ),
                _transaction(
                    current_user.id,
                    transaction_type="expense",
                    amount_cents=2500,
                    occurred_at=datetime(2026, 1, 12, 9, 0, tzinfo=UTC),
                ),
                _transaction(
                    current_user.id,
                    transaction_type="expense",
                    amount_cents=900,
                    occurred_at=datetime(2026, 1, 18, 9, 0, tzinfo=UTC),
                ),
                _transaction(
                    current_user.id,
                    transaction_type="income",
                    amount_cents=5000,
                    occurred_at=datetime(2026, 2, 2, 9, 0, tzinfo=UTC),
                ),
                _transaction(
                    current_user.id,
                    transaction_type="expense",
                    amount_cents=3000,
                    occurred_at=datetime(2026, 2, 11, 9, 0, tzinfo=UTC),
                ),
            ]
        ]
    )

    response = _client(db, current_user).get("/imperium/vault/summary/monthly")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["items"] == [
        {
            "month": "2026-02",
            "total_income_cents": 5000,
            "total_expense_cents": 3000,
            "net_cents": 2000,
            "transaction_count": 2,
            "income_count": 1,
            "expense_count": 1,
        },
        {
            "month": "2026-01",
            "total_income_cents": 12000,
            "total_expense_cents": 3400,
            "net_cents": 8600,
            "transaction_count": 3,
            "income_count": 1,
            "expense_count": 2,
        },
    ]


def test_get_vault_monthly_summary_is_strictly_user_scoped() -> None:
    current_user = _user()
    db = FakeDb(
        scalars_results=[
            [
                _transaction(
                    current_user.id,
                    transaction_type="income",
                    amount_cents=4000,
                    occurred_at=datetime(2026, 5, 2, 8, 0, tzinfo=UTC),
                ),
            ]
        ]
    )

    response = _client(db, current_user).get("/imperium/vault/summary/monthly")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"] == [
        {
            "month": "2026-05",
            "total_income_cents": 4000,
            "total_expense_cents": 0,
            "net_cents": 4000,
            "transaction_count": 1,
            "income_count": 1,
            "expense_count": 0,
        }
    ]
    assert "imperium_vault_transactions.user_id" in str(db.queries[0])


def test_get_vault_monthly_summary_filters_currency() -> None:
    current_user = _user()
    db = FakeDb(
        scalars_results=[
            [
                _transaction(
                    current_user.id,
                    transaction_type="expense",
                    amount_cents=2300,
                    currency="USD",
                    occurred_at=datetime(2026, 5, 4, 8, 0, tzinfo=UTC),
                ),
            ]
        ]
    )

    response = _client(db, current_user).get("/imperium/vault/summary/monthly?currency=USD")

    assert response.status_code == 200
    body = response.json()
    assert body["currency"] == "USD"
    assert body["count"] == 1
    assert body["items"] == [
        {
            "month": "2026-05",
            "total_income_cents": 0,
            "total_expense_cents": 2300,
            "net_cents": -2300,
            "transaction_count": 1,
            "income_count": 0,
            "expense_count": 1,
        }
    ]
    assert "imperium_vault_transactions.currency" in str(db.queries[0])


def test_get_vault_monthly_summary_filters_occurred_from() -> None:
    current_user = _user()
    newer = datetime(2026, 5, 25, 8, 0, tzinfo=UTC)
    occurred_from = datetime(2026, 5, 25, 0, 0, tzinfo=UTC)
    db = FakeDb(
        scalars_results=[
            [
                _transaction(current_user.id, transaction_type="expense", amount_cents=1000, occurred_at=newer),
            ]
        ]
    )

    response = _client(db, current_user).get(
        f"/imperium/vault/summary/monthly?occurred_from={occurred_from.isoformat().replace('+00:00', 'Z')}"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"] == [
        {
            "month": "2026-05",
            "total_income_cents": 0,
            "total_expense_cents": 1000,
            "net_cents": -1000,
            "transaction_count": 1,
            "income_count": 0,
            "expense_count": 1,
        }
    ]
    assert body["items"][0]["month"] == "2026-05"


def test_get_vault_monthly_summary_filters_occurred_to() -> None:
    current_user = _user()
    older = datetime(2026, 5, 24, 8, 0, tzinfo=UTC)
    occurred_to = datetime(2026, 5, 24, 23, 59, tzinfo=UTC)
    db = FakeDb(
        scalars_results=[
            [
                _transaction(current_user.id, transaction_type="income", amount_cents=4000, occurred_at=older),
            ]
        ]
    )

    response = _client(db, current_user).get(
        f"/imperium/vault/summary/monthly?occurred_to={occurred_to.isoformat().replace('+00:00', 'Z')}"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"] == [
        {
            "month": "2026-05",
            "total_income_cents": 4000,
            "total_expense_cents": 0,
            "net_cents": 4000,
            "transaction_count": 1,
            "income_count": 1,
            "expense_count": 0,
        }
    ]


def test_get_vault_monthly_summary_sorts_month_desc() -> None:
    current_user = _user()
    db = FakeDb(
        scalars_results=[
            [
                _transaction(
                    current_user.id,
                    transaction_type="income",
                    amount_cents=1100,
                    occurred_at=datetime(2026, 1, 10, 8, 0, tzinfo=UTC),
                ),
                _transaction(
                    current_user.id,
                    transaction_type="expense",
                    amount_cents=200,
                    occurred_at=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
                ),
                _transaction(
                    current_user.id,
                    transaction_type="income",
                    amount_cents=2500,
                    occurred_at=datetime(2026, 3, 1, 8, 0, tzinfo=UTC),
                ),
                _transaction(
                    current_user.id,
                    transaction_type="expense",
                    amount_cents=500,
                    occurred_at=datetime(2026, 2, 7, 8, 0, tzinfo=UTC),
                ),
            ]
        ]
    )

    response = _client(db, current_user).get("/imperium/vault/summary/monthly")

    assert response.status_code == 200
    assert [item["month"] for item in response.json()["items"]] == ["2026-03", "2026-02", "2026-01"]


def test_get_vault_monthly_summary_groups_by_occurred_at_utc_month() -> None:
    current_user = _user()
    db = FakeDb(
        scalars_results=[
            [
                _transaction(
                    current_user.id,
                    transaction_type="income",
                    amount_cents=8000,
                    occurred_at=datetime(2026, 2, 1, 4, 30, tzinfo=UTC),
                    local_date=datetime(2026, 1, 31, 23, 30).date(),
                    timezone="UTC-05:00",
                ),
            ]
        ]
    )

    response = _client(db, current_user).get("/imperium/vault/summary/monthly")

    assert response.status_code == 200
    assert response.json()["items"][0]["month"] == "2026-02"


def test_get_vault_monthly_summary_accepts_lowercase_currency_and_normalizes() -> None:
    current_user = _user()
    db = FakeDb(scalars_results=[[]])

    response = _client(db, current_user).get("/imperium/vault/summary/monthly?currency=usd")

    assert response.status_code == 200
    assert response.json()["currency"] == "USD"


def test_get_vault_monthly_summary_rejects_naive_occurred_from() -> None:
    response = _client(FakeDb(scalars_results=[[]]), _user()).get(
        "/imperium/vault/summary/monthly?occurred_from=2026-01-01T00:00:00"
    )

    assert response.status_code == 422


def test_get_vault_monthly_summary_does_not_require_idempotency_key() -> None:
    response = _client(FakeDb(scalars_results=[[]]), _user()).get("/imperium/vault/summary/monthly")

    assert response.status_code == 200
    assert response.json()["safe_explanation"] == "Vault monthly summary computed from current user's ledger transactions."


def test_get_vault_monthly_summary_is_read_only_and_has_no_ai_n8n_or_persistent_wallet_side_effects() -> None:
    current_user = _user()
    db = FakeDb(
        scalars_results=[
            [
                _transaction(
                    current_user.id,
                    transaction_type="income",
                    amount_cents=1000,
                    occurred_at=datetime(2026, 5, 2, 8, 0, tzinfo=UTC),
                ),
            ]
        ]
    )

    response = _client(db, current_user).get("/imperium/vault/summary/monthly")

    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False
    assert db.rolled_back is False

    route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_vault.py").read_text(encoding="utf-8")
    service_text = (BACKEND_ROOT / "app" / "services" / "imperium" / "vault.py").read_text(encoding="utf-8")
    schema_text = (BACKEND_ROOT / "app" / "schemas" / "imperium.py").read_text(encoding="utf-8")
    docs_text = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8")
    route_section = route_text.split('@router.get("/summary/monthly"', maxsplit=1)[1].split(
        '@router.get("/transactions"',
        maxsplit=1,
    )[0]
    schema_section = schema_text.split("class ImperiumVaultMonthlySummaryItem", maxsplit=1)[1].split(
        "class ImperiumVaultCategorySummaryItem",
        maxsplit=1,
    )[0]
    combined_code = "\n".join([route_text, service_text, schema_section]).lower()
    lowered_docs = docs_text.lower()

    assert "class ImperiumVaultMonthlySummaryItem" in schema_text
    assert "class ImperiumVaultMonthlySummaryResponse" in schema_text
    assert "safe_explanation: str = \"Vault monthly summary computed from current user's ledger transactions.\"" in schema_text
    assert "get_vault_monthly_summary(" in service_text
    assert "ImperiumVaultTransaction" in service_text
    assert "db.add(" not in service_text
    assert "db.flush" not in service_text
    assert "db.commit" not in service_text
    assert "Idempotency-Key" not in route_section
    assert "current_user: CurrentUserDep" in route_section
    assert "currency" in route_section
    assert "occurred_from" in route_section
    assert "occurred_to" in route_section
    assert "month" in schema_section
    assert "count" in schema_section
    assert "items" in schema_section
    assert "YYYY-MM" in docs_text
    assert "patch 9d" in lowered_docs
    assert "read-only" in lowered_docs
    assert "grouped by month" in lowered_docs
    assert "no ai/n8n/ocr/sadaqa/balance workflows" in lowered_docs
    assert "QwenClient" not in combined_code
    assert "n8n_client" not in combined_code
    assert "trigger_n8n" not in combined_code
    assert "pgvector" not in combined_code
    assert "embedding" not in combined_code
    assert "memory" not in combined_code
    assert "calendar" not in combined_code
    assert "ocr" not in combined_code
    assert "sadaqa" not in combined_code
    assert "wallet" not in combined_code
    assert "balance" not in combined_code
