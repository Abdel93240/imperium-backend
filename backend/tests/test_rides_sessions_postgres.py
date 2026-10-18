"""PostgreSQL : sessions VTC Vector — démarrage, saisies écrites au Vault, dépose, clôture (doc 59 §14)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("rides sessions DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_vector  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.vault import ImperiumVaultTransaction  # noqa: E402
from app.schemas.vault import ImperiumVaultTransactionReverseRequest  # noqa: E402
from app.services.imperium import vault_transactions  # noqa: E402
from app.services.vault.weekly import DEFAULT_CATEGORY_MAP, build_weekly_summary_detail  # noqa: E402

BASE = "/api/imperium/vector/sessions"


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
        {"id": str(user_id), "email": f"rides-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_vector.router, prefix="/api/imperium/vector")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def _start(client, **payload) -> dict:
    response = client.post(BASE, headers=_key(), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_start_one_active_session(db) -> None:
    user = _user(db)
    client = _client(db, user)
    assert client.get(f"{BASE}/current").json() == {"session": None}
    key = _key()
    first = client.post(BASE, headers=key, json={"target_ca_cents": 25000, "strategic_direction": "retour Paris"})
    assert first.status_code == 201
    body = first.json()
    assert (body["status"], body["kpis"]["revenue_cents"], body["kpis"]["objective_reached"]) == ("active", 0, False)
    assert client.post(BASE, headers=key, json={"target_ca_cents": 25000, "strategic_direction": "retour Paris"}).status_code == 200
    second = client.post(BASE, headers=_key(), json={})
    assert (second.status_code, second.json()["code"], second.json()["current"]["id"]) == (409, "RIDES_SESSION_STATE", body["id"])
    assert client.post(BASE, headers=_key(), json={"mission_id": str(uuid4())}).status_code == 409  # session déjà active
    event = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "rides.session.started"))
    assert (event.payload["target_ca_cents"], event.source_app) == (25000, "vector")


def test_unknown_mission_is_refused(db) -> None:
    client = _client(db, _user(db))
    assert client.post(BASE, headers=_key(), json={"mission_id": str(uuid4())}).status_code == 422


def test_revenue_and_expenses_go_to_the_vault_as_business(db) -> None:
    user = _user(db)
    client = _client(db, user)
    session = _start(client, target_ca_cents=10000)
    key = _key()
    revenue = client.post(f"{BASE}/{session['id']}/manual-revenue", headers=key, json={"amount_cents": 6000, "zone": "Orly"})
    assert revenue.status_code == 201, revenue.text
    assert client.post(f"{BASE}/{session['id']}/manual-revenue", headers=key,
                       json={"amount_cents": 6000, "zone": "Orly"}).json()["transaction_id"] == revenue.json()["transaction_id"]
    client.post(f"{BASE}/{session['id']}/manual-revenue", headers=_key(), json={"amount_cents": 5000})
    fuel = client.post(f"{BASE}/{session['id']}/manual-expense", headers=_key(), json={"amount_cents": 3000, "category": "carburant"})
    toll = client.post(f"{BASE}/{session['id']}/manual-expense", headers=_key(), json={"amount_cents": 700, "category": "peage"})
    kpis = toll.json()["session"]["kpis"]
    assert (kpis["revenue_cents"], kpis["expense_cents"], kpis["net_cents"], kpis["revenue_entries"], kpis["expense_entries"]) == (
        11000, 3700, 7300, 2, 2,
    )
    assert (kpis["target_progress"], kpis["objective_reached"]) == ("1.10", True)
    transactions = list(db.scalars(select(ImperiumVaultTransaction).where(ImperiumVaultTransaction.user_id == user.id)))
    by_id = {str(t.id): t for t in transactions}
    assert (by_id[revenue.json()["transaction_id"]].category, by_id[revenue.json()["transaction_id"]].note) == ("vtc", "Zone : Orly")
    assert (by_id[toll.json()["transaction_id"]].category, by_id[toll.json()["transaction_id"]].note) == ("charges", "Péage")
    assert {t.source for t in transactions} == {"vector_manual"}
    detail = build_weekly_summary_detail(transactions, category_map=DEFAULT_CATEGORY_MAP)
    assert str(detail["weekly_business_profit"]) == "73.00"
    assert fuel.status_code == 201


def test_a_reversed_vault_entry_no_longer_counts(db) -> None:
    user = _user(db)
    client = _client(db, user)
    session = _start(client)
    entry = client.post(f"{BASE}/{session['id']}/manual-revenue", headers=_key(), json={"amount_cents": 4000}).json()
    vault_transactions.reverse_vault_transaction(
        db, current_user=user, transaction_id=entry["transaction_id"],
        payload=ImperiumVaultTransactionReverseRequest(reason="Saisie en double"), idempotency_key=uuid4().hex,
        request_method="POST", request_path="/t",
    )
    assert client.get(f"{BASE}/current").json()["session"]["kpis"]["revenue_cents"] == 0


def test_drop_zone_and_future_time(db) -> None:
    user = _user(db)
    client = _client(db, user)
    session = _start(client)
    key = _key()
    drop = client.post(f"{BASE}/{session['id']}/drop-zone", headers=key,
                       json={"zone": "Gare de Lyon", "latitude": "48.844", "longitude": "2.374", "real_duration_minutes": 34})
    assert drop.status_code == 201, drop.text
    assert client.post(f"{BASE}/{session['id']}/drop-zone", headers=key,
                       json={"zone": "Gare de Lyon", "latitude": "48.844", "longitude": "2.374", "real_duration_minutes": 34}).status_code == 200
    assert client.post(f"{BASE}/{session['id']}/drop-zone", headers=_key(), json={"zone": "X", "latitude": "1"}).status_code == 422
    assert [z["zone"] for z in client.get(f"{BASE}/{session['id']}/drop-zones").json()] == ["Gare de Lyon"]
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    assert client.post(f"{BASE}/{session['id']}/manual-revenue", headers=_key(),
                       json={"amount_cents": 100, "occurred_at": future}).status_code == 422
    assert db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "rides.drop_zone.recorded")) is not None


def test_update_needs_version(db) -> None:
    client = _client(db, _user(db))
    session = _start(client, target_ca_cents=20000)
    stale = client.patch(f"{BASE}/{session['id']}", headers=_key(), json={"version": 5, "target_ca_cents": 15000})
    assert (stale.status_code, stale.json()["code"]) == (409, "RIDES_SESSION_VERSION_CONFLICT")
    updated = client.patch(f"{BASE}/{session['id']}", headers=_key(), json={"version": 1, "target_ca_cents": 15000})
    assert (updated.json()["target_ca_cents"], updated.json()["version"]) == (15000, 2)


def test_completion_freezes_the_figures(db) -> None:
    user = _user(db)
    client = _client(db, user)
    session = _start(client, target_ca_cents=20000)
    revenue_key = _key()
    client.post(f"{BASE}/{session['id']}/manual-revenue", headers=revenue_key, json={"amount_cents": 12000})
    key = _key()
    done = client.post(f"{BASE}/{session['id']}/complete", headers=key, json={"review_note": "Soirée calme"})
    assert done.status_code == 200, done.text
    body = done.json()
    assert (body["status"], body["kpis"]["revenue_cents"], body["kpis"]["objective_reached"], body["review_note"]) == (
        "completed", 12000, False, "Soirée calme",
    )
    assert client.post(f"{BASE}/{session['id']}/complete", headers=key, json={"review_note": "Soirée calme"}).json() == body
    closed = client.post(f"{BASE}/{session['id']}/manual-revenue", headers=_key(), json={"amount_cents": 500})
    assert closed.status_code == 409
    replay = client.post(f"{BASE}/{session['id']}/manual-revenue", headers=revenue_key, json={"amount_cents": 12000})
    assert replay.status_code == 201  # rejeu d'une saisie faite avant la clôture
    assert client.get(f"{BASE}/{session['id']}").json()["kpis"]["revenue_cents"] == 12000
    assert client.get(f"{BASE}/current").json() == {"session": None}
    assert len(client.get(BASE).json()["items"]) == 1
    event = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "rides.session.ended"))
    assert (event.payload["revenue_cents"], event.payload["objective_reached"]) == (12000, False)
    assert client.post(BASE, headers=_key(), json={}).status_code == 201  # nouvelle session possible
