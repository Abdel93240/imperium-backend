"""PostgreSQL : vacances scolaires (zone C) et scan web hebdomadaire des événements et fermetures (doc 31 §10, doc 57 §5.6)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("vector signals DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, delete, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_vector  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.rides import RidesEventScan, RidesEventSignal, RidesSchoolHoliday  # noqa: E402
from app.services.ai import cloud  # noqa: E402
from app.services.vector import agendas, events, school  # noqa: E402

BASE = "/api/imperium/vector"
PARIS = events.PARIS
CALENDAR = [
    {"description": "Vacances de la Toussaint", "population": "-", "zones": "Zone C", "annee_scolaire": "2026-2027",
     "start_date": "2026-10-16T22:00:00+00:00", "end_date": "2026-11-01T23:00:00+00:00"},
    {"description": "Vacances d'Été", "population": "Enseignants", "zones": "Zone C", "annee_scolaire": "2025-2026",
     "start_date": "2026-07-03T22:00:00+00:00", "end_date": "2026-08-30T22:00:00+00:00"},
    {"description": "Vacances d'Été", "population": "Élèves", "zones": "Zone C", "annee_scolaire": "2025-2026",
     "start_date": "2026-07-03T22:00:00+00:00", "end_date": "2026-08-31T22:00:00+00:00"},
]


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    with Session(engine) as session:
        for model in (RidesEventSignal, RidesEventScan, RidesSchoolHoliday):
            session.execute(delete(model))
        session.commit()
        yield session
        session.rollback()
        for model in (RidesEventSignal, RidesEventScan, RidesSchoolHoliday):
            session.execute(delete(model))
        session.commit()


def _client(db) -> tuple[TestClient, str]:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"s-{user_id}@example.test"})
    db.commit()
    user = db.get(User, user_id)
    app = FastAPI()
    app.include_router(imperium_vector.router, prefix=BASE)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    return client, client.post(f"{BASE}/sessions", headers={"Idempotency-Key": uuid4().hex}, json={}).json()["id"]


def _offer(client, session_id, at: datetime, **extra) -> dict:
    response = client.post(f"{BASE}/sessions/{session_id}/offers", headers={"Idempotency-Key": uuid4().hex},
                           json={"price_cents": 2000, "estimated_duration_min": 25, "offered_at": at.isoformat(), **extra})
    assert response.status_code == 201, response.text
    return response.json()["features"]


def test_school_holidays_zone_c(db) -> None:
    assert school.holiday_on(db, date(2026, 10, 20)) == (None, None)  # jamais relevé : rien n'est supposé
    assert school.refresh(db, today=date(2026, 10, 23), fetcher=lambda since: CALENDAR) == 2  # ligne enseignants écartée
    db.commit()
    assert school.holiday_on(db, date(2026, 10, 17)) == (True, "Vacances de la Toussaint")   # premier jour
    assert school.holiday_on(db, date(2026, 11, 1)) == (True, "Vacances de la Toussaint")
    assert school.holiday_on(db, date(2026, 11, 2)) == (False, None)                         # jour de reprise
    assert school.holiday_on(db, date(2026, 8, 31)) == (True, "Vacances d'Été")              # élèves, pas enseignants
    assert school.refresh(db, today=date(2026, 10, 23), fetcher=lambda since: CALENDAR) == 2  # relu sans doublon
    db.commit()
    assert len(list(db.scalars(select(RidesSchoolHoliday)))) == 2


def _scan_now() -> datetime:
    return datetime.now(UTC)


def _fake_call(items):
    def call(db, **kwargs):
        assert kwargs["slot_code"] == "vector.event_scan" and kwargs["user"].startswith("Du ")
        return SimpleNamespace(output={"items": items}, model="web-model")
    return call


def _no_paris(url):
    return {"results": []}


def _paris(at: datetime | None) -> str | None:
    """Heure locale de Paris sans décalage, comme la demande la consigne du spécialiste web."""
    return at.astimezone(events.PARIS).replace(tzinfo=None).isoformat(timespec="minutes") if at else None


def _item(kind="event", title="Concert", starts=None, ends=None, code="75012", attendance=20000, **extra):
    return {"kind": kind, "category": extra.pop("category", "concert"), "title": title, "venue": extra.pop("venue", "Accor Arena"),
            "commune": "Paris", "postal_code": code, "road": extra.pop("road", None),
            "starts_at": _paris(starts), "ends_at": _paris(ends),
            "expected_attendance": attendance, "source_url": "https://example.test/x", "confidence": 0.9, **extra}


def test_scan_keeps_valid_items_once_and_feeds_offers(db) -> None:
    client, session_id = _client(db)
    now = _scan_now()
    assert _offer(client, session_id, now, pickup_zone_code="75012")["event_ending_within_60min_pickup"] is None
    items = [
        _item(starts=now - timedelta(hours=2), ends=now + timedelta(minutes=30)),               # finit dans 30 min
        _item(title="Salon", category="salon", code="93420", starts=now - timedelta(hours=5),
              ends=now + timedelta(hours=4), attendance=60000, venue="Paris Nord Villepinte"),
        _item(kind="road_closure", category="road", title="Fermeture A86", code=None, road="A86",
              starts=now - timedelta(hours=1), ends=now + timedelta(hours=5), attendance=None, venue=None),
        _item(title="Sans date", starts=None),                                                  # écarté
        _item(title="Trop loin", starts=now + timedelta(days=30)),                              # hors semaine
    ]
    run = events.scan(db, now=now, fetch_paris=_no_paris, call=_fake_call(items))
    db.commit()
    assert (run.status, run.items, run.model) == ("done", 3, "web-model")   # 5 recherches ciblées, sans doublon
    shifted = events._when("2026-10-26T20:45:00+02:00")                     # décalage faux après le changement d'heure
    assert (shifted.hour, shifted.utcoffset()) == (20, timedelta(hours=1))
    again = events.scan(db, now=now, fetch_paris=_no_paris, call=_fake_call(items[:1]))                                # même concert : pas de doublon
    db.commit()
    assert again.items == 0
    f = _offer(client, session_id, now, pickup_zone_code="75012", destination_zone_code="93420")
    assert (f["event_ending_within_60min_pickup"], f["event_ongoing_pickup"], f["event_nearby_attendees"]) == (True, True, 20000)
    assert (f["event_ending_within_60min_dest"], f["event_nearby_category"]) == (False, "concert")
    assert (f["events_ending_within_60min_idf"], f["road_closures_active"], f["rail_works_active"]) == (1, 1, 0)
    elsewhere = _offer(client, session_id, now, pickup_zone_code="75015")
    assert (elsewhere["event_ending_within_60min_pickup"], elsewhere["event_nearby_attendees"]) == (False, 0)
    feed = client.get(f"{BASE}/feeds/events").json()
    assert feed["status"] == "ok" and [i["title"] for i in feed["items"]] == ["Salon", "Concert"]
    roads = client.get(f"{BASE}/feeds/events", params={"kind": "road_closure"}).json()
    assert [i["road"] for i in roads["items"]] == ["A86"]
    run.status, run.error = "failed", "remplacé par un nouveau scan"                           # scan remplacé : ignoré
    events.scan(db, now=now, fetch_paris=_no_paris, call=_fake_call([]))
    db.commit()
    assert client.get(f"{BASE}/feeds/events").json()["items"] == []


def test_failed_scan_is_recorded_and_feed_unavailable(db) -> None:
    client, _ = _client(db)
    assert client.get(f"{BASE}/feeds/events").json()["status"] == "unavailable"

    def off(db, **kwargs):
        raise cloud.CloudError("Cloud slot 'vector.event_scan' is off.")
    def down(url):
        raise agendas.AgendaUnavailableError("URLError")
    run = events.scan(db, call=off, fetch_paris=down)
    db.commit()
    assert (run.status, run.items) == ("failed", 0) and "off" in run.error
    assert client.get(f"{BASE}/feeds/events").json()["status"] == "unavailable"


def test_only_the_scan_slot_may_search_the_web(monkeypatch) -> None:
    seen = []
    monkeypatch.setattr(cloud, "_run", lambda args, stdin, timeout, cwd: seen.append(args) or "")
    for slot, web in (("vector.event_scan", True), ("calendar.deadline_plan", False)):
        try:
            cloud._codex("m", None, "s", "u", {"type": "object"}, web=web)
        except Exception:  # noqa: BLE001 - sortie vide : seul l'argument compte ici
            pass
    assert "web_search=live" in seen[0] and "web_search=disabled" in seen[1]
    # L'hôte de code porte la recherche web de Codex : gardé pour le slot web seulement (scan vide le 24/10 sans lui).
    disabled = [[a[i + 1] for i, x in enumerate(a) if x == "--disable"] for a in seen]
    assert "code_mode_host" not in disabled[0] and "code_mode_host" in disabled[1]
    assert "shell_tool" in disabled[0] and "browser_use" in disabled[0]   # le reste reste coupé
    assert cloud.WEB_SLOTS == frozenset({"vector.event_scan"})
    assert cloud.SLOT_ROLES["vector.event_scan"] == "web_fresh_data"


def test_paris_open_data_sessions_become_events(db) -> None:
    record = {"title": "Jam de nuit", "qfap_tags": "Concert", "address_name": "Le Baiser Salé", "address_zipcode": "75001",
              "address_city": "Paris", "url": "https://www.paris.fr/x", "date_start": "2026-10-27T00:00:00+00:00",
              "date_end": "2026-10-31T23:59:59+00:00",
              "occurrences": "2026-10-27T23:00:00+02:00_2026-10-27T02:00:00+02:00;2026-11-20T21:00:00+01:00_2026-11-20T22:00:00+01:00"}
    expo = {**record, "title": "Expo", "qfap_tags": "Expo", "occurrences": None}
    kids = {**record, "title": "Concert enfants", "qfap_tags": "Concert;Enfants"}
    start = datetime(2026, 10, 26, tzinfo=events.PARIS)
    items = agendas.paris_events(start, start + timedelta(days=7), fetch=lambda url: {"results": [record, expo, kids]})
    assert [(i["title"], i["starts_at"], i["ends_at"], i["category"]) for i in items] == [
        ("Jam de nuit", "2026-10-27T23:00", "2026-10-28T02:00", "concert")]           # finit le lendemain, hors semaine écartée
    run = events.scan(db, now=start + timedelta(hours=3), call=_fake_call([]),
                      fetch_paris=lambda url: {"results": [record]})
    db.commit()
    assert (run.status, run.items) == ("done", 1)
    daily = events.scan(db, now=start + timedelta(days=1, hours=12), daily=True, call=_fake_call([]),
                        fetch_paris=lambda url: {"results": [record]})
    db.commit()
    assert (daily.week_start, daily.items) == (date(2026, 10, 27), 0)                 # même séance : pas de doublon
