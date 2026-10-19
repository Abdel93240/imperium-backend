"""Règles de canonicité et vocabulaire des context_predicate de W3 (spec WR §6.1, §13.4, §13.5)."""
from __future__ import annotations

import pytest

from app.services.wr.learning import PLANNED_EFFECTS, PREDICATE_FIELDS, canonical_errors, validate_predicate


@pytest.mark.parametrize(("statement", "expected"), [
    ("Les sessions VTC démarrées après 21h le samedi ont un €/h supérieur de 15-25%.", []),
    ("", ["empty"]),
    ("x" * 241, ["too_long"]),
    ("Les sessions du samedi rapportent-elles plus ?", ["not_declarative"]),
    ("Il rapporte plus le samedi.", ["dangling_pronoun"]),
    ("C'est plus rentable le samedi.", ["dangling_pronoun"]),
    ("Le samedi rapporte plus depuis récemment.", ["relative_date:récemment"]),
    ("Les missions d'hier ont glissé.", ["relative_date:hier"]),
    ("Le samedi rapporte plus. Le dimanche rapporte moins.", ["multiple_statements"]),
    ("Le samedi rapporte plus ; le dimanche moins.", ["multiple_statements"]),
])
def test_canonical_rules(statement: str, expected: list[str]) -> None:
    assert canonical_errors(statement) == expected


def test_relative_date_needs_a_whole_word() -> None:
    assert canonical_errors("Le cahier des missions reste à jour.") == []  # « hier » dans « cahier »


def test_predicates_are_checked_against_the_rollup_vocabulary() -> None:
    good = {"all": [{"field": "day.day_of_week", "op": "in", "value": ["saturday", "sunday"]},
                    {"field": "rides.worked_minutes", "op": ">=", "value": 120}]}
    assert validate_predicate(good) == good
    assert validate_predicate({"any": [{"field": "day.is_weekend", "op": "=", "value": True}]}) is not None
    for bad in (
        None, [], {"all": []}, {"all": [], "any": []}, {"none": [{"field": "day.is_weekend", "op": "=", "value": True}]},
        {"all": [{"field": "session.start_hour", "op": ">=", "value": 21}]},  # hors vocabulaire
        {"all": [{"field": "rides.worked_minutes", "op": "~", "value": 1}]},
        {"all": [{"field": "rides.worked_minutes", "op": ">", "value": "beaucoup"}]},
        {"all": [{"field": "rides.worked_minutes", "op": ">", "value": True}]},
        {"all": [{"field": "day.day_of_week", "op": ">", "value": "monday"}]},
        {"all": [{"field": "day.day_of_week", "op": "=", "value": "samedi"}]},
        {"all": [{"field": "day.is_weekend", "op": "<", "value": True}]},
        {"all": [{"field": "day.day_of_week", "op": "in", "value": []}]},
        {"all": [{"field": "day.is_weekend", "op": "=", "value": True, "extra": 1}]},
    ):
        assert validate_predicate(bad) is None, bad
    assert "finance.pressure_score" in PREDICATE_FIELDS and "missions.overdue_open_at_day_end" in PREDICATE_FIELDS


def test_planned_effects_follow_the_spec() -> None:
    assert PLANNED_EFFECTS == {"duplicate": "increment", "reinforces": "increment", "refines": "refine_link",
                               "contradicts": "docket_contradiction", "unrelated": "new_pattern"}
