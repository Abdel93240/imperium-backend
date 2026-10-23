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

from app.models.rides import RidesEventScan, RidesEventSignal, RidesWeatherCellReading, RidesZoneScore  # noqa: E402
from app.services.vector import economics, geo  # noqa: E402

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
        for model in (RidesZoneScore, RidesEventSignal, RidesEventScan, RidesWeatherCellReading):
            session.execute(delete(model))
        session.commit()
        yield session
        session.rollback()
        for model in (RidesZoneScore, RidesEventSignal, RidesEventScan):
            session.execute(delete(model))
        session.commit()


def _verdict(db, price, approach, trip, place, at=EVENING):
    return economics.verdict(db, price_cents=price, approach_min=approach, trip_min=trip,
                             destination=geo.resolve(place) if place else None, offered_at=at)


def test_real_offer_of_17h46_is_red(db) -> None:
    v = _verdict(db, 1284, 8, 28, "Fontenay-sous-Bois 94120")
    assert v.signal == "red"
    assert (v.features["hourly_global_eur"], v.features["dest_zone_score"], v.features["reposition_min"]) == (21.4, 5.0, 0)


def test_excellent_arrival_zone_turns_green_under_the_threshold(db) -> None:
    late = datetime(2026, 10, 23, 21, 0, tzinfo=PARIS)
    v = _verdict(db, 1000, 5, 25, "Bastille, Paris", at=late)           # 20 €/h, Paris en fin de soirée : 8/10
    assert (v.signal, v.features["dest_zone_score"]) == ("green", 8.0)
    assert "zone excellente" in v.reason


def test_bad_arrival_zone_adds_repositioning_time(db) -> None:
    v = _verdict(db, 2400, 5, 40, "Chelles 77500")                      # 32 €/h global, grande couronne : 3/10
    assert v.features["dest_zone_score"] == 3.0
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
    v = _verdict(db, 1284, 8, 28, "Créteil 94000")                     # 94 le soir 5/10 + 2 (concert) = 7
    assert v.features["dest_zone_score"] == 7.0
    assert "événement" in v.features["dest_zone_reasons"][-1]


def test_no_ride_duration_no_opinion_and_unknown_destination(db) -> None:
    assert _verdict(db, 1284, 8, None, "Créteil 94000").signal is None
    blind = _verdict(db, 3000, 5, 25, None)                            # 60 €/h, arrivée inconnue : €/h seul
    assert (blind.signal, blind.features["dest_zone_score"]) == ("green", None)
