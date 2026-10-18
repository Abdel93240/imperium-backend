"""PostgreSQL : « Où aller ? » Vector — recommandation de zone déterministe (doc 33 §4.1, §5)."""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("rides recommendations DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_vector  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.schemas.rides import ManualRevenueCreate, RecommendationRequest, SessionComplete, SessionStart  # noqa: E402
from app.schemas.vault import ImperiumVaultTransactionReverseRequest  # noqa: E402
from app.services.imperium import vault_transactions  # noqa: E402
from app.services.vector import recommendations, sessions  # noqa: E402
from app.services.vector.zones import zone_key  # noqa: E402

BASE = "/api/imperium/vector/recommendations"
PARIS = recommendations.PARIS
NOW = datetime(2026, 10, 14, 18, 30, tzinfo=PARIS)  # mercredi


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
        {"id": str(user_id), "email": f"reco-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_vector.router, prefix="/api/imperium/vector")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _session(db, user, start: datetime, rides: list[tuple[str, int]]) -> list[str]:
    session, _ = sessions.start_session(db, current_user=user, payload=SessionStart(), idempotency_key=uuid4().hex, now=start)
    ids = []
    for minute, (zone, amount) in enumerate(rides):
        entry = sessions.add_revenue(
            db, current_user=user, session_id=session.id,
            payload=ManualRevenueCreate(amount_cents=amount, zone=zone, occurred_at=start + timedelta(minutes=10 * minute)),
            idempotency_key=uuid4().hex, request_path="/t",
        )
        ids.append(str(entry.transaction_id))
    sessions.complete_session(db, current_user=user, session_id=session.id, payload=SessionComplete(),
                              idempotency_key=uuid4().hex, request_path="/t", now=start + timedelta(hours=2))
    return ids


def _history(db, user) -> list[str]:
    ids = []
    for weeks in (1, 2):
        start = NOW - timedelta(weeks=weeks, minutes=20)
        ids += _session(db, user, start, [("Bercy", 3000)] * 3 + [("Gare de Lyon", 2000)] * 3)
    _session(db, user, NOW - timedelta(weeks=3), [("Orly", 9000)] * 6)  # une seule session : pas comparée
    _session(db, user, NOW - timedelta(days=4), [("Bercy", 1000)] * 6)  # samedi : autre créneau
    return ids


def _recommend(db, user, current=None):
    read, _ = recommendations.recommend(db, current_user=user, payload=RecommendationRequest(current_zone=current),
                                        idempotency_key=uuid4().hex, now=NOW)
    return read


def test_zone_key_ignores_case_accents_and_spaces() -> None:
    assert zone_key("  Gare de  l'Est ") == zone_key("gare de l est") == "gare de l est"
    assert zone_key("Défense") == "defense" and zone_key("   ") is None


def test_moves_to_a_clearly_better_zone_and_states_what_is_missing(db) -> None:
    user = _user(db)
    _history(db, user)
    read = _recommend(db, user, "gare de lyon")
    assert (read.recommendation, read.zone, read.slot) == ("move_to_zone", "Bercy", "semaine, 17 h–20 h")
    assert [(z.zone, z.rides, z.sessions, z.average_ride_cents) for z in read.zones] == [
        ("Bercy", 6, 2, 3000), ("Gare de Lyon", 6, 2, 2000),
    ]
    assert read.reason == ("Aller vers Bercy : 6 courses notées à ce créneau, 30,00 € en moyenne. "
                           "Événements, trains, aéroports et trafic non pris en compte.")
    assert (str(read.confidence), read.hourly_rate_estimate_cents, read.missing_context) == (
        "0.15", None, ["events", "rail", "airport", "traffic"],
    )
    stay = _recommend(db, user, "BERCY")
    assert (stay.recommendation, stay.zone) == ("stay_here", "Bercy")
    event = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "rides.zone.recommended"))
    assert event.source_app == "vector"


def test_abstains_without_enough_history(db) -> None:
    user = _user(db)
    _session(db, user, NOW - timedelta(weeks=1), [("Bercy", 3000)] * 4)
    read = _recommend(db, user, "Bercy")
    assert (read.recommendation, read.zone, str(read.confidence)) == ("abstain", None, "0.00")
    assert read.reason.startswith("Haute incertitude, à toi de juger.")


def test_reversed_revenue_is_left_out(db) -> None:
    user = _user(db)
    ids = _history(db, user)
    for transaction_id in ids[:3]:  # trois courses Bercy de la première session annulées au Vault
        vault_transactions.reverse_vault_transaction(
            db, current_user=user, transaction_id=transaction_id,
            payload=ImperiumVaultTransactionReverseRequest(reason="Erreur"), idempotency_key=uuid4().hex,
            request_method="POST", request_path="/t",
        )
    read = _recommend(db, user, "gare de lyon")
    assert [z.zone for z in read.zones] == ["Gare de Lyon"]  # Bercy n'a plus qu'une session
    assert read.recommendation == "stay_here"


def test_routes_latest_detail_and_feedback(db) -> None:
    user = _user(db)
    client = _client(db, user)
    assert client.get(f"{BASE}/latest").json() is None
    key = {"Idempotency-Key": uuid4().hex}
    created = client.post(BASE, headers=key, json={"current_zone": "Bastille"})
    assert created.status_code == 201, created.text
    reco = created.json()
    assert reco["recommendation"] == "abstain"
    assert client.post(BASE, headers=key, json={"current_zone": "Bastille"}).status_code == 200
    assert client.post(BASE, headers=key, json={"current_zone": "Nation"}).status_code == 409
    assert client.get(f"{BASE}/latest").json()["id"] == reco["id"]
    assert client.get(f"{BASE}/{reco['id']}").json()["missing_context"] == ["events", "rail", "airport", "traffic"]
    feedback = {"useful": False, "ride_user_action": "ignored", "reason": "Zone calme"}
    first = client.post(f"{BASE}/{reco['id']}/feedback", json=feedback)
    assert (first.status_code, first.json()["feedback_useful"], first.json()["ride_user_action"]) == (200, False, "ignored")
    assert client.post(f"{BASE}/{reco['id']}/feedback", json=feedback).status_code == 200
    other = client.post(f"{BASE}/{reco['id']}/feedback", json={"useful": True})
    assert (other.status_code, other.json()["code"]) == (409, "RIDES_FEEDBACK_CONFLICT")
    assert client.get(f"{BASE}/{uuid4()}").status_code == 404
