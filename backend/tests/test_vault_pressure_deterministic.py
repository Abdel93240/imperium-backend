from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.vault import ImperiumVaultTransaction, UpcomingExpense
from app.services.vault import pressure as pressure_service
from app.services.vault.pressure import PressureInputs, compute_pressure, load_pressure_inputs


class FakeDb:
    def __init__(self, *, scalars_results) -> None:
        self.scalars_results = [list(result) for result in scalars_results]
        self.queries = []

    def scalars(self, query):
        self.queries.append(query)
        if self.scalars_results:
            return self.scalars_results.pop(0)
        return []


GOLDENS = [
    (
        "safe",
        PressureInputs(
            current_week_income=Decimal("650"),
            expected_week_income=Decimal("800"),
            fixed_weekly_charges=Decimal("300"),
            upcoming_required_expenses=Decimal("100"),
            overdue_expenses=Decimal("0"),
            available_liquidity=Decimal("700"),
            fuel_required_next_days=Decimal("60"),
            conditional_required_expenses=Decimal("0"),
            exceptional_required_expenses=Decimal("0"),
            urgent_fixed_charges_due_within_3_days=Decimal("0"),
            minimum_survival_threshold=Decimal("150"),
            number_of_remaining_work_days=3,
            realistic_daily_capacity=Decimal("220"),
        ),
        0,
        {"minimum": Decimal("0.00"), "comfortable": Decimal("0.00"), "optimal": Decimal("0.00")},
    ),
    (
        "stable",
        PressureInputs(
            current_week_income=Decimal("450"),
            expected_week_income=Decimal("800"),
            fixed_weekly_charges=Decimal("300"),
            upcoming_required_expenses=Decimal("150"),
            overdue_expenses=Decimal("0"),
            available_liquidity=Decimal("352"),
            fuel_required_next_days=Decimal("100"),
            conditional_required_expenses=Decimal("0"),
            exceptional_required_expenses=Decimal("0"),
            urgent_fixed_charges_due_within_3_days=Decimal("0"),
            minimum_survival_threshold=Decimal("150"),
            number_of_remaining_work_days=3,
            realistic_daily_capacity=Decimal("220"),
        ),
        30,
        {"minimum": Decimal("66.00"), "comfortable": Decimal("89.10"), "optimal": Decimal("115.50")},
    ),
    (
        "attention",
        PressureInputs(
            current_week_income=Decimal("500"),
            expected_week_income=Decimal("850"),
            fixed_weekly_charges=Decimal("300"),
            upcoming_required_expenses=Decimal("230"),
            overdue_expenses=Decimal("0"),
            available_liquidity=Decimal("300"),
            fuel_required_next_days=Decimal("100"),
            conditional_required_expenses=Decimal("0"),
            exceptional_required_expenses=Decimal("0"),
            urgent_fixed_charges_due_within_3_days=Decimal("0"),
            minimum_survival_threshold=Decimal("150"),
            number_of_remaining_work_days=3,
            realistic_daily_capacity=Decimal("200"),
        ),
        55,
        {"minimum": Decimal("110.00"), "comfortable": Decimal("148.50"), "optimal": Decimal("192.50")},
    ),
    (
        "pressure",
        PressureInputs(
            current_week_income=Decimal("420"),
            expected_week_income=Decimal("760"),
            fixed_weekly_charges=Decimal("300"),
            upcoming_required_expenses=Decimal("160"),
            overdue_expenses=Decimal("50"),
            available_liquidity=Decimal("200"),
            fuel_required_next_days=Decimal("80"),
            conditional_required_expenses=Decimal("0"),
            exceptional_required_expenses=Decimal("0"),
            urgent_fixed_charges_due_within_3_days=Decimal("0"),
            minimum_survival_threshold=Decimal("150"),
            number_of_remaining_work_days=3,
            realistic_daily_capacity=Decimal("200"),
        ),
        75,
        {"minimum": Decimal("130.00"), "comfortable": Decimal("175.50"), "optimal": Decimal("227.50")},
    ),
    (
        "critical",
        PressureInputs(
            current_week_income=Decimal("300"),
            expected_week_income=Decimal("720"),
            fixed_weekly_charges=Decimal("200"),
            upcoming_required_expenses=Decimal("110"),
            overdue_expenses=Decimal("0"),
            available_liquidity=Decimal("100"),
            fuel_required_next_days=Decimal("50"),
            conditional_required_expenses=Decimal("100"),
            exceptional_required_expenses=Decimal("100"),
            urgent_fixed_charges_due_within_3_days=Decimal("150"),
            minimum_survival_threshold=Decimal("150"),
            number_of_remaining_work_days=3,
            realistic_daily_capacity=Decimal("200"),
        ),
        85,
        {"minimum": Decimal("120.00"), "comfortable": Decimal("162.00"), "optimal": Decimal("210.00")},
    ),
]


@pytest.mark.parametrize(("expected_label", "inputs", "expected_score", "expected_targets"), GOLDENS)
def test_pressure_golden_examples_are_exact(expected_label, inputs, expected_score, expected_targets) -> None:
    result = compute_pressure(inputs)

    assert result.score == expected_score
    assert result.label == expected_label
    assert result.daily_targets == expected_targets


def test_pressure_monotonicity_for_required_expense_and_confirmed_income() -> None:
    base = PressureInputs(
        fixed_weekly_charges=Decimal("300"),
        upcoming_required_expenses=Decimal("150"),
        available_liquidity=Decimal("352"),
        fuel_required_next_days=Decimal("100"),
        number_of_remaining_work_days=3,
        realistic_daily_capacity=Decimal("220"),
    )

    with_added_mandatory_expense = PressureInputs(
        **{**base.__dict__, "upcoming_required_expenses": Decimal("250")}
    )
    with_confirmed_income = PressureInputs(
        **{**base.__dict__, "available_liquidity": Decimal("452")}
    )

    assert compute_pressure(with_added_mandatory_expense).score >= compute_pressure(base).score
    assert compute_pressure(with_confirmed_income).score <= compute_pressure(base).score


def test_load_pressure_inputs_uses_doc11_weekly_buckets(monkeypatch) -> None:
    current_user = SimpleNamespace(id=uuid4())
    now = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    today = date(2026, 7, 16)
    transactions = [
        _transaction(current_user.id, amount_cents=30000, wallet="cash", occurred_at=now),
        _transaction(
            current_user.id,
            transaction_type="expense",
            amount_cents=5000,
            wallet="bank",
            occurred_at=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
        ),
        _transaction(
            current_user.id,
            amount_cents=90000,
            wallet="cash",
            occurred_at=datetime(2026, 7, 18, 12, 0, tzinfo=UTC),
            local_date=date(2026, 7, 18),
        ),
    ]
    expenses = [
        _expense(amount=Decimal("20.00"), due_date=date(2026, 7, 15), category="other"),
        _expense(amount=Decimal("30.00"), due_date=today, category="charges"),
        _expense(amount=Decimal("70.00"), due_date=date(2026, 7, 17), category="fuel"),
        _expense(amount=Decimal("180.00"), due_date=date(2026, 7, 18), category="school", recurrence="monthly"),
        _expense(amount=Decimal("120.00"), due_date=date(2026, 7, 19), category="maintenance"),
        _expense(amount=Decimal("40.00"), due_date=date(2026, 7, 19), category="other"),
        _expense(amount=Decimal("999.00"), due_date=date(2026, 7, 20), category="other"),
    ]
    db = FakeDb(scalars_results=[transactions, expenses])

    monkeypatch.setattr(pressure_service, "get_parameter", lambda *_args, default=None: default)
    monkeypatch.setattr(pressure_service, "_recent_daily_capacity", lambda *_args, **_kwargs: Decimal("220.00"))

    inputs = load_pressure_inputs(db, current_user=current_user, today=today, now=now)

    assert inputs.current_week_income == Decimal("300.00")
    assert inputs.expected_week_income == Decimal("300.00")
    assert inputs.available_liquidity == Decimal("250.00")
    assert inputs.fixed_weekly_charges == Decimal("30.00")
    assert inputs.upcoming_required_expenses == Decimal("40.00")
    assert inputs.overdue_expenses == Decimal("20.00")
    assert inputs.fuel_required_next_days == Decimal("70.00")
    assert inputs.conditional_required_expenses == Decimal("180.00")
    assert inputs.exceptional_required_expenses == Decimal("120.00")
    assert inputs.urgent_fixed_charges_due_within_3_days == Decimal("440.00")
    assert inputs.number_of_remaining_work_days == 4
    assert inputs.realistic_daily_capacity == Decimal("220.00")


def test_daily_modules_do_not_import_vault_pressure() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "services" / "imperium"
    for path in (root / "daily_plan.py", root / "daily_plans.py"):
        text = path.read_text(encoding="utf-8")
        assert "services.vault.pressure" not in text
        assert "vault.pressure" not in text


def _transaction(user_id, **overrides) -> ImperiumVaultTransaction:
    occurred_at = overrides.pop("occurred_at", datetime(2026, 7, 16, 10, 0, tzinfo=UTC))
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


def _expense(**overrides) -> UpcomingExpense:
    return UpcomingExpense(
        id=overrides.pop("id", uuid4()),
        user_id=overrides.pop("user_id", uuid4()),
        label_fr=overrides.pop("label_fr", "Expense"),
        amount=overrides.pop("amount", Decimal("10.00")),
        due_date=overrides.pop("due_date", date(2026, 7, 16)),
        recurrence=overrides.pop("recurrence", None),
        category=overrides.pop("category", "other"),
        wallet=overrides.pop("wallet", "bank"),
        mandatory=overrides.pop("mandatory", True),
        active=overrides.pop("active", True),
    )
