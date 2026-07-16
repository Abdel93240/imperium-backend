from decimal import Decimal
from pathlib import Path

import pytest

from app.services.vault.pressure import PressureInputs, compute_pressure


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


def test_daily_modules_do_not_import_vault_pressure() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "services" / "imperium"
    for path in (root / "daily_plan.py", root / "daily_plans.py"):
        text = path.read_text(encoding="utf-8")
        assert "services.vault.pressure" not in text
        assert "vault.pressure" not in text
