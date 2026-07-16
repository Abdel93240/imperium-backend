"""Vector service skeleton. Business logic intentionally not implemented yet."""

from app.services.vector.scoring import (
    VECTOR_ABSTENTION_MESSAGE,
    VectorHourlyRateAggregationResult,
    VectorRideSample,
    aggregate_hourly_rate_estimate,
)

__all__ = [
    "VECTOR_ABSTENTION_MESSAGE",
    "VectorHourlyRateAggregationResult",
    "VectorRideSample",
    "aggregate_hourly_rate_estimate",
]
