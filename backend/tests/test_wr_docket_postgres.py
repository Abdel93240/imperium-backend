"""PostgreSQL : docket du WR — priorité, portage, décision forcée, rouge (spec WR §3.1, §7, §12)."""
from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("wr docket DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import wr  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.toolbox import Notification  # noqa: E402
from app.models.wr import WrDocketItem  # noqa: E402
from app.services.wr import docket  # noqa: E402

BASE = "/api/wr/docket"


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
        {"id": str(user_id), "email": f"docket-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(wr.router, prefix="/api/wr")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _item(db, user, **overrides) -> WrDocketItem:
    fields = {
        "item_type": "anomaly", "domain": "vault", "title_fr": "Dépenses carburant inhabituelles",
        "payload": {"signal": "vault.fuel"}, "evidence_refs": {"events": ["evt_x"]},
        "impact_estimate": 3, "source_worker": "w4",
    }
    fields.update(overrides)
    item = docket.create_item(db, current_user=user, **fields)
    db.commit()
    return item


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def test_priority_formula_follows_the_spec() -> None:
    assert docket.compute_priority(severity="normal", impact_estimate=3, age_days=0, confidence=None, halflife_days=14) == pytest.approx(3)
    # rouge ×4, confiance 50 → facteur 0,75, fraîcheur exp(−14/14)
    assert docket.compute_priority(severity="red", impact_estimate=5, age_days=14, confidence=50, halflife_days=14) == pytest.approx(
        4 * 5 * math.exp(-1) * 0.75
    )
    # une basse confiance monte moins qu'une haute
    low = docket.compute_priority(severity="elevated", impact_estimate=2, age_days=1, confidence=10, halflife_days=14)
    high = docket.compute_priority(severity="elevated", impact_estimate=2, age_days=1, confidence=90, halflife_days=14)
    assert low < high


def test_create_item_validates_and_emits_an_event(db) -> None:
    user = _user(db)
    item = _item(db, user, confidence=80)
    assert (item.status, item.consecutive_defers, item.force_decision) == ("pending", 0, False)
    assert float(item.priority) == pytest.approx(3 * (0.5 + 80 / 200))
    event = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "planning.docket.item_created"))
    assert event.payload == {"item_id": str(item.id), "item_type": "anomaly", "status": "pending", "defers": 0}
    with pytest.raises(docket.DocketValidationError):
        docket.create_item(db, current_user=user, item_type="gossip", domain="vault", title_fr="x", payload={},
                           evidence_refs={}, impact_estimate=3, source_worker="w4")
    with pytest.raises(docket.DocketValidationError):
        docket.create_item(db, current_user=user, item_type="anomaly", domain="vault", title_fr="x", payload={},
                           evidence_refs={}, impact_estimate=6, source_worker="w4")
    db.rollback()


def test_red_item_notifies_without_applying_anything(db) -> None:
    user = _user(db)
    item = _item(db, user, severity="red", item_type="red_flag_ref", title_fr="Choc plan")
    note = db.scalar(select(Notification).where(Notification.ref_type == "wr_docket_item", Notification.ref_id == item.id))
    assert (note.severity, note.domain) == ("red", "wr")
    red_event = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "planning.docket.red_notified"))
    assert red_event.payload == {"item_id": str(item.id), "severity": "red"}
    assert item.status == "pending"  # le rouge notifie et attend la décision
    red = _client(db, user).get(f"{BASE}/red").json()
    assert [row["id"] for row in red["items"]] == [str(item.id)]


def test_list_filters_and_orders_by_priority(db) -> None:
    user = _user(db)
    low = _item(db, user, impact_estimate=1)
    high = _item(db, user, impact_estimate=5, item_type="pattern_new")
    old = _item(db, user, impact_estimate=5)
    old.created_at = datetime.now(UTC) - timedelta(days=60)  # fraîcheur décotée
    db.commit()
    other = _user(db)
    _item(db, other)
    client = _client(db, user)
    body = client.get(BASE).json()
    # 5 × e^(−60/14) ≈ 0,07 : l'item ancien passe sous l'impact 1 tout frais.
    assert [row["id"] for row in body["items"]] == [str(high.id), str(low.id), str(old.id)]
    assert body["items"][2]["priority"] == pytest.approx(5 * math.exp(-60 / 14), rel=1e-3)
    typed = client.get(BASE, params={"type": "pattern_new"}).json()
    assert [row["id"] for row in typed["items"]] == [str(high.id)]
    assert client.get(BASE, params={"status": "validated"}).json()["items"] == []
    assert client.get(BASE, params={"status": "bogus"}).status_code == 422


def test_defers_force_a_decision(db) -> None:
    user = _user(db)
    client = _client(db, user)
    item = _item(db, user)
    url = f"{BASE}/{item.id}/decision"
    for expected in (1, 2):
        body = client.post(url, headers=_key(), json={"decision": "deferred"}).json()
        assert (body["status"], body["consecutive_defers"], body["force_decision"]) == ("deferred", expected, False)
    third = client.post(url, headers=_key(), json={"decision": "deferred"}).json()
    assert (third["consecutive_defers"], third["force_decision"]) == (3, True)
    forced = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "planning.docket.item_forced"))
    assert forced.payload["defers"] == 3
    # Décision forcée : seulement trancher ou archiver, et l'item remonte en tête.
    again = client.post(url, headers=_key(), json={"decision": "deferred"})
    assert (again.status_code, again.json()["code"]) == (409, "DOCKET_DECISION_FORCED")
    _item(db, user, impact_estimate=5)
    assert client.get(BASE).json()["items"][0]["id"] == str(item.id)
    archived = client.post(url, headers=_key(), json={"decision": "archived"}).json()
    assert archived["status"] == "archived" and archived["decided_at"] is not None


def test_decision_rules_and_idempotency(db) -> None:
    user = _user(db)
    client = _client(db, user)
    item = _item(db, user)
    url = f"{BASE}/{item.id}/decision"
    assert client.post(url, json={"decision": "validated"}).status_code == 400  # Idempotency-Key requise
    bad = client.post(url, headers=_key(), json={"decision": "deferred", "modified_payload": {"x": 1}})
    assert bad.status_code == 422  # modification réservée à la validation
    key = _key()
    payload = {"decision": "validated", "decision_note": "ok mais seuil 50", "modified_payload": {"signal": "vault.fuel", "threshold": 50}}
    first = client.post(url, headers=key, json=payload)
    assert first.status_code == 200, first.text
    assert (first.json()["status"], first.json()["payload"]["threshold"], first.json()["decision_note"]) == ("validated", 50, "ok mais seuil 50")
    replay = client.post(url, headers=key, json=payload)
    assert replay.json() == first.json()
    assert client.post(url, headers=key, json={"decision": "refused"}).status_code == 409  # même clé, autre corps
    done = client.post(url, headers=_key(), json={"decision": "refused"})
    assert (done.status_code, done.json()["code"]) == (409, "DOCKET_ALREADY_DECIDED")
    decided = db.scalars(select(Event).where(Event.user_id == user.id, Event.event_type == "planning.docket.item_decided")).all()
    assert [event.payload["status"] for event in decided] == ["validated"]  # rejeu et refus tardif : rien de plus
    assert _client(db, _user(db)).post(url, headers=_key(), json={"decision": "refused"}).status_code == 404
    assert client.post(f"{BASE}/{uuid4()}/decision", headers=_key(), json={"decision": "refused"}).status_code == 404


def test_reprioritize_persists_the_fresh_priority(db) -> None:
    user = _user(db)
    item = _item(db, user, impact_estimate=4)
    item.created_at = datetime.now(UTC) - timedelta(days=14)
    db.commit()
    assert docket.reprioritize(db, current_user=user) == 1
    db.commit()
    db.refresh(item)
    assert float(item.priority) == pytest.approx(4 * math.exp(-1), rel=1e-3)
