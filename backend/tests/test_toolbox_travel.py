"""§13.7 travel: 1.3 floor even against a lower parameter, cache hit/expiry,
very_high → ZERO outbound request (network spy), fallback marked."""

from __future__ import annotations

import urllib.request
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select

from _postgres import require_test_database_url

pytest.importorskip("psycopg")

from sqlalchemy.orm import Session  # noqa: E402

from app.models import ai, auth, event, idempotency, imperium, path, toolbox, vault  # noqa: E402,F401
from app.models.toolbox import TravelCacheEntry  # noqa: E402
from app.services.params import set_parameter  # noqa: E402
import importlib  # noqa: E402

from app.services.travel import LatLng, estimate  # noqa: E402

# The package re-exports estimate() (graved signature), which shadows the
# submodule attribute — resolve the module explicitly for monkeypatching.
estimate_module = importlib.import_module("app.services.travel.estimate")
from app.services.travel.geo import cell_corridor, h3_cell, haversine_m  # noqa: E402

ORIGIN = LatLng(48.8566, 2.3522)
DEST = LatLng(48.8738, 2.2950)


@pytest.fixture(scope="module")
def engine():
    engine = create_engine(require_test_database_url("toolbox travel tests"), future=True)
    yield engine
    engine.dispose()


@pytest.fixture()
def network_spy(monkeypatch):
    calls = []

    def spy(*args, **kwargs):
        calls.append(args)
        raise AssertionError("outbound network request detected")

    monkeypatch.setattr(urllib.request, "urlopen", spy)
    return calls


def test_floor_1_3_applies_even_when_parameter_tries_lower(engine, monkeypatch) -> None:
    with Session(engine) as db:
        set_parameter(
            db,
            code="toolbox.travel_floor",
            value=1.0,
            origin="test",
            rationale_fr="Tentative de plancher sous 1,3 (doit être clampée).",
        )
        db.commit()
        try:
            result = estimate(ORIGIN, DEST, datetime.now(UTC), privacy_tier="very_high", db=db)
            assert result.multiplier_applied == 1.3  # hard floor wins over the parameter
        finally:
            set_parameter(
                db,
                code="toolbox.travel_floor",
                value=1.3,
                origin="test",
                rationale_fr="Restauration du seed.",
            )
            db.commit()


def test_very_high_privacy_never_reaches_a_provider(network_spy, monkeypatch) -> None:
    # Lock-test Q2: a very_high call produces ZERO outbound request even with a
    # provider key configured.
    from types import SimpleNamespace

    monkeypatch.setattr(
        estimate_module,
        "get_settings",
        lambda: SimpleNamespace(
            google_directions_api_key="fake-key", travel_request_timeout_seconds=5
        ),
    )
    result = estimate(ORIGIN, DEST, datetime.now(UTC), privacy_tier="very_high")
    assert result.provider == "local_fallback"
    assert network_spy == []


def test_offline_fallback_is_marked_and_uses_25kmh_floor(network_spy) -> None:
    # No API key configured → local fallback: distance/25 km/h × 1.3.
    result = estimate(ORIGIN, DEST, datetime.now(UTC))
    assert result.provider == "local_fallback"
    distance_m = haversine_m(ORIGIN, DEST)
    expected_s = int((distance_m / 1000.0) / 25.0 * 3600.0 * 1.3)
    assert abs(result.duration_s - expected_s) <= 1
    assert network_spy == []


def test_cache_hit_and_expiry(engine, monkeypatch) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr(
        estimate_module,
        "get_settings",
        lambda: SimpleNamespace(
            google_directions_api_key="fake-key", travel_request_timeout_seconds=5
        ),
    )
    provider_calls = []

    def fake_directions(origin, dest, at):
        provider_calls.append(at)
        return 600, 4600

    monkeypatch.setattr(estimate_module, "_google_directions", fake_directions)

    at = datetime.now(UTC).replace(hour=9, minute=5)
    with Session(engine) as db:
        # Idempotent re-runs: purge any committed entry for this cache key.
        db.query(TravelCacheEntry).filter(
            TravelCacheEntry.origin_h3 == h3_cell(ORIGIN),
            TravelCacheEntry.dest_h3 == h3_cell(DEST),
        ).delete()
        db.commit()
        first = estimate(ORIGIN, DEST, at, db=db)
        assert first.cached is False
        assert first.provider == "google_directions"
        assert first.duration_s == int(600 * 1.3)
        db.commit()

        second = estimate(ORIGIN, DEST, at.replace(minute=40), db=db)  # same hour slot
        assert second.cached is True
        assert len(provider_calls) == 1  # cache hit, no second provider call

        # Expire the entry → provider is called again.
        row = db.scalar(
            select(TravelCacheEntry).where(
                TravelCacheEntry.origin_h3 == h3_cell(ORIGIN),
                TravelCacheEntry.dest_h3 == h3_cell(DEST),
            )
        )
        row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.flush()
        third = estimate(ORIGIN, DEST, at, db=db)
        assert third.cached is False
        assert len(provider_calls) == 2
        db.query(TravelCacheEntry).filter(
            TravelCacheEntry.origin_h3 == h3_cell(ORIGIN),
            TravelCacheEntry.dest_h3 == h3_cell(DEST),
        ).delete()
        db.commit()


def test_geo_corridor_and_h3_cells_are_deterministic() -> None:
    corridor_1 = cell_corridor(ORIGIN, DEST)
    corridor_2 = cell_corridor(ORIGIN, DEST)
    assert corridor_1 == corridor_2
    assert h3_cell(ORIGIN) in corridor_1
    assert h3_cell(DEST) in corridor_1
    assert len(corridor_1) > len(set())  # non-empty widened path
