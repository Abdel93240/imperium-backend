"""PostgreSQL : flux en temps réel — perturbations IDFM, trafic TomTom, avions OpenSky — et leur place dans les offres."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("vector feeds DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, delete  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models.rides import (  # noqa: E402
    RidesAirportSnapshot,
    RidesTrafficIncident,
    RidesTransitDisruption,
    RidesTransitStop,
)
from app.services.vector import feeds, grid  # noqa: E402

GARE_DE_LYON = (48.8443, 2.3743)
MODELS = (RidesTransitDisruption, RidesTransitStop, RidesTrafficIncident, RidesAirportSnapshot)


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    with Session(engine) as session:
        for model in MODELS:
            session.execute(delete(model))
        session.commit()
        yield session
        session.rollback()
        for model in MODELS:
            session.execute(delete(model))
        session.commit()


def _idfm(now: datetime) -> dict:
    fmt = "%Y%m%dT%H%M%S"
    local = now.astimezone(grid.PARIS)
    period = [{"begin": (local - timedelta(minutes=20)).strftime(fmt), "end": (local + timedelta(hours=1)).strftime(fmt)}]
    return {
        "disruptions": [
            {"id": "d1", "severity": "BLOQUANTE", "cause": "PERTURBATION", "title": "RER A : panne", "applicationPeriods": period},
            {"id": "d2", "severity": "INFORMATION", "cause": "INFORMATION", "title": "Info", "applicationPeriods": period},
            {"id": "d3", "severity": "PERTURBEE", "cause": "TRAVAUX", "title": "Bus 91", "applicationPeriods": period},
        ],
        "lines": [
            {"id": "line:A", "shortName": "A", "mode": "RapidTransit", "impactedObjects": [
                {"type": "line", "id": "line:A", "disruptionIds": ["d1", "d2"]},
                {"type": "stop_point", "id": "stop:gdl", "name": "Gare de Lyon", "disruptionIds": ["d1"]}]},
            {"id": "line:91", "shortName": "91", "mode": "Bus", "impactedObjects": [
                {"type": "stop_point", "id": "stop:bus", "name": "X", "disruptionIds": ["d3"]}]},
        ],
    }


def test_transit_traffic_airports_feed_the_offer_context(db) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    calls = []

    def stop(sid):
        calls.append(sid)
        return {"stop_points": [{"coord": {"lat": str(GARE_DE_LYON[0]), "lon": str(GARE_DE_LYON[1])}}]}

    assert feeds.refresh_transit(db, now=now, fetch_bulk=lambda: _idfm(now), fetch_stop=stop) == 1  # bus et info écartés
    assert feeds.refresh_transit(db, now=now + timedelta(minutes=10), fetch_bulk=lambda: _idfm(now), fetch_stop=stop) == 1
    assert calls == ["stop:gdl"]                                          # position de l'arrêt demandée une seule fois
    jam = {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[2.30, 48.88], [2.31, 48.88], [2.32, 48.88]]},
           "properties": {"iconCategory": 6, "magnitudeOfDelay": 3, "delay": 600, "length": 1200, "roadNumbers": ["A1"]}}
    closed = {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[2.31, 48.881], [2.312, 48.881]]},
              "properties": {"iconCategory": 8, "magnitudeOfDelay": 4, "delay": 0, "length": 300, "roadNumbers": ["D909"]}}
    north_west = feeds.TOMTOM_BOXES[2]  # le rectangle qui contient Paris nord-ouest
    flows = []
    assert feeds.refresh_traffic(db, now=now, fetch=lambda box: {"incidents": [jam, closed] if box == north_west else []},
                                 flow=lambda lat, lng: flows.append((lat, lng)) or
                                 {"frc": "FRC1", "currentSpeed": 20, "freeFlowSpeed": 80}) == 2
    assert len(flows) == 1                                                # seule la fermeture est mesurée
    assert feeds.closure_impact("FRC1", 20, 80) == 74 and feeds.closure_impact("FRC6", 30, 30) == 5
    assert feeds.closure_impact(None, 10, 50) is None
    assert feeds.closure_impact("FRC0", 0, 0) == 100 and feeds.closure_impact("FRC2", 30, 30, closed=True) == 70
    cdg = feeds.AIRPORTS["CDG"]

    def sky(box):
        inside = box[0] < cdg[0] < box[2] and box[1] < cdg[1] < box[3]
        return {"states": [["a1", "", "", 0, 0, cdg[1] + 0.05, cdg[0], 600, False, 70, 0, -4],
                           ["a2", "", "", 0, 0, cdg[1] + 0.08, cdg[0], 800, False, 80, 0, -5],
                           ["a3", "", "", 0, 0, cdg[1], cdg[0], 0, True, 0, 0, 0],
                           ["a4", "", "", 0, 0, cdg[1] + 0.05, cdg[0], 3000, False, 200, 0, 8]] if inside else []}
    for minutes in (50, 40):
        feeds.refresh_airports(db, now=now - timedelta(minutes=minutes), fetch=sky)
    db.commit()
    ctx = feeds.context(db, now + timedelta(minutes=10), {"pickup": GARE_DE_LYON, "dest": (48.8805, 2.311)})
    assert (ctx["transit_heavy_disruptions"], ctx["transit_blocking"], ctx["rer_lines_disrupted"]) == (1, 1, 1)
    assert (ctx["pickup_transit_disrupted"], ctx["pickup_transit_blocking"], ctx["pickup_transit_lines"]) == (True, True, ["rer A"])
    assert (ctx["dest_transit_disrupted"], ctx["dest_traffic_delay_min"], ctx["dest_road_closed"]) == (False, 10, True)
    assert (ctx["traffic_incidents_idf"], ctx["traffic_closures_idf"], ctx["traffic_closures_departmental_idf"]) == (2, 1, 1)
    assert (ctx["traffic_closures_major_idf"], ctx["traffic_jams_major_idf"], ctx["traffic_jams_on_major_roads_idf"]) == (0, 1, 1)
    assert (ctx["dest_major_road_closed"], ctx["dest_jam_level"], ctx["dest_closure_impact_max"]) == (False, 3, 74)
    assert ctx["traffic_closures_high_impact_idf"] == 1
    assert [feeds.road_class(r) for r in (["A1"], ["N118"], ["BP"], ["D909"], [], ["Rue X"])] == [
        "major", "major", "major", "departmental", "street", "street"]
    assert (ctx["cdg_landings_30_60_min"], ctx["ory_landings_30_60_min"]) == (2, 0)   # a1, a2 en approche finale
    stale = feeds.context(db, now + timedelta(hours=3), {"pickup": GARE_DE_LYON})
    assert (stale["transit_heavy_disruptions"], stale["pickup_transit_disrupted"]) == (None, None)  # relevé trop ancien


def test_missing_keys_say_so(db, monkeypatch) -> None:
    from app.core import config
    monkeypatch.setattr(config.get_settings(), "idfm_prim_api_key", None)
    monkeypatch.setattr(config.get_settings(), "tomtom_api_key", None)
    with pytest.raises(feeds.FeedUnavailableError):
        feeds.refresh_transit(db)
    with pytest.raises(feeds.FeedUnavailableError):
        feeds.refresh_traffic(db)


def test_dashboard_cards_read_the_latest_pass(db) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    assert feeds.transit_feed(db, now=now).status == "unavailable"            # aucun relevé : rien d'inventé
    assert feeds.airport_feed(db, now=now).airports == []
    assert feeds.traffic_feed(db, now=now).status == "unavailable"
    old, last = now - timedelta(minutes=10), now - timedelta(minutes=5)

    def disruption(at, line, mode, severity, title, ends):
        return RidesTransitDisruption(fetched_at=at, disruption_id=title, line_id=line, line_name=f"{mode} {line[-1]}",
                                      mode=mode, severity=severity, title=title, ends_at=now + timedelta(hours=ends),
                                      stop_ids=[], zone_codes=[])
    db.add_all([
        disruption(old, "line:C", "rer", "BLOQUANTE", "ancien relevé", 1),
        disruption(last, "line:4", "metro", "PERTURBEE", "Métro 4 : ralenti", 1),
        disruption(last, "line:4", "metro", "BLOQUANTE", "Métro 4 : interrompu", 3),
        disruption(last, "line:4", "metro", "BLOQUANTE", "Métro 4 : interrompu", 3),
        disruption(last, "line:A", "rer", "BLOQUANTE", "RER A : panne", 2),
        disruption(last, "line:L", "transilien", "PERTURBEE", "Transilien L : retards", 1),
    ])

    def incident(category, roads, **kw):
        return RidesTrafficIncident(fetched_at=last, category=category, roads=roads, lat=48.85, lng=2.35, zone_code="75", **kw)
    db.add_all([
        incident(6, ["A86"], magnitude=3, delay_s=900, length_m=4200),
        incident(8, ["A14"], impact=100, length_m=4000),
        incident(8, ["D909"], impact=70),                                     # route départementale : synthèse seulement
        incident(9, ["BP"], delay_s=60),
    ])
    db.add_all([RidesAirportSnapshot(fetched_at=at, airport="CDG", approaching=n, on_ground=4, final_icao=icao)
                for at, n, icao in ((now - timedelta(minutes=40), 1, ["a1"]), (last, 2, ["a2", "a3"]))])
    db.commit()

    transit = feeds.transit_feed(db, now=now)
    assert transit.status == "ok" and transit.fetched_at == last
    assert [(line.label, line.status) for line in transit.lines] == [
        ("RER A", "interrupted"), ("Métro 4", "interrupted"), ("Transilien L", "disrupted")]  # interrompues, fin la plus proche
    assert transit.lines[1].messages == ["Métro 4 : interrompu", "Métro 4 : ralenti"]  # pire d'abord, sans doublon
    assert feeds.transit_feed(db, now=now + timedelta(minutes=30)).status == "stale"

    traffic = feeds.traffic_feed(db, now=now)
    assert (traffic.incidents, traffic.delay_min, traffic.major_closures, traffic.major_jams) == (4, 16, 1, 1)
    assert [(i.kind, i.roads) for i in traffic.items] == [("closure", ["A14"]), ("jam", ["A86"]), ("works", ["BP"])]
    assert (traffic.items[1].delay_min, traffic.items[1].length_km, traffic.items[1].jam_level) == (15, 4.2, 3)

    airports = feeds.airport_feed(db, now=now)
    assert [(a.airport, a.approaching, a.on_ground, a.landings_last_30_min, a.landings_30_60_min)
            for a in airports.airports] == [("CDG", 2, 4, 2, 1)]
