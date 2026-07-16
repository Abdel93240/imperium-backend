from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.models.event import Event
from app.models.vault import ImperiumVaultTransaction, WeeklyFinanceSummary
from app.services.vault.weekly import DEFAULT_CATEGORY_MAP, build_weekly_summary_detail, compute_weekly_finance_summary


class FakeDb:
    def __init__(self, transactions):
        self.transactions = transactions
        self.summaries = {}
        self.added = []
        self.commits = 0

    def scalars(self, query):
        return list(self.transactions)

    def execute(self, query, params=None):
        class EmptyResult:
            def first(self):
                return None

            def one(self):
                return (None, None)

        return EmptyResult()

    def get(self, model, key):
        if model is WeeklyFinanceSummary:
            return self.summaries.get(key)
        return None

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()
        self.added.append(obj)
        if isinstance(obj, WeeklyFinanceSummary):
            self.summaries[obj.week_start] = obj

    def flush(self):
        pass

    def commit(self):
        self.commits += 1


def _transaction(**overrides):
    occurred_at = overrides.pop("occurred_at", datetime(2026, 7, 6, 10, 0, tzinfo=UTC))
    return ImperiumVaultTransaction(
        id=overrides.pop("id", uuid4()),
        user_id=overrides.pop("user_id", uuid4()),
        transaction_type=overrides.pop("transaction_type", "income"),
        amount_cents=overrides.pop("amount_cents", 10000),
        currency=overrides.pop("currency", "EUR"),
        wallet=overrides.pop("wallet", "cash"),
        occurred_at=occurred_at,
        local_date=overrides.pop("local_date", occurred_at.date()),
        timezone=overrides.pop("timezone", "UTC"),
        category=overrides.pop("category", "vtc"),
        source=overrides.pop("source", "manual"),
        note=None,
        external_ref=None,
        is_reversal=False,
        created_at=occurred_at,
        updated_at=occurred_at,
    )


def test_weekly_profit_aggregates_business_and_personal_categories() -> None:
    transactions = [
        _transaction(transaction_type="income", amount_cents=30000, category="vtc", wallet="cash"),
        _transaction(transaction_type="expense", amount_cents=7500, category="fuel", wallet="bank"),
        _transaction(transaction_type="expense", amount_cents=5000, category="loyer", wallet="bank"),
    ]

    summary = build_weekly_summary_detail(transactions, category_map=DEFAULT_CATEGORY_MAP)

    assert summary["business_revenue"] == summary["weekly_business_profit"] + summary["business_expenses"]
    assert str(summary["business_revenue"]) == "300.00"
    assert str(summary["business_expenses"]) == "75.00"
    assert str(summary["weekly_business_profit"]) == "225.00"
    assert str(summary["personal_expenses"]) == "50.00"
    assert summary["detail"]["by_category"]["fuel"]["business_expenses"] == "75.00"
    assert summary["detail"]["by_category"]["loyer"]["personal_expenses"] == "50.00"


def test_weekly_summary_upsert_is_idempotent_and_emits_event() -> None:
    user = SimpleNamespace(id=uuid4())
    week_start = date(2026, 7, 6)
    db = FakeDb([_transaction(user_id=user.id, amount_cents=10000, category="vtc")])

    first = compute_weekly_finance_summary(db, week_start=week_start, current_user=user)
    second = compute_weekly_finance_summary(db, week_start=week_start, current_user=user)

    assert first is second
    assert len(db.summaries) == 1
    assert str(second.weekly_business_profit) == "100.00"
    events = [item for item in db.added if isinstance(item, Event)]
    assert events
    assert all(event.event_type == "finance.weekly_summary.created" for event in events)


def test_empty_week_summary_returns_zeroes() -> None:
    summary = build_weekly_summary_detail([], category_map=DEFAULT_CATEGORY_MAP)

    assert str(summary["business_revenue"]) == "0.00"
    assert str(summary["business_expenses"]) == "0.00"
    assert str(summary["weekly_business_profit"]) == "0.00"
    assert str(summary["personal_expenses"]) == "0.00"
