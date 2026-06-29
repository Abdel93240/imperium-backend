from dataclasses import dataclass
from decimal import Decimal
from collections.abc import Mapping, Sequence


VECTOR_ABSTENTION_MESSAGE = "Haute incertitude, à toi de juger."


@dataclass(frozen=True, slots=True)
class VectorRideSample:
    hourly_rate_estimate_eur_per_h: Decimal
    type2_context: Mapping[str, object | None]


@dataclass(frozen=True, slots=True)
class VectorHourlyRateAggregationResult:
    status: str
    hourly_rate_estimate_eur_per_h: Decimal | None
    sample_count: int
    missing_type2_variables: tuple[str, ...]
    message: str


def aggregate_hourly_rate_estimate(
    samples: Sequence[VectorRideSample],
    *,
    required_type2_variables: Sequence[str],
) -> VectorHourlyRateAggregationResult:
    required_variables = tuple(required_type2_variables)
    if not samples:
        return VectorHourlyRateAggregationResult(
            status="abstain",
            hourly_rate_estimate_eur_per_h=None,
            sample_count=0,
            missing_type2_variables=required_variables,
            message=VECTOR_ABSTENTION_MESSAGE,
        )

    missing_type2_variables = tuple(
        sorted(
            {
                variable_name
                for sample in samples
                for variable_name in required_variables
                if variable_name not in sample.type2_context or sample.type2_context[variable_name] is None
            }
        )
    )
    if missing_type2_variables:
        return VectorHourlyRateAggregationResult(
            status="abstain",
            hourly_rate_estimate_eur_per_h=None,
            sample_count=len(samples),
            missing_type2_variables=missing_type2_variables,
            message=VECTOR_ABSTENTION_MESSAGE,
        )

    total = sum((sample.hourly_rate_estimate_eur_per_h for sample in samples), start=Decimal("0"))
    average = total / Decimal(len(samples))
    return VectorHourlyRateAggregationResult(
        status="average",
        hourly_rate_estimate_eur_per_h=average,
        sample_count=len(samples),
        missing_type2_variables=(),
        message="Context complete; average computed from complete samples.",
    )
