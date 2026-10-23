"""PostgreSQL : règle économique de Vector — €/h global et note de la zone d'arrivée (décision utilisateur 2026-10-23)."""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("vector economics DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, delete  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models.rides import (  # noqa: E402
    RidesDropObservation,
    RidesEventScan,
    RidesEventSignal,
    RidesWeatherCellReading,
    RidesZoneScore,
)
from app.services.vector import economics, geo, grid  # noqa: E402

PARIS = economics.PARIS
EVENING = datetime(2026, 10, 23, 17, 46, tzinfo=PARIS)


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    with Session(engine) as session:
        for model in (RidesZoneScore, RidesEventSignal, RidesEventScan, RidesWeatherCellReading, RidesDropObservation):
            session.execute(delete(model))
        session.commit()
        yield session
        session.rollback()
        for model in (RidesZoneScore, RidesEventSignal, RidesEventScan, RidesDropObservation):
            session.execute(delete(model))
        session.commit()


def _verdict(db, price, approach, trip, place, at=EVENING):
    return economics.verdict(db, price_cents=price, approach_min=approach, trip_min=trip,
                             destination=geo.resolve(place) if place else None, offered_at=at)


def test_real_offer_of_17h46_is_red(db) -> None:
    v = _verdict(db, 1284, 8, 28, "Fontenay-sous-Bois 94120")
    assert v.signal == "red"
    assert (v.features["hourly_global_eur"], v.features["dest_zone_score"], v.features["reposition_min"]) == (21.4, 50.0, 0)
    assert v.features["dest_zone_score_source"] == "default"


def test_excellent_arrival_zone_turns_green_under_the_threshold(db) -> None:
    late = datetime(2026, 10, 23, 21, 0, tzinfo=PARIS)
    v = _verdict(db, 1000, 5, 25, "Bastille, Paris", at=late)           # 20 €/h, Paris en fin de soirée : 8/10
    assert (v.signal, v.features["dest_zone_score"]) == ("green", 80.0)
    assert "zone excellente" in v.reason


def test_bad_arrival_zone_adds_repositioning_time(db) -> None:
    v = _verdict(db, 2400, 5, 40, "Chelles 77500")                      # 32 €/h global, grande couronne : 3/10
    assert v.features["dest_zone_score"] == 30.0
    assert v.features["reposition_min"] > 20
    assert v.signal == "red" and v.features["hourly_effective_eur"] < 25
    rich = _verdict(db, 6000, 8, 40, "Chelles 77500")                   # même zone, course bien payée
    assert rich.signal == "green"


def test_user_scores_and_events_raise_the_zone(db) -> None:
    db.add(RidesZoneScore(id=uuid4(), zone_key="94120", time_block="all", score=9, note="sortie de bureaux"))
    db.commit()
    assert _verdict(db, 1284, 8, 28, "Fontenay-sous-Bois 94120").signal == "green"
    end = EVENING + timedelta(minutes=36)
    scan = RidesEventScan(id=uuid4(), started_at=EVENING, week_start=EVENING.date(), status="done")
    db.add(scan)
    db.flush()
    db.add(RidesEventSignal(id=uuid4(), scan_id=scan.id, kind="event", category="concert", title="Concert",
                            postal_code="94000", starts_at=end - timedelta(hours=2), ends_at=end + timedelta(minutes=10),
                            confidence=0.9, fingerprint=uuid4().hex))
    db.commit()
    v = _verdict(db, 1284, 8, 28, "Créteil 94000")                     # 94 le soir 50/100 + 20 (concert) = 70
    assert v.features["dest_zone_score"] == 70.0
    assert "événement" in v.features["dest_zone_reasons"][-1]


def test_no_ride_duration_no_opinion_and_unknown_destination(db) -> None:
    assert _verdict(db, 1284, 8, None, "Créteil 94000").signal is None
    blind = _verdict(db, 3000, 5, 25, None)                            # 60 €/h, arrivée inconnue : €/h seul
    assert (blind.signal, blind.features["dest_zone_score"]) == ("green", None)


def _measure(db, lat, lng, at, eur_h):
    from sqlalchemy import text

    import app.models.imperium  # noqa: F401 - table des missions, cible d'une clé de session
    from app.models.rides import RidesOffer, RidesSession
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) VALUES (:i, :e, FALSE, now(), now())"),
               {"i": str(user_id), "e": f"m-{user_id}@example.test"})
    session = RidesSession(id=uuid4(), user_id=user_id, status="completed", started_at=at - timedelta(hours=1), ended_at=at,
                           version=1, idempotency_key=uuid4().hex, request_hash="x")
    db.add(session)
    db.flush()
    offer = RidesOffer(id=uuid4(), user_id=user_id, session_id=session.id, offered_at=at, source="manual", platform="bolt",
                       price_cents=1000, ride_type="immediate", features={}, version=1, idempotency_key=uuid4().hex,
                       request_hash="x", triggered_rules=[])
    db.add(offer)
    db.flush()
    db.add(RidesDropObservation(id=uuid4(), user_id=user_id, session_id=session.id, offer_id=offer.id, dropped_at=at,
                                drop_lat=lat, drop_lng=lng, slot=grid.slot_of(at), day_type=grid.day_type(at),
                                status="closed", cycle_hourly_cents=int(eur_h * 100)))


def test_measures_take_over_the_default_score(db) -> None:
    fontenay = geo.resolve("Fontenay-sous-Bois 94120")
    end = EVENING + timedelta(minutes=36)
    # Six dépôts passés au même endroit, même créneau, jours de semaine : 40 €/h mesurés.
    for weeks in range(1, 7):
        _measure(db, fontenay.lat, fontenay.lng, end - timedelta(weeks=weeks), 40)
    db.commit()
    scored = economics.base_score(db, fontenay, end)
    assert scored.source == "measured" and scored.measured_weight > 3
    assert scored.score > 50                                           # mieux que la note de départ (50)
    v = _verdict(db, 1284, 8, 28, "Fontenay-sous-Bois 94120")
    assert v.features["dest_zone_expected_eur"] > 25
    elsewhere = economics.base_score(db, geo.resolve("Suresnes"), end)  # loin : aucune mesure ne compte
    assert (elsewhere.source, elsewhere.measured_weight) == ("default", 0.0)
