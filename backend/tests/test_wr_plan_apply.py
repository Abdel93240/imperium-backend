"""Applicateur de deltas du plan (spec WR §8.2, §14 verrou 9) : tout ou rien, rejet motivé."""
from __future__ import annotations

import pytest

from app.services.wr.plan import PlanDeltaRejectedError, apply_operations, horizon_weeks

PLAN = {"items": [{"ref": "mission:a", "title_fr": "A", "week": 1, "params": {}},
                  {"ref": "objective:b", "title_fr": "B", "week": 2, "params": {"cible": 3}}],
        "invariants_fr": ["B ne bouge pas"]}


def test_operations_apply_in_order_on_a_copy() -> None:
    result = apply_operations(PLAN, [
        {"op": "move", "target_ref": "mission:a", "params": {"to_week": 3}, "reason_fr": "surcharge"},
        {"op": "add", "target_ref": "mission:c", "params": {"title_fr": "C", "week": 4}},
        {"op": "modify", "target_ref": "objective:b", "params": {"title_fr": "B bis"}},
        {"op": "remove", "target_ref": "mission:c"},
    ], weeks=4)
    assert [(item["ref"], item["title_fr"], item["week"]) for item in result["items"]] == [
        ("mission:a", "A", 3), ("objective:b", "B bis", 2)]
    assert result["invariants_fr"] == ["B ne bouge pas"]
    assert PLAN["items"][0]["week"] == 1  # l'original n'est pas touché


def test_one_bad_operation_rejects_the_whole_delta_with_reasons() -> None:
    with pytest.raises(PlanDeltaRejectedError) as rejected:
        apply_operations(PLAN, [
            {"op": "move", "target_ref": "mission:a", "params": {"to_week": 2}},
            {"op": "move", "target_ref": "mission:zzz", "params": {"to_week": 2}},
            {"op": "move", "target_ref": "mission:a", "params": {"to_week": 5}},
            {"op": "add", "target_ref": "objective:b", "params": {"title_fr": "dup", "week": 1}},
            {"op": "add", "target_ref": "mission:d", "params": {"title_fr": "D", "week": 9}},
            {"op": "modify", "target_ref": "mission:a", "params": {"week": 2}},
            {"op": "rename", "target_ref": "mission:a"},
        ], weeks=4)
    reasons = rejected.value.reasons
    assert len(reasons) == 6 and reasons[0].startswith("op 2 move : mission:zzz absent")
    assert any("hors horizon" in reason for reason in reasons)
    assert any("non modifiables ['week']" in reason for reason in reasons)


def test_remove_then_touch_is_rejected_and_weeks_round_up() -> None:
    with pytest.raises(PlanDeltaRejectedError):
        apply_operations(PLAN, [{"op": "remove", "target_ref": "mission:a"},
                                {"op": "modify", "target_ref": "mission:a", "params": {"title_fr": "x"}}], weeks=4)
    from datetime import date
    assert (horizon_weeks(date(2026, 10, 19), date(2026, 11, 15)), horizon_weeks(date(2026, 10, 19), date(2026, 11, 16))) == (4, 5)
