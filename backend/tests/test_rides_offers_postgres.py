"""PostgreSQL : courses proposées Vector — variables, décision, résultat réel (doc 57 §5–§6, doc 33 §8)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("rides offers DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_vector  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.rides import RidesOffer, RidesRevenueEntry  # noqa: E402
from app.models.vault import ImperiumVaultTransaction  # noqa: E402
from app.schemas.rides import RideOfferCreate  # noqa: E402
from app.services.vector import offers  # noqa: E402

BASE = "/api/imperium/vector"
PARIS = offers.PARIS


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
        {"id": str(user_id), "email": f"offers-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_vector.router, prefix=BASE)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def _session(client, **payload) -> dict:
    return client.post(f"{BASE}/sessions", headers=_key(), json=payload).json()


def _offer(client, session_id, **payload) -> dict:
    body = {"price_cents": 2400, "estimated_duration_min": 30, "distance_km": "12.00", "approach_duration_min": 6,
            "pickup_zone": "Gare du Nord", "destination_zone": "La Défense", **payload}
    response = client.post(f"{BASE}/sessions/{session_id}/offers", headers=_key(), json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_offer_features_without_verdict(db) -> None:
    client = _client(db, _user(db))
    session = _session(client, target_ca_cents=20000)
    offered_at = datetime(2026, 10, 16, 23, 15, tzinfo=PARIS)  # vendredi soir
    key = _key()
    body = {"price_cents": 2400, "estimated_duration_min": 30, "distance_km": "12.00", "approach_duration_min": 6,
            "pickup_zone": "Gare du Nord", "destination_zone": "La Défense", "offered_at": offered_at.isoformat()}
    created = client.post(f"{BASE}/sessions/{session['id']}/offers", headers=key, json=body)
    assert created.status_code == 201, created.text
    offer = created.json()
    features = offer["features"]
    assert (features["hourly_rate_offered_cents"], features["price_per_km_cents"], features["total_ride_time_min"]) == (4800, 200, 36)
    assert (features["time_block"], features["is_friday_night"], features["is_weekend"], features["day_of_week"]) == (
        "late_evening", True, False, 4,
    )
    assert (features["pickup_zone_key"], features["destination_zone_key"]) == ("gare du nord", "la defense")
    assert not any("prayer" in name or "ramadan" in name or "fatigue" in name for name in features)
    assert (offer["signal"], offer["decision"], offer["source"]) == (None, None, "manual")
    assert client.post(f"{BASE}/sessions/{session['id']}/offers", headers=key, json=body).status_code == 200
    assert client.post(f"{BASE}/sessions/{session['id']}/offers", headers=key, json={**body, "price_cents": 1}).status_code == 409


def test_decision_is_recorded_and_versioned(db) -> None:
    user = _user(db)
    client = _client(db, user)
    offer = _offer(client, _session(client)["id"])
    refused = client.post(f"{BASE}/offers/{offer['id']}/decision", json={"version": 1, "decision": "refused", "note": "trop loin"})
    assert (refused.json()["decision"], refused.json()["version"]) == ("refused", 2)
    assert client.post(f"{BASE}/offers/{offer['id']}/decision",
                       json={"version": 1, "decision": "refused", "note": "trop loin"}).status_code == 200  # rejeu
    stale = client.post(f"{BASE}/offers/{offer['id']}/decision", json={"version": 1, "decision": "accepted"})
    assert (stale.status_code, stale.json()["code"]) == (409, "RIDES_OFFER_VERSION_CONFLICT")
    assert client.post(f"{BASE}/offers/{offer['id']}/outcome",
                       json={"version": 2, "actual_earning_cents": 2400, "approach_minutes": 6, "ride_minutes": 30}).status_code == 409
    event = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "rides.ride.refused"))
    assert event.payload["hourly_rate_offered_cents"] == 4800 and "trop loin" not in str(event.payload)


def test_outcome_gives_the_real_hourly_rate_and_the_vault_revenue(db) -> None:
    user = _user(db)
    client = _client(db, user)
    session = _session(client)
    offer = _offer(client, session["id"])
    client.post(f"{BASE}/offers/{offer['id']}/decision", json={"version": 1, "decision": "accepted"})
    payload = {"version": 2, "actual_earning_cents": 2400, "approach_minutes": 6, "wait_minutes": 3, "ride_minutes": 38,
               "return_minutes": 13}
    done = client.post(f"{BASE}/offers/{offer['id']}/outcome", json=payload)
    assert done.status_code == 200, done.text
    body = done.json()
    assert (body["mobilized_minutes"], body["actual_hourly_rate_cents"]) == (60, 2400)  # 24 € en 60 min
    transaction = db.get(ImperiumVaultTransaction, body["revenue_transaction_id"])
    assert (transaction.transaction_type, transaction.amount_cents, transaction.category) == ("income", 2400, "vtc")
    assert db.scalar(select(RidesRevenueEntry.zone).where(RidesRevenueEntry.transaction_id == transaction.id)) == "Gare du Nord"
    assert client.post(f"{BASE}/offers/{offer['id']}/outcome", json=payload).json()["revenue_transaction_id"] == str(transaction.id)
    assert client.post(f"{BASE}/offers/{offer['id']}/outcome", json={**payload, "ride_minutes": 40}).status_code == 409
    assert client.post(f"{BASE}/offers/{offer['id']}/decision", json={"version": 3, "decision": "refused"}).status_code == 409
    assert client.get(f"{BASE}/sessions/current").json()["session"]["kpis"]["revenue_cents"] == 2400
    second = _offer(client, session["id"])
    assert (second["features"]["session_rides_done"], second["features"]["last_ride_destination_zone_key"]) == (1, "la defense")


def test_outcome_without_revenue_after_the_session_is_closed(db) -> None:
    client = _client(db, _user(db))
    session = _session(client)
    offer = _offer(client, session["id"])
    client.post(f"{BASE}/offers/{offer['id']}/decision", json={"version": 1, "decision": "accepted"})
    client.post(f"{BASE}/sessions/{session['id']}/complete", headers=_key(), json={})
    payload = {"version": 2, "actual_earning_cents": 1500, "approach_minutes": 5, "ride_minutes": 20}
    assert client.post(f"{BASE}/offers/{offer['id']}/outcome", json=payload).status_code == 409
    late = client.post(f"{BASE}/offers/{offer['id']}/outcome", json={**payload, "record_revenue": False})
    assert (late.status_code, late.json()["actual_hourly_rate_cents"], late.json()["revenue_transaction_id"]) == (200, 3600, None)
    assert client.post(f"{BASE}/sessions/{session['id']}/offers", headers=_key(), json={"price_cents": 1000}).status_code == 409


def test_training_summary_counts_only_real_outcomes(db) -> None:
    user = _user(db)
    client = _client(db, user)
    session = _session(client)
    for earning, minutes in ((1800, 30), (3000, 60), (2000, 20)):
        offer = _offer(client, session["id"])
        client.post(f"{BASE}/offers/{offer['id']}/decision", json={"version": 1, "decision": "accepted"})
        client.post(f"{BASE}/offers/{offer['id']}/outcome",
                    json={"version": 2, "actual_earning_cents": earning, "approach_minutes": 0, "ride_minutes": minutes,
                          "record_revenue": False})
    refused = _offer(client, session["id"])
    client.post(f"{BASE}/offers/{refused['id']}/decision", json={"version": 1, "decision": "refused"})
    _offer(client, session["id"])
    summary = client.get(f"{BASE}/training-summary").json()
    assert (summary["offers"], summary["decided"], summary["accepted"], summary["refused"], summary["with_outcome"]) == (5, 4, 3, 1, 3)
    assert (summary["median_hourly_rate_cents"], summary["phase"]) == (3600, "cold_start")  # 36, 30, 60 €/h
    assert summary["message"] == "3 courses avec résultat réel ; le modèle n'est pas encore entraîné (phase suivante à 100)."
    assert len(client.get(f"{BASE}/sessions/{session['id']}/offers").json()["items"]) == 5


def test_future_offer_is_refused(db) -> None:
    user = _user(db)
    client = _client(db, user)
    session = _session(client)
    with pytest.raises(offers.OfferInputError):
        offers.record_offer(db, current_user=user, session_id=session["id"],
                            payload=RideOfferCreate(price_cents=1000, offered_at=datetime.now(PARIS) + timedelta(hours=1)),
                            idempotency_key=uuid4().hex)
    assert client.get(f"{BASE}/offers/{uuid4()}").status_code == 404


def test_pause_resume_and_ride_counters(db) -> None:
    """Kit Vector : pause/reprise (durée active hors pauses), courses faites = résultat réel, refusées = décision."""
    from datetime import UTC, datetime, timedelta

    from app.services.vector import sessions as session_service

    user = _user(db)
    client = _client(db, user)
    session = _session(client)
    sid = session["id"]
    accepted, refused, pending = (_offer(client, sid) for _ in range(3))
    client.post(f"{BASE}/offers/{accepted['id']}/decision", json={"version": 1, "decision": "accepted"})
    client.post(f"{BASE}/offers/{accepted['id']}/outcome", json={"version": 2, "actual_earning_cents": 1500,
                                                                  "approach_minutes": 5, "ride_minutes": 20})
    client.post(f"{BASE}/offers/{refused['id']}/decision", json={"version": 1, "decision": "refused"})
    client.post(f"{BASE}/offers/{pending['id']}/decision", json={"version": 1, "decision": "accepted"})  # pas encore réalisée
    kpis = client.get(f"{BASE}/sessions/current").json()["session"]["kpis"]
    assert (kpis["rides_done"], kpis["rides_refused"], kpis["revenue_cents"]) == (1, 1, 1500)

    start = datetime.now(UTC)
    paused = session_service.pause_session(db, current_user=user, session_id=sid, now=start)
    assert paused.status == "paused" and paused.paused_at is not None
    assert session_service.pause_session(db, current_user=user, session_id=sid, now=start + timedelta(minutes=1)).paused_at == paused.paused_at
    assert client.get(f"{BASE}/sessions/current").json()["session"]["status"] == "paused"
    assert client.post(f"{BASE}/sessions/{sid}/offers", headers=_key(), json={"platform": "uber", "price_cents": 1000,
                                                                              "ride_type": "immediate"}).status_code == 409
    resumed = session_service.resume_session(db, current_user=user, session_id=sid, now=start + timedelta(minutes=30))
    assert resumed.status == "active"
    again = session_service.pause_session(db, current_user=user, session_id=sid, now=start + timedelta(minutes=40))
    done = session_service.complete_session(
        db, current_user=user, session_id=sid, payload=session_service.SessionComplete(), idempotency_key="end",
        request_path="/end", now=start + timedelta(minutes=50))
    assert again.status == "paused" and done.status == "completed" and done.paused_at is None
    # 30 min + 10 min de pause retirées de la durée active.
    assert done.kpis.elapsed_minutes - done.kpis.active_minutes == 40
    assert client.post(f"{BASE}/sessions/{sid}/pause").status_code == 409
    assert client.post(f"{BASE}/sessions", headers=_key(), json={}).status_code == 201  # plus de session ouverte


def test_outcome_keeps_the_timeline_read_on_bolt_screens(db) -> None:
    client = _client(db, _user(db))
    session_id = _session(client)["id"]
    offer = _offer(client, session_id, price_cents=2462, estimated_duration_min=57, source="assistant")
    decided = client.post(f"{BASE}/offers/{offer['id']}/decision", json={"version": offer["version"], "decision": "accepted"}).json()
    t0 = datetime(2026, 10, 23, 9, 30, tzinfo=UTC)
    body = {"version": decided["version"], "actual_earning_cents": 2462, "approach_minutes": 5, "wait_minutes": 2,
            "ride_minutes": 57, "record_revenue": False, "payment": "card", "price_source": "ride_screen",
            "timeline": {"accepted": t0.isoformat(), "arrived": (t0 + timedelta(minutes=5)).isoformat(),
                         "started": (t0 + timedelta(minutes=7)).isoformat(), "ended": (t0 + timedelta(minutes=64)).isoformat()},
            "pickup_lat": "48.835000", "pickup_lng": "2.250000", "dropoff_lat": "48.884500", "dropoff_lng": "2.595400"}
    done = client.post(f"{BASE}/offers/{offer['id']}/outcome", json=body)
    assert done.status_code == 200, done.text
    row = db.get(RidesOffer, UUID(offer["id"]))
    assert row.outcome["timeline"]["arrived"] == "2026-10-23T09:35:00+00:00"
    assert (row.outcome["payment"], row.outcome["price_source"], row.outcome["dropoff_zone_cell"][:1]) == ("card", "ride_screen", "B")
    assert row.mobilized_minutes == 64
