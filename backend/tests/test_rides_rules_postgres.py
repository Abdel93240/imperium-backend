"""PostgreSQL : règles métier Vector et signal « règles seules » (doc 57 §3.1, §4, §5.7)."""
from __future__ import annotations

from datetime import datetime
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
        ("R1", "red", True), ("R2", "red", True), ("R7", "green", True), ("R8", "green", True),
    ]
    assert body["not_coded"] == ["R3", "R4", "R5", "R6", "R9", "R10", "R11"]


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
