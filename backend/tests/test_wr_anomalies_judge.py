"""W4 : jugement d'une valeur contre sa baseline médiane ± MAD (spec WR §4 W4) — sans base."""
from __future__ import annotations

import pytest

from app.services.wr.anomalies import band_at_least, judge

BANDS = {"method": "median_mad", "yellow": 2, "orange": 3, "red": 4, "min_history_days": 14,
         "direction": "high", "min_scale": 1}


def test_insufficient_history_gives_no_verdict() -> None:
    assert judge(5, [1.0] * 13, BANDS) is None


def test_bands_follow_the_worrying_direction() -> None:
    history = [10.0, 12.0] * 7  # médiane 11, MAD 1 → échelle 1,4826
    assert judge(11, history, BANDS).band == "green"
    assert judge(14, history, BANDS).band == "yellow"  # z ≈ 2,02
    assert judge(16, history, BANDS).band == "orange"  # z ≈ 3,37
    assert judge(20, history, BANDS).band == "red"
    assert judge(0, history, BANDS).band == "green"  # baisse : sens « high » seulement
    assert judge(0, history, {**BANDS, "direction": "low"}).band == "red"
    assert judge(0, history, {**BANDS, "direction": "both"}).band == "red"
    verdict = judge(16, history, BANDS)
    assert (verdict.baseline, verdict.scale, verdict.z) == (11, pytest.approx(1.4826), pytest.approx(3.37, abs=0.01))


def test_flat_history_uses_the_scale_floor() -> None:
    flat = [0.0] * 20  # MAD 0 : sans plancher, une seule mission ratée serait « rouge »
    assert judge(1, flat, BANDS).band == "green"
    assert judge(3, flat, BANDS).band == "orange"


def test_band_order() -> None:
    assert band_at_least("red", "orange") and band_at_least("orange", "orange")
    assert not band_at_least("yellow", "orange") and not band_at_least(None, "yellow")
