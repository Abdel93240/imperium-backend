from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.models.vault import UpcomingExpense
from app.services.vault import upcoming as upcoming_service
from app.services.vault.upcoming import ensure_next_occurrence, next_due_date


class FakeDb:
    def __init__(self, *, scalars_results=None):
        self.existing = None
        self.scalars_results = [list(result) for result in scalars_results] if scalars_results is not None else []
        self.added = []
        self.queries = []

    def scalar(self, query):
        self.queries.append(query)
        return self.existing

    def scalars(self, query):
        self.queries.append(query)
        if self.scalars_results:
            return self.scalars_results.pop(0)
        return []

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()
        self.added.append(obj)
        self.existing = obj

    def flush(self):
        pass


def _expense(**overrides):
    return UpcomingExpense(
        id=uuid4(),
        user_id=overrides.pop("user_id", uuid4()),
        label_fr=overrides.pop("label_fr", "Loyer"),
        amount=overrides.pop("amount", Decimal("900.00")),
        due_date=overrides.pop("due_date", date(2026, 1, 31)),
        recurrence=overrides.pop("recurrence", "monthly"),
        category=overrides.pop("category", "loyer"),
        wallet=overrides.pop("wallet", "bank"),
        mandatory=overrides.pop("mandatory", True),
        active=overrides.pop("active", True),
    )


def test_next_due_date_handles_monthly_quarterly_yearly_calendar_edges() -> None:
    assert next_due_date(date(2026, 1, 31), "monthly") == date(2026, 2, 28)
    assert next_due_date(date(2026, 1, 31), "quarterly") == date(2026, 4, 30)
    assert next_due_date(date(2024, 2, 29), "yearly") == date(2025, 2, 28)
    assert next_due_date(date(2026, 1, 31), None) is None


def test_ensure_next_occurrence_does_not_duplicate_existing_generated_expense() -> None:
    db = FakeDb()
    expense = _expense()

    first = ensure_next_occurrence(db, expense=expense)
    second = ensure_next_occurrence(db, expense=expense)

    assert first is second
    assert len(db.added) == 1
    assert first.due_date == date(2026, 2, 28)


def test_upcoming_expenses_crud_is_user_scoped() -> None:
    user = SimpleNamespace(id=uuid4())
    db = FakeDb(scalars_results=[[]])

    listed = upcoming_service.list_upcoming_expenses(db, current_user=user)

    assert listed == []
    assert "upcoming_expenses.user_id" in str(db.queries[0])


def test_expenses_horizon_job_generates_overdue_recurring_occurrence(monkeypatch) -> None:
    def no_notify(*args, **kwargs):
        raise AssertionError("overdue recurring generation must not notify outside J-7/J-1")

    monkeypatch.setattr(upcoming_service, "notify", no_notify)
    user = SimpleNamespace(id=uuid4())
    monkeypatch.setattr(upcoming_service, "_job_user", lambda _db: user)
    db = FakeDb()
    expired = _expense(user_id=user.id, due_date=date(2026, 6, 30), recurrence="monthly")

    scalars_results = [[expired], []]

    def scalars(query):
        return scalars_results.pop(0)

    db.scalars = scalars
    ctx = SimpleNamespace(db=db, items_in=None, items_out=None, detail=None, cursor_ts=None)
    window = SimpleNamespace(to_ts=datetime(2026, 7, 16, 6, 0, tzinfo=UTC))

    upcoming_service.expenses_horizon_job(ctx, window)

    assert len(db.added) == 1
    assert db.added[0].user_id == user.id
    assert db.added[0].due_date == date(2026, 7, 30)
    assert ctx.detail == {"notifications": 0, "generated_occurrences": 1}
