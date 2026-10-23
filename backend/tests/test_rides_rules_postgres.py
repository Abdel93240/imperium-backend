"""PostgreSQL : règles métier Vector et signal « règles seules » (doc 57 §3.1, §4, §5.7)."""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("rides rules DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_vector  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.rides import RidesBusinessRule, RidesRuleRevision  # noqa: E402
from app.services.vector import offers  # noqa: E402

BASE = "/api/imperium/vector"
PARIS = offers.PARIS
NOON = datetime(2026, 10, 14, 12, 0, tzinfo=PARIS)  # journée
NIGHT = datetime(2026, 10, 14, 2, 30, tzinfo=PARIS)


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    with Session(engine) as session:
        yield session
        session.rollback()


def _user(db) -> User:
    user_id = uuid4()
    db.execute(
        text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) VALUES (:id, :email, FALSE, now(), now())"),
        {"id": str(user_id), "email": f"rules-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_vector.router, prefix=BASE)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _setup(db):
    user = _user(db)
    client = _client(db, user)
    session = client.post(f"{BASE}/sessions", headers={"Idempotency-Key": uuid4().hex}, json={}).json()
    return user, client, session["id"]


def _offer(client, session_id, at: datetime, **extra) -> dict:
    body = {"price_cents": 2000, "estimated_duration_min": 25, "offered_at": at.isoformat(), **extra}
    response = client.post(f"{BASE}/sessions/{session_id}/offers", headers={"Idempotency-Key": uuid4().hex}, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_default_rules_and_not_coded_list(db) -> None:
    _, client, _ = _setup(db)
    body = client.get(f"{BASE}/rules").json()
    assert [(r["rule_code"], r["action"], r["is_active"]) for r in body["items"]] == [
        ("R1", "red", True), ("R2", "red", True), ("R3", "red", True), ("R7", "green", True), ("R8", "green", True),
    ]
    assert body["not_coded"] == ["R4", "R5", "R6", "R9", "R10", "R11"]


def test_red_and_green_signals(db) -> None:
    _, client, session_id = _setup(db)
    r1 = _offer(client, session_id, NOON, destination_zone_code="75008")
    assert (r1["signal"], r1["triggered_rules"], r1["signal_source"]) == ("red", ["R1"], "rules_only")
    assert r1["signal_reason"] == "R1 : Éviter le 8e arrondissement."
    assert r1["features"]["rule_R1_triggered"] is True and r1["features"]["rule_R7_triggered"] is False
    r2 = _offer(client, session_id, NOON, pickup_zone_code="75018", destination_zone_code="75011")
    assert (r2["signal"], r2["triggered_rules"]) == ("red", ["R2"])
    not_daytime = _offer(client, session_id, NIGHT, pickup_zone_code="75018", destination_zone_code="75011")
    assert (not_daytime["signal"], not_daytime["triggered_rules"]) == ("green", ["R7"])
    scheduled = _offer(client, session_id, NIGHT, ride_type="scheduled", destination_zone_code="93200")
    assert (scheduled["signal"], scheduled["triggered_rules"]) == ("green", ["R8"])


def test_red_wins_over_green_and_missing_data_abstains(db) -> None:
    _, client, session_id = _setup(db)
    both = _offer(client, session_id, NIGHT, destination_zone_code="75008", ride_type="scheduled")
    assert (both["signal"], both["triggered_rules"]) == ("red", ["R1", "R7", "R8"])
    unknown = _offer(client, session_id, NOON)
    assert (unknown["signal"], unknown["triggered_rules"], unknown["signal_reason"]) == (
        None, [], "Haute incertitude, à toi de juger.",
    )
    assert client.post(f"{BASE}/sessions/{session_id}/offers", headers={"Idempotency-Key": uuid4().hex},
                       json={"price_cents": 100, "pickup_zone_code": "Paris"}).status_code == 422


def test_rule_revision_with_history(db) -> None:
    user, client, session_id = _setup(db)
    rules = {r["rule_code"]: r for r in client.get(f"{BASE}/rules").json()["items"]}
    off = client.patch(f"{BASE}/rules/R1", json={"version": rules["R1"]["version"], "is_active": False,
                                                  "reason": "Le 8e rapporte bien le soir."})
    assert (off.status_code, off.json()["is_active"], off.json()["revision_count"]) == (200, False, 1)
    assert _offer(client, session_id, NOON, destination_zone_code="75008")["signal"] is None
    stale = client.patch(f"{BASE}/rules/R1", json={"version": 1, "is_active": True, "reason": "Retour"})
    assert (stale.status_code, stale.json()["code"]) == (409, "RIDES_RULE_VERSION_CONFLICT")
    widened = client.patch(f"{BASE}/rules/R2", json={
        "version": 1, "reason": "Ajouter le 20e en journée.",
        "conditions": {"zone_codes": ["75018", "75019", "75020"], "applies_to": ["pickup"], "time_blocks": ["daytime"]},
    })
    assert widened.json()["conditions"]["zone_codes"] == ["75018", "75019", "75020"]
    assert _offer(client, session_id, NOON, pickup_zone_code="75020")["triggered_rules"] == ["R2"]
    mine = list(db.scalars(
        select(RidesRuleRevision).join(RidesBusinessRule, RidesBusinessRule.id == RidesRuleRevision.rule_id)
        .where(RidesBusinessRule.user_id == user.id).order_by(RidesRuleRevision.revised_at)
    ))
    assert [(r.revision_type, r.proposed_by, r.user_validated) for r in mine] == [
        ("disabled", "user_manual", True), ("modified", "user_manual", True),
    ]
    assert client.patch(f"{BASE}/rules/R2", json={"version": 2, "reason": "x", "conditions": {}}).status_code == 422
    assert client.patch(f"{BASE}/rules/R99", json={"version": 1, "reason": "Inconnue"}).status_code == 404
    applied = {r["rule_code"]: r["times_applied"] for r in client.get(f"{BASE}/rules").json()["items"]}
    assert applied["R2"] == 1


def test_r3_far_destination_in_daytime(db) -> None:
    _, client, session_id = _setup(db)
    far = _offer(client, session_id, NOON, destination_zone_code="77700")  # Marne-la-Vallée, au-delà de Noisy-le-Grand
    assert (far["signal"], far["triggered_rules"]) == ("red", ["R3"])
    for code in ("75011", "92100", "78000", "95700", "91300"):  # Paris, petite couronne, communes en deçà, Roissy-CDG
        assert _offer(client, session_id, NOON, destination_zone_code=code)["triggered_rules"] == [], code
    assert _offer(client, session_id, NIGHT, destination_zone_code="77700")["triggered_rules"] == []
    assert _offer(client, session_id, NOON)["triggered_rules"] == []  # sans code postal : rien n'est supposé
    rules = {r["rule_code"]: r for r in client.get(f"{BASE}/rules").json()["items"]}
    allowed = client.patch(f"{BASE}/rules/R3", json={
        "version": rules["R3"]["version"], "reason": "Marne-la-Vallée me convient.",
        "conditions": {**rules["R3"]["conditions"],
                       "destination_allowed_codes": [*rules["R3"]["conditions"]["destination_allowed_codes"], "77700"]},
    })
    assert allowed.status_code == 200, allowed.text
    assert _offer(client, session_id, NOON, destination_zone_code="77700")["signal"] is None
    lonely = client.patch(f"{BASE}/rules/R3", json={"version": 2, "reason": "x", "conditions": {"destination_allowed_codes": ["77700"]}})
    assert lonely.status_code == 422


def test_offer_read_by_the_assistant(db) -> None:
    _, client, session_id = _setup(db)
    read = _offer(client, session_id, NOON, source="assistant", destination_zone_code="75008")
    assert (read["source"], read["signal"]) == ("assistant", "red")
    assert _offer(client, session_id, NOON)["source"] == "manual"
    bad = client.post(f"{BASE}/sessions/{session_id}/offers", headers={"Idempotency-Key": uuid4().hex},
                      json={"price_cents": 100, "source": "ocr"})
    assert bad.status_code == 422


def test_offer_keeps_every_surge_form_and_context(db) -> None:
    _, client, session_id = _setup(db)
    assumption = datetime(2026, 8, 15, 12, 0, tzinfo=PARIS)  # 15 août
    body = {"surge_multiplier": "1.4", "surge_percent": 20, "surge_bonus_cents": 240, "toll_cents": 410,
            "ride_class": "comfort", "payment_type": "cash", "driver_lat": "48.853400", "driver_lng": "2.348800",
            "pickup_zone_code": "92100", "destination_zone_code": "75011"}
    offer = client.post(f"{BASE}/sessions/{session_id}/offers", headers={"Idempotency-Key": uuid4().hex},
                        json={"price_cents": 3150, "estimated_duration_min": 35, "offered_at": NOON.isoformat(), **body})
    assert offer.status_code == 201, offer.text
    f = offer.json()["features"]
    assert (f["surge_multiplier"], f["surge_percent"], f["surge_bonus_cents"], f["has_surge"]) == (1.4, 20, 240, True)
    assert (f["toll_cents"], f["ride_class"], f["payment_type"]) == (410, "comfort", "cash")
    assert (f["pickup_in_petite_couronne"], f["pickup_in_paris"], f["dest_in_paris"]) == (True, False, True)
    assert (f["driver_lat"], f["driver_lng"]) == (48.8534, 2.3488)
    assert (f["is_public_holiday"], f["is_school_holiday"]) == (False, None)
    plain = _offer(client, session_id, assumption)["features"]
    assert (plain["is_public_holiday"], plain["has_surge"], plain["pickup_in_paris"]) == (True, False, None)
    eve = _offer(client, session_id, datetime(2026, 8, 14, 12, 0, tzinfo=PARIS))["features"]
    assert eve["is_eve_of_holiday"] is True


def test_french_public_holidays() -> None:
    from datetime import date

    from app.services.vector import calendar
    assert calendar.easter(2026) == date(2026, 4, 5)
    assert calendar.easter(2027) == date(2027, 3, 28)
    assert {d for d in calendar.public_holidays(2026) if d.month in (4, 5)} == {
        date(2026, 4, 6), date(2026, 5, 1), date(2026, 5, 8), date(2026, 5, 14), date(2026, 5, 25)}


def test_priority_offers_by_zone_and_hour(db) -> None:
    _, client, session_id = _setup(db)
    here = {"driver_lat": "48.853400", "driver_lng": "2.348800", "pickup_zone_code": "75004"}
    first = _offer(client, session_id, NOON, is_priority=True, **here)["features"]
    assert (first["is_priority"], first["zone_cell"], first["priority_offers_seen_cell_hour"]) == (True, "A-04-03", 0)
    assert first["priority_share_cell_hour"] is None                    # rien vu avant : pas de part
    for minutes, flag in ((5, False), (10, True), (15, False), (20, True)):
        _offer(client, session_id, NOON + timedelta(minutes=minutes), is_priority=flag, **here)
    _offer(client, session_id, NOON + timedelta(minutes=25), **here)    # étiquette non lue : ne compte pas
    later = _offer(client, session_id, NOON + timedelta(minutes=30), is_priority=False, **here)["features"]
    assert (later["priority_offers_seen_cell_hour"], later["priority_share_cell_hour"]) == (5, 0.6)
    night = _offer(client, session_id, NIGHT, is_priority=False, **here)["features"]
    assert night["priority_offers_seen_cell_hour"] == 0               # autre heure : autre propension
    stats = client.get(f"{BASE}/stats/priority").json()
    cell = next(r for r in stats["rows"] if r["by"] == "zone_cell" and r["time_block"] == "daytime")
    assert (cell["zone"], cell["offers"], cell["priority"], cell["share"]) == ("A-04-03", 6, 3, 0.5)
    code_night = next(r for r in stats["rows"] if r["by"] == "pickup_zone_code" and r["time_block"] == "night")
    assert (code_night["zone"], code_night["offers"], code_night["share"]) == ("75004", 1, None)  # trop peu d'offres
