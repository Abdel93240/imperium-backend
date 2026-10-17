"""Repas Pulse : conversion des unités du décompte (doc 40 §10.3) — sans base."""
from decimal import Decimal

import pytest

from app.services.pulse.meals import convert


@pytest.mark.parametrize(("quantity", "unit", "target", "expected"), [
    ("200", "g", "kg", Decimal("0.200")), ("1.5", "kg", "g", Decimal("1500.000")), ("33", "cl", "l", Decimal("0.330")),
    ("25", "cl", "ml", Decimal("250.000")), ("2", "piece", "piece", Decimal("2")), ("2", "g", "g", Decimal("2")),
])
def test_convertible_units(quantity, unit, target, expected) -> None:
    assert convert(Decimal(quantity), unit, target) == expected


@pytest.mark.parametrize(("unit", "target"), [("piece", "g"), ("l", "kg"), ("ml", "piece")])
def test_other_families_do_not_convert(unit, target) -> None:
    assert convert(Decimal("1"), unit, target) is None
