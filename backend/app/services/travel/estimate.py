"""toolbox.travel v0 — graved interface, provisional engine (spec socle §7).

Engine v0: Google Directions provider + HARD ×1.3 floor (coded, applied even if
a parameter tries lower) + (origin H3, dest H3, hour slot) cache with 2 h TTL +
offline fallback distance_km / 25 km/h × 1.3 marked provider='local_fallback'.

privacy_tier (Q2 GRAVED): 'very_high' (any call coming from The Path) is coded
so it can NEVER reach an external provider — v0 serves it exclusively from the
local fallback. Lock-test: a network spy sees ZERO outbound request for a
very_high call. The Vector pass will refine the local engine (H3 matrix)
without changing this signature.
"""

import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.toolbox import TravelCacheEntry
from app.services.params import get_parameter
from app.services.travel.geo import DEFAULT_H3_RES, LatLng, h3_cell, haversine_m, time_slot

logger = logging.getLogger(__name__)

# Hard floor, coded (doubled as parameter toolbox.travel_floor; the CODE wins
# when a parameter tries to go below — graved rule).
TRAVEL_FLOOR = 1.3
FALLBACK_SPEED_KMH_DEFAULT = 25.0
CACHE_TTL_MIN_DEFAULT = 120

PrivacyTier = Literal["normal", "sensitive", "very_high"]
Profile = Literal["planning", "realtime"]


@dataclass(frozen=True)
class TravelEstimate:
    duration_s: int
    distance_m: int
    provider: str
    multiplier_applied: float
    cached: bool
    computed_at: datetime


class TravelProviderError(RuntimeError):
    pass


def estimate(
    origin: LatLng,
    dest: LatLng,
    at: datetime,
    privacy_tier: PrivacyTier = "normal",
    profile: Profile = "planning",
    *,
    db: Session | None = None,
) -> TravelEstimate:
    """Graved signature (spec socle §7) — Vector strengthens, never changes it."""
    floor = _effective_floor(db)

    # Q2 graved: very_high NEVER reaches an external provider. No cache either:
    # the cache would leak the visited cells into a shared table keyed for
    # provider results; the local fallback is cheap enough to recompute.
    if privacy_tier == "very_high":
        return _local_fallback(origin, dest, floor, db)

    if db is not None:
        cached = _cache_lookup(db, origin, dest, at, profile)
        if cached is not None:
            return cached

    try:
        duration_s, distance_m = _google_directions(origin, dest, at)
        provider = "google_directions"
    except TravelProviderError as exc:
        logger.info("Travel provider unavailable, using local fallback.", extra={"error": str(exc)})
        return _local_fallback(origin, dest, floor, db)

    duration_s = int(duration_s * floor)
    result = TravelEstimate(
        duration_s=duration_s,
        distance_m=distance_m,
        provider=provider,
        multiplier_applied=floor,
        cached=False,
        computed_at=datetime.now(UTC),
    )
    if db is not None:
        _cache_store(db, origin, dest, at, profile, result)
    return result


def _effective_floor(db: Session | None) -> float:
    """max(parameter, hard floor): a parameter below 1.3 is clamped up."""
    parameter_floor = TRAVEL_FLOOR
    if db is not None:
        try:
            parameter_floor = float(get_parameter(db, "toolbox.travel_floor", default=TRAVEL_FLOOR))
        except Exception:  # noqa: BLE001 - parameter store must not break travel
            parameter_floor = TRAVEL_FLOOR
    return max(parameter_floor, TRAVEL_FLOOR)


def _fallback_speed_kmh(db: Session | None) -> float:
    if db is None:
        return FALLBACK_SPEED_KMH_DEFAULT
    try:
        return float(
            get_parameter(db, "toolbox.fallback_speed_kmh", default=FALLBACK_SPEED_KMH_DEFAULT)
        )
    except Exception:  # noqa: BLE001
        return FALLBACK_SPEED_KMH_DEFAULT


def _local_fallback(
    origin: LatLng, dest: LatLng, floor: float, db: Session | None
) -> TravelEstimate:
    distance_m = haversine_m(origin, dest)
    speed_kmh = _fallback_speed_kmh(db)
    duration_s = int((distance_m / 1000.0) / speed_kmh * 3600.0 * floor)
    return TravelEstimate(
        duration_s=duration_s,
        distance_m=int(distance_m),
        provider="local_fallback",
        multiplier_applied=floor,
        cached=False,
        computed_at=datetime.now(UTC),
    )


def _cache_key(origin: LatLng, dest: LatLng, at: datetime, db: Session | None) -> tuple[str, str, str]:
    res = DEFAULT_H3_RES
    if db is not None:
        try:
            res = int(get_parameter(db, "toolbox.h3_res", default=DEFAULT_H3_RES))
        except Exception:  # noqa: BLE001
            res = DEFAULT_H3_RES
    return h3_cell(origin, res), h3_cell(dest, res), time_slot(at.hour)


def _cache_lookup(
    db: Session, origin: LatLng, dest: LatLng, at: datetime, profile: str
) -> TravelEstimate | None:
    origin_h3, dest_h3, slot = _cache_key(origin, dest, at, db)
    row = db.scalar(
        select(TravelCacheEntry).where(
            TravelCacheEntry.origin_h3 == origin_h3,
            TravelCacheEntry.dest_h3 == dest_h3,
            TravelCacheEntry.time_slot == slot,
            TravelCacheEntry.profile == profile,
            TravelCacheEntry.expires_at > datetime.now(UTC),
        )
    )
    if row is None:
        return None
    return TravelEstimate(
        duration_s=row.duration_s,
        distance_m=row.distance_m or 0,
        provider=row.provider,
        multiplier_applied=float(row.multiplier_applied),
        cached=True,
        computed_at=row.computed_at,
    )


def _cache_store(
    db: Session,
    origin: LatLng,
    dest: LatLng,
    at: datetime,
    profile: str,
    result: TravelEstimate,
) -> None:
    origin_h3, dest_h3, slot = _cache_key(origin, dest, at, db)
    ttl_min = CACHE_TTL_MIN_DEFAULT
    try:
        ttl_min = int(get_parameter(db, "toolbox.travel_cache_ttl_min", default=ttl_min))
    except Exception:  # noqa: BLE001
        pass
    existing = db.scalar(
        select(TravelCacheEntry).where(
            TravelCacheEntry.origin_h3 == origin_h3,
            TravelCacheEntry.dest_h3 == dest_h3,
            TravelCacheEntry.time_slot == slot,
            TravelCacheEntry.profile == profile,
        )
    )
    expires_at = datetime.now(UTC) + timedelta(minutes=ttl_min)
    if existing is not None:
        existing.duration_s = result.duration_s
        existing.distance_m = result.distance_m
        existing.provider = result.provider
        existing.multiplier_applied = result.multiplier_applied
        existing.computed_at = result.computed_at
        existing.expires_at = expires_at
    else:
        db.add(
            TravelCacheEntry(
                id=uuid4(),
                origin_h3=origin_h3,
                dest_h3=dest_h3,
                time_slot=slot,
                profile=profile,
                duration_s=result.duration_s,
                distance_m=result.distance_m,
                provider=result.provider,
                multiplier_applied=result.multiplier_applied,
                computed_at=result.computed_at,
                expires_at=expires_at,
            )
        )
    db.flush()


def _google_directions(origin: LatLng, dest: LatLng, at: datetime) -> tuple[int, int]:
    settings = get_settings()
    api_key = settings.google_directions_api_key
    if not api_key:
        raise TravelProviderError("GOOGLE_DIRECTIONS_API_KEY is not configured.")
    query = urllib.parse.urlencode(
        {
            "origin": f"{origin.lat},{origin.lng}",
            "destination": f"{dest.lat},{dest.lng}",
            "departure_time": int(at.timestamp()),
            "key": api_key,
        }
    )
    url = f"https://maps.googleapis.com/maps/api/directions/json?{query}"
    try:
        with urllib.request.urlopen(  # nosec B310 - provider HTTPS endpoint
            url, timeout=settings.travel_request_timeout_seconds
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - any transport error → fallback
        raise TravelProviderError(f"Google Directions unreachable: {exc}") from exc
    routes = payload.get("routes") or []
    if payload.get("status") != "OK" or not routes:
        raise TravelProviderError(f"Google Directions status: {payload.get('status')}")
    leg = routes[0]["legs"][0]
    duration = leg.get("duration_in_traffic") or leg["duration"]
    return int(duration["value"]), int(leg["distance"]["value"])
