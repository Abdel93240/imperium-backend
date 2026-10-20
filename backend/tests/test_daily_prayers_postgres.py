"""PostgreSQL : prières en engagements fixes de G4, choix de la mosquée qui prie le plus tôt parmi celles
joignables à temps (Q6 ; ACT-DLY-10)."""
from __future__ import annotations

import math
from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("daily prayers DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import daily as daily_routes  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.imperium import ImperiumMission  # noqa: E402
from app.models.path import PathMawaqitCache, PathRegisteredMosque  # noqa: E402
from app.services.daily import prayers, selection  # noqa: E402
from app.services.params import set_parameter  # noqa: E402
from app.services.path import mosque_times  # noqa: E402
from app.services.travel.estimate import estimate  # noqa: E402
from app.services.travel.geo import LatLng  # noqa: E402

PARIS = ZoneInfo("Europe/Paris")
DAY = date(2026, 10, 21)
IVRY = LatLng(48.8156, 2.3849)


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"dpray-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _mosque(db, user, name: str, lat: float, lng: float, **offsets) -> PathRegisteredMosque:
    mosque = PathRegisteredMosque(user_id=user.id, name=name, latitude=lat, longitude=lng, version=1, **offsets)
    db.add(mosque)
    db.commit()
    return mosque


def _adhan(db, user, mosque, name: str = "dhuhr") -> datetime:
    return mosque_times.mosque_times(db, mosque, DAY, user_id=user.id).adhans[name]


def _plan(db, user, *, origin=IVRY, ready_at=None, name="dhuhr"):
    return prayers.plan_prayer(db, user=user, name=name, day=DAY, origin=origin, ready_at=ready_at,
                               origin_source="current_position")


def test_earliest_reachable_mosque_wins_with_margin_and_iqama(db) -> None:
    user = _user(db)
    near = _mosque(db, user, "Proche", 48.8190, 2.3870, iqama_offsets={"dhuhr": 8})  # ~0,4 km
    later = _mosque(db, user, "Plus tardive", 48.8250, 2.3950, adhan_offsets={"dhuhr": 25})  # ~1,3 km
    _mosque(db, user, "Versailles", 48.8049, 2.1204)  # hors des 20 min
    early = _plan(db, user, ready_at=_adhan(db, user, near) - timedelta(minutes=30))
    assert (early.mosque_name, early.solo_reason, early.times_source) == ("Proche", None, "calculated")
    assert early.depart_at == early.adhan - timedelta(minutes=early.travel_min)
    assert early.iqama == early.adhan + timedelta(minutes=8)
    assert early.block_end == early.iqama + timedelta(minutes=15)  # iqama + 15 min
    # Plus le temps d'arriver à l'adhan de la proche : la plus tardive, encore joignable, est retenue.
    late = _plan(db, user, ready_at=_adhan(db, user, near) - timedelta(minutes=1))
    assert late.mosque_name == "Plus tardive" and late.adhan == _adhan(db, user, later)
    assert late.iqama is None and late.block_end == late.adhan + timedelta(minutes=20)
    # Le trajet porte la marge de 20 %, estimé en local (jamais de fournisseur externe pour un lieu de culte).
    trip = estimate(IVRY, LatLng(48.8190, 2.3870), early.adhan.astimezone(UTC), privacy_tier="very_high", db=db)
    assert trip.provider == "local_fallback" and early.travel_min == math.ceil(trip.duration_s / 60 * 1.2)
    too_late = _plan(db, user, ready_at=_adhan(db, user, later) + timedelta(minutes=1))
    assert too_late.solo_reason == "none_reachable_in_time" and too_late.mosque_id is None
    assert too_late.block_end == too_late.reference_adhan + timedelta(minutes=20)


def test_solo_reasons_and_mawaqit_cache_first(db) -> None:
    user = _user(db)
    assert _plan(db, user).solo_reason == "no_mosque_in_range"
    assert _plan(db, user, origin=None).solo_reason == "no_origin"
    mosque = _mosque(db, user, "Avec MAWAQIT", 48.8190, 2.3870, adhan_offsets={"dhuhr": 90})
    db.add(PathMawaqitCache(id=uuid4(), mosque_id=mosque.id, date=DAY, prayer_times={
        "fajr": "06:40", "dhuhr": "13:55", "asr": "16:30", "maghrib": "18:52", "isha": "20:30"}))
    db.commit()
    times = mosque_times.mosque_times(db, mosque, DAY, user_id=user.id)
    assert times.source == "mawaqit" and times.adhans["dhuhr"] == datetime.combine(DAY, time(13, 55), tzinfo=PARIS)
    assert _plan(db, user).adhan == datetime.combine(DAY, time(13, 55), tzinfo=PARIS)


def test_g4_stops_at_departure_when_enabled(db) -> None:
    user = _user(db)
    mosque = _mosque(db, user, "Proche", 48.8190, 2.3870)
    now = _adhan(db, user, mosque) - timedelta(minutes=45)
    assert selection.next_commitment(db, user, now, origin=IVRY) is None
    set_parameter(db, code="daily.prayer_commitments_enabled", value=True, origin="user", rationale_fr="Test.")
    db.commit()
    plan = prayers.next_prayer(db, user=user, now=now, origin=IVRY)
    commitment = selection.next_commitment(db, user, now, origin=IVRY)
    assert (commitment.kind, commitment.at) == ("prayer", plan.depart_at)
    assert commitment.ref == prayers.commitment_ref(user, DAY, "dhuhr")
    result = selection.compute(db, current_user=user, now=now, origin=IVRY)
    assert result.remaining_min == int((plan.depart_at - now).total_seconds() // 60)
    log = selection.select_next(db, current_user=user, trigger="manual", origin=IVRY, now=now)
    db.flush()
    assert (log.next_fixed_kind, log.next_fixed_ref) == ("prayer", commitment.ref)
    # Lieu inconnu : prière seul, la borne est l'adhan de référence.
    solo = selection.next_commitment(db, user, now, origin=None)
    assert solo.at == prayers.next_prayer(db, user=user, now=now, origin=None).reference_adhan
    db.rollback()


def test_day_plan_leaves_from_the_previous_mission_and_route(db) -> None:
    user = _user(db)
    mosque = _mosque(db, user, "Proche", 48.8190, 2.3870)
    dhuhr = _adhan(db, user, mosque)
    db.add(ImperiumMission(user_id=user.id, title="Médecin", domain="health", status="backlog",
                           started_at=dhuhr - timedelta(hours=3), planned_start_at=dhuhr - timedelta(hours=2),
                           estimated_minutes=60, location_lat=48.8160, location_lng=2.3850))
    db.commit()
    plans = {plan.prayer: plan for plan in prayers.day_plan(db, user=user, day=DAY, origin=None,
                                                             now=datetime(2026, 10, 21, 4, 0, tzinfo=UTC))}
    assert plans["dhuhr"].origin_source == "previous_mission" and plans["dhuhr"].mosque_name == "Proche"
    assert plans["fajr"].origin_source == "none" and plans["fajr"].solo_reason == "no_origin"
    app = FastAPI()
    app.include_router(daily_routes.router, prefix="/api/daily")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    assert client.get("/api/daily/prayers").json()["code"] == "DAILY_PRAYERS_DISABLED"
    set_parameter(db, code="daily.prayer_commitments_enabled", value=True, origin="user", rationale_fr="Test.")
    db.commit()
    body = client.get("/api/daily/prayers", params={"date": DAY.isoformat(), "lat": IVRY.lat, "lng": IVRY.lng}).json()
    assert [item["prayer"] for item in body["items"]] == ["fajr", "dhuhr", "asr", "maghrib", "isha"]
    assert body["items"][1]["mosque_name"] == "Proche"
    assert client.get("/api/daily/prayers", params={"lat": 48.8}).status_code == 422
