"""Verrou de parité (spec Daily §4.4, carte ACT-DLY-01) : barèmes externalisés = scores d'avant, à l'identique.

`fixtures/df_golden_scores.json` a été capturé sur le service AVANT l'externalisation (83 cas couvrant
chaque tranche de chaque critère et les 10 buckets) : explication, breakdown, bucket, statut.
"""
import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.schemas.imperium import DecisionFrameworkScorePreviewRequest
from app.services.imperium import decision_framework as df
from df_golden_cases import CASES

GOLDEN = json.loads((Path(__file__).parent / "fixtures" / "df_golden_scores.json").read_text())
ROUND_TRIP = df.scales_from_parameter_values(df.scale_parameter_values())


def _materialize(case: dict) -> dict:
    data = {key: value for key, value in case.items() if key != "deadline_days"}
    if case.get("deadline_days") is not None:
        data["deadline_at"] = (datetime.now(UTC) + timedelta(days=case["deadline_days"])).date()
    return data


def _scores(case: dict, scales) -> dict:
    data = _materialize(case)
    entry = {"explain": df.explain_score(data, scales=scales).model_dump(mode="json")}
    fields = {key: value for key, value in data.items() if key in DecisionFrameworkScorePreviewRequest.model_fields}
    try:
        preview = df.preview_decision_framework_score(DecisionFrameworkScorePreviewRequest(**fields), scales=scales)
        entry["preview"] = preview.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001 - le golden fige aussi les refus
        entry["preview_error"] = type(exc).__name__
    return entry


def test_golden_suite_covers_every_band() -> None:
    assert len(CASES) == len(GOLDEN) >= 40
    assert {entry["preview"]["priority_bucket"] for entry in GOLDEN if "preview" in entry} == set(range(1, 11))
    assert {entry["explain"]["deadline_points"] for entry in GOLDEN} == {0, 5, 10, 15, 20, 25, 30}


@pytest.mark.parametrize("scales", [df.CODE_SCALES, ROUND_TRIP], ids=["code", "parameters"])
def test_scores_are_strictly_identical(scales) -> None:
    for index, case in enumerate(CASES):
        assert _scores(case, scales) == GOLDEN[index], f"case {index}: {case}"


def test_weighted_scores_and_coefficients_unchanged() -> None:
    for scales in (df.CODE_SCALES, ROUND_TRIP):
        assert [df.get_domain_coefficient(position, scales) for position in (1, 2, 3, 4)] == [10, 8, 5, 4]
        for entry in GOLDEN:
            intrinsic = entry["explain"]["final_intrinsic_score"]
            assert [df.compute_weighted_score(intrinsic, df.get_domain_coefficient(p, scales)) for p in (1, 2, 3, 4)] == [
                intrinsic * 10, intrinsic * 8, intrinsic * 5, intrinsic * 4]


def test_migration_seeds_exactly_the_code_scales() -> None:
    path = Path(__file__).parents[1] / "alembic" / "versions" / "20261019_0101_df_scales_parameters.py"
    spec = importlib.util.spec_from_file_location("df_seed_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert {code: value for code, (value, _) in module.PARAMETERS.items()} == df.scale_parameter_values()
    assert set(module.PARAMETERS) == set(df.SCALE_PARAMETERS)


@pytest.mark.parametrize("code, value", [
    ("df.criterion_max", {"deadline": 60, "impact": 30, "mission_type": 20, "dependency": 10, "recurrence": 10}),
    ("df.impact_points", {"critical": 31}),
    ("df.impact_points", {}),
    ("df.deadline_points", {"overdue_or_today": 30, "bands": [[6, 20], [2, 25]], "beyond": 5}),
    ("df.coefficient_by_position", {"1": 10, "2": 8, "3": 5}),
    ("df.coefficient_by_position", {"1": 10, "2": 8, "3": 5, "4": True}),
    ("df.priority_buckets", {"thresholds": [[20, 2], [700, 10]], "floor": 1}),
    ("df.dependency_points", {"labels": {"none": 0}}),
])
def test_malformed_scales_are_rejected(code, value) -> None:
    values = df.scale_parameter_values()
    values[code] = value
    with pytest.raises(ValueError):
        df.scales_from_parameter_values(values)
