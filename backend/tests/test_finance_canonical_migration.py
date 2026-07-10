from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import vault
from app.models.event import Event
from app.models.idempotency import IdempotencyKey
from app.models.vault import ImperiumVaultTransaction
from app.services.imperium.dashboard import get_dashboard_snapshot
from app.services.imperium.weekly_report import get_weekly_report


class FakeDb:
    def __init__(self, *, scalar_results=None, scalars_results=None) -> None:
        self.scalar_results = list(scalar_results or [])
        self.scalars_results = [list(result) for result in scalars_results] if scalars_results is not None else []
        self.added = []
        self.queries = []
        self.flushed = False
        self.committed = False
        self.rolled_back = False

    def add(self, obj) -> None:
        self._prepare(obj)
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed = True
        for item in self.added:
            self._prepare(item)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def scalar(self, query):
        self.queries.append(query)
        if self.scalar_results:
            return self.scalar_results.pop(0)
        return None

    def scalars(self, query):
        self.queries.append(query)
        if self.scalars_results:
            return self.scalars_results.pop(0)
        return []

    def _prepare(self, obj) -> None:
        now = datetime.now(UTC)
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()
        if hasattr(obj, "created_at") and getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if hasattr(obj, "updated_at") and getattr(obj, "updated_at", None) is None:
            obj.updated_at = now
        if isinstance(obj, Event) and getattr(obj, "received_at", None) is None:
            obj.received_at = now


def _user(user_id=None) -> SimpleNamespace:
    return SimpleNamespace(id=user_id or uuid4(), timezone="UTC")


def _legacy_vault_client(db: FakeDb, current_user: SimpleNamespace) -> TestClient:
    app = FastAPI()
    app.include_router(vault.router, prefix="/vault")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _transaction(user_id, **overrides) -> ImperiumVaultTransaction:
    occurred_at = overrides.pop("occurred_at", datetime(2026, 7, 6, 10, 0, tzinfo=UTC))
    return ImperiumVaultTransaction(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        transaction_type=overrides.pop("transaction_type", "income"),
        amount_cents=overrides.pop("amount_cents", 10000),
        currency=overrides.pop("currency", "EUR"),
        wallet=overrides.pop("wallet", "cash"),
        occurred_at=occurred_at,
        local_date=overrides.pop("local_date", occurred_at.date()),
        timezone=overrides.pop("timezone", "UTC"),
        category=overrides.pop("category", "vtc"),
        source=overrides.pop("source", "manual"),
        note=overrides.pop("note", None),
        external_ref=overrides.pop("external_ref", None),
        is_reversal=overrides.pop("is_reversal", False),
        reversal_of_transaction_id=overrides.pop("reversal_of_transaction_id", None),
        reversal_reason=overrides.pop("reversal_reason", None),
        created_at=overrides.pop("created_at", occurred_at),
        updated_at=overrides.pop("updated_at", occurred_at),
    )


def test_legacy_vault_create_writes_canonical_transaction_in_cents_and_keeps_event() -> None:
    current_user = _user()
    db = FakeDb()

    response = _legacy_vault_client(db, current_user).post(
        "/vault/transactions",
        headers={"Idempotency-Key": "legacy-vault-income-1"},
        json={
            "occurred_at": "2026-07-06T10:00:00Z",
            "local_date": "2026-07-06",
            "timezone": "UTC",
            "transaction_type": "income",
            "wallet": "revolut_business",
            "category": "vtc",
            "label": "Bolt morning",
            "amount": "123.45",
            "currency": "eur",
            "notes": "gross revenue",
        },
    )

    assert response.status_code == 201
    body = response.json()
    transaction = next(item for item in db.added if isinstance(item, ImperiumVaultTransaction))
    event = next(item for item in db.added if isinstance(item, Event))
    assert transaction.amount_cents == 12345
    assert transaction.wallet == "revolut_business"
    assert transaction.transaction_type == "income"
    assert transaction.source == "vault"
    assert transaction.note == "gross revenue"
    assert transaction.is_reversal is False
    assert body["transaction"]["amount"] == "123.45"
    assert body["transaction"]["wallet"] == "revolut_business"
    assert body["transaction"]["is_reversal"] is False
    assert event.event_type == "vault.transaction.created"
    assert event.payload["transaction_id"] == str(transaction.id)
    assert any(isinstance(item, IdempotencyKey) for item in db.added)
    assert db.committed is True


def test_dashboard_vault_week_uses_canonical_cents_and_exposes_reversals() -> None:
    current_user = _user()
    original_income = _transaction(current_user.id, transaction_type="income", amount_cents=20000)
    fuel_expense = _transaction(
        current_user.id,
        transaction_type="expense",
        amount_cents=5000,
        wallet="bank",
    )
    reversal = _transaction(
        current_user.id,
        transaction_type="expense",
        amount_cents=20000,
        is_reversal=True,
        reversal_of_transaction_id=original_income.id,
        reversal_reason="duplicate",
    )
    db = FakeDb(
        scalar_results=[None, None, None, None],
        scalars_results=[[], [], [original_income, fuel_expense, reversal], []],
    )

    snapshot = get_dashboard_snapshot(db, current_user=current_user)

    assert snapshot.vault_week.income_total == Decimal("200.00")
    assert snapshot.vault_week.expense_total == Decimal("250.00")
    assert snapshot.vault_week.net_total == Decimal("-50.00")
    assert snapshot.vault_week.reversal_total == Decimal("200.00")
    assert snapshot.vault_week.reversal_count == 1
    assert snapshot.vault_week.transaction_count == 3
    assert "imperium_vault_transactions.user_id" in "\n".join(str(query) for query in db.queries)


def test_legacy_vault_weekly_summary_uses_canonical_cents_wallets_and_reversals() -> None:
    current_user = _user()
    original_income = _transaction(
        current_user.id,
        transaction_type="income",
        amount_cents=15000,
        wallet="cash",
        category="vtc",
    )
    fuel_expense = _transaction(
        current_user.id,
        transaction_type="expense",
        amount_cents=2500,
        wallet="bank",
        category="fuel",
    )
    reversal = _transaction(
        current_user.id,
        transaction_type="expense",
        amount_cents=15000,
        wallet="cash",
        category="vtc",
        is_reversal=True,
        reversal_of_transaction_id=original_income.id,
        reversal_reason="duplicate",
    )
    db = FakeDb(scalars_results=[[original_income, fuel_expense, reversal]])

    response = _legacy_vault_client(db, current_user).get("/vault/summary/week?week_start=2026-07-06")

    assert response.status_code == 200
    body = response.json()
    assert body["income_total"] == "150.00"
    assert body["expense_total"] == "175.00"
    assert body["net_total"] == "-25.00"
    assert body["reversal_total"] == "150.00"
    assert body["reversal_count"] == 1
    assert body["by_wallet"]["cash"]["reversal_total"] == "150.00"
    assert body["by_wallet"]["cash"]["reversal_count"] == 1
    assert body["by_category"]["vtc"]["reversal_total"] == "150.00"
    assert "imperium_vault_transactions.user_id" in "\n".join(str(query) for query in db.queries)


def test_weekly_report_finance_uses_canonical_wallets_and_exposes_reversals() -> None:
    current_user = _user()
    week_start = date(2026, 7, 6)
    original_income = _transaction(
        current_user.id,
        transaction_type="income",
        amount_cents=30000,
        wallet="cash",
        category="vtc",
    )
    fuel_expense = _transaction(
        current_user.id,
        transaction_type="expense",
        amount_cents=7500,
        wallet="bank",
        category="fuel",
    )
    reversal = _transaction(
        current_user.id,
        transaction_type="expense",
        amount_cents=30000,
        wallet="cash",
        category="vtc",
        is_reversal=True,
        reversal_of_transaction_id=original_income.id,
        reversal_reason="duplicate",
    )
    db = FakeDb(
        scalars_results=[[], [], [], [], [original_income, fuel_expense, reversal], []],
    )

    report = get_weekly_report(db, current_user=current_user, week_start=week_start)

    assert report.vault.income_total == "300.00"
    assert report.vault.expense_total == "375.00"
    assert report.vault.net_total == "-75.00"
    assert report.vault.reversal_total == "300.00"
    assert report.vault.reversal_count == 1
    by_wallet = {item.wallet: item for item in report.vault.by_wallet}
    assert by_wallet["cash"].income_total == "300.00"
    assert by_wallet["cash"].expense_total == "300.00"
    assert by_wallet["cash"].reversal_total == "300.00"
    assert by_wallet["cash"].reversal_count == 1
    by_category = {item.category: item for item in report.vault.by_category}
    assert by_category["vtc"].reversal_total == "300.00"
    assert by_category["vtc"].reversal_count == 1
    assert "imperium_vault_transactions.user_id" in "\n".join(str(query) for query in db.queries)
