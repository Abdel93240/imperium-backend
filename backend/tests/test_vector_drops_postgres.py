"""PostgreSQL : découpage fin (zones 1 / 3 / 10 km², créneaux de 10 min) et mesure après chaque dépose."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("vector drops DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_vector  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.rides import RidesDropObservation, RidesOffer  # noqa: E402
from app.services.vector import grid  # noqa: E402

BASE = "/api/imperium/vector"


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


def _client(db) -> TestClient:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"d-{user_id}@example.test"})
    db.commit()
    user = db.get(User, user_id)
    app = FastAPI()
    app.include_router(imperium_vector.router, prefix=BASE)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def _ride(client, session_id, offered: datetime, *, accepted: datetime, ended: datetime, earning: int,
          drop=("48.853400", "2.348800")) -> str:
    offer = client.post(f"{BASE}/sessions/{session_id}/offers", headers=_key(), json={
        "price_cents": earning, "estimated_duration_min": 20, "approach_duration_min": 5, "offered_at": offered.isoformat(),
        "source": "assistant", "destination_address": "Picpus, Paris"}).json()
    decided = client.post(f"{BASE}/offers/{offer['id']}/decision", json={"version": offer["version"], "decision": "accepted"}).json()
    arrived = accepted + timedelta(minutes=5)
    done = client.post(f"{BASE}/offers/{offer['id']}/outcome", json={
        "version": decided["version"], "actual_earning_cents": earning, "approach_minutes": 5, "wait_minutes": 1,
        "ride_minutes": max(1, int((ended - arrived).total_seconds() // 60) - 1), "record_revenue": False,
        "timeline": {"accepted": accepted.isoformat(), "arrived": arrived.isoformat(), "ended": ended.isoformat()},
        "dropoff_lat": drop[0], "dropoff_lng": drop[1]})
    assert done.status_code == 200, done.text
    return offer["id"]


def test_fine_grid_and_slots() -> None:
    assert grid.zone_at(48.853, 2.349).kind == "P"                    # Paris : 1 km²
    assert grid.zone_at(48.835, 2.240).kind == "V"                    # Boulogne : ville, 3 km²
    assert grid.zone_at(48.404, 2.700).kind == "C"                    # Fontainebleau : campagne, 10 km²
    assert grid.zone_at(49.0097, 2.5479).kind == "A"                  # Roissy-CDG : 1 km²
    assert grid.zone_at(48.853, 2.349) == grid.zone_at(48.8531, 2.3491)  # même case à quelques mètres près
    t = datetime(2026, 10, 23, 17, 46, tzinfo=grid.PARIS)
    assert (grid.slot_of(t), grid.slot_label(106), grid.day_type(t)) == (106, "17:40", "weekday")
    assert grid.day_type(datetime(2026, 8, 15, 12, 0, tzinfo=grid.PARIS)) == "holiday"


def test_measure_after_drop_until_next_ride(db) -> None:
    client = _client(db)
    session_id = client.post(f"{BASE}/sessions", headers=_key(), json={}).json()["id"]
    t0 = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=2)
    first = _ride(client, session_id, t0, accepted=t0 + timedelta(seconds=20), ended=t0 + timedelta(minutes=30), earning=2000)
    drop = db.scalar(select(RidesDropObservation).where(RidesDropObservation.offer_id == UUID(first)))
    assert (drop.status, drop.zone_source, drop.zone_code[:2], drop.slot) == ("open", "gps", "P:", grid.slot_of(drop.dropped_at))
    dropped = t0 + timedelta(minutes=30)
    # Une offre refusée 6 min après la dépose, puis une course acceptée 9 min après.
    refused = client.post(f"{BASE}/sessions/{session_id}/offers", headers=_key(), json={
        "price_cents": 900, "estimated_duration_min": 15, "offered_at": (dropped + timedelta(minutes=6)).isoformat()}).json()
    assert refused["features"]["slot_10min"] == grid.slot_of(dropped + timedelta(minutes=6))
    _ride(client, session_id, dropped + timedelta(minutes=9), accepted=dropped + timedelta(minutes=9),
          ended=dropped + timedelta(minutes=49), earning=3000)
    db.expire_all()
    closed = db.get(RidesDropObservation, drop.id)
    assert (closed.status, closed.offers_seen, float(closed.wait_first_offer_min), float(closed.wait_to_accept_min)) == (
        "closed", 2, 6.0, 9.0)
    # 30 € pour 9 min d'attente + 40 min mobilisées = 49 min → 36,73 €/h
    assert (closed.next_earning_cents, closed.next_mobilized_min, closed.cycle_hourly_cents) == (3000, 40, 3673)
    client.post(f"{BASE}/sessions/{session_id}/pause")                 # pause : la mesure suivante s'arrête
    db.expire_all()
    last = db.scalars(select(RidesDropObservation).where(RidesDropObservation.session_id == UUID(session_id))
                      .order_by(RidesDropObservation.dropped_at.desc())).first()
    assert (last.status, last.closed_reason) == ("interrupted", "pause")


def test_paid_cancellation_counts_as_earning_without_a_drop(db) -> None:
    client = _client(db)
    session_id = client.post(f"{BASE}/sessions", headers=_key(), json={}).json()["id"]
    t0 = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=20)
    offer = client.post(f"{BASE}/sessions/{session_id}/offers", headers=_key(), json={
        "price_cents": 957, "estimated_duration_min": 11, "approach_duration_min": 1, "offered_at": t0.isoformat(),
        "source": "assistant"}).json()
    decided = client.post(f"{BASE}/offers/{offer['id']}/decision", json={
        "version": offer["version"], "decision": "accepted", "note": "annulée par le passager"}).json()
    body = {"version": decided["version"], "actual_earning_cents": 532, "approach_minutes": 2, "wait_minutes": 5,
            "ride_minutes": 0, "record_revenue": False, "price_source": "cancellation_fee",
            "timeline": {"accepted": t0.isoformat(), "ended": (t0 + timedelta(minutes=7)).isoformat()}}
    assert client.post(f"{BASE}/offers/{offer['id']}/outcome", json=body).status_code == 422   # sans course ni annulation
    done = client.post(f"{BASE}/offers/{offer['id']}/outcome", json={**body, "cancelled": True})
    assert done.status_code == 200, done.text
    # Cas réel du 24/10 : 5,32 € de frais pour 7 min mobilisées → 45,60 €/h ; aucune mesure de zone à l'annulation.
    assert (done.json()["actual_earning_cents"], done.json()["actual_hourly_rate_cents"]) == (532, 4560)
    db.expire_all()
    assert db.get(RidesOffer, UUID(offer["id"])).outcome["cancelled"] is True
    assert db.scalar(select(RidesDropObservation).where(RidesDropObservation.offer_id == UUID(offer["id"]))) is None
