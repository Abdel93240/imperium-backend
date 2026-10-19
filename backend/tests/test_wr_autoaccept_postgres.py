"""PostgreSQL : classes d'auto-acceptation du docket et contrôles (spec WR §9 P4, §13.8)."""
from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("wr autoaccept DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, delete, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import wr  # noqa: E402
from app.models import ai  # noqa: E402,F401 - FK de la session WR vers ai_tasks
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.toolbox import AIAuditSample, AISlotTransition  # noqa: E402
from app.models.wr import WrAutoacceptClass, WrDocketItem  # noqa: E402
from app.schemas.wr import DocketDecisionRequest  # noqa: E402
from app.services.ai import audit_loop  # noqa: E402
from app.services.wr import autoaccept, docket  # noqa: E402

PARIS = ZoneInfo("Europe/Paris")
SLOT = "test.autoaccept_slot"
NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)  # semaine en cours = lundi 19/10
CLOSED_WEEKS = (date(2026, 10, 12), date(2026, 10, 5), date(2026, 9, 28))


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


def _cleanup(session: Session) -> None:
    class_ids = select(WrAutoacceptClass.id).where(WrAutoacceptClass.slot_code == SLOT)
    session.execute(delete(WrDocketItem).where(WrDocketItem.autoaccept_class_id.in_(class_ids)))
    session.execute(delete(WrAutoacceptClass).where(WrAutoacceptClass.slot_code == SLOT))
    session.execute(delete(AIAuditSample).where(AIAuditSample.slot_code == SLOT))
    session.execute(delete(AISlotTransition).where(AISlotTransition.slot_code == SLOT))
    session.commit()


@pytest.fixture()
def db(engine):
    with Session(engine) as session:
        _cleanup(session)
        session.add(AISlotTransition(slot_code=SLOT, domain="wr", tier="local_default", audit_sample_pct=100,
                                     agreement_target_pct=92))
        session.commit()
        yield session
        session.rollback()
        _cleanup(session)


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"autoacc-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _agreement(db, *, weeks=CLOSED_WEEKS, agreed: int = 6) -> None:
    for week in weeks:
        at = datetime.combine(week + timedelta(days=1), time(9), tzinfo=PARIS)
        for _ in range(agreed):
            sample, _ = audit_loop.record_sample(db, slot_code=SLOT, run_ref=uuid4(), local_output={}, cloud_output={},
                                                 cloud_model="cloud-role", agreement=True)
            sample.created_at = at
    db.commit()


def _class(db, user, **fields) -> WrAutoacceptClass:
    values = {"item_type": "pattern_new", "domain": None, "slot_code": SLOT, "min_confidence": 70,
              "rationale_fr": "Fiable depuis un mois."}
    values.update(fields)
    row = WrAutoacceptClass(user_id=user.id, created_at=NOW - timedelta(days=1), **values)
    db.add(row)
    db.commit()
    return row


def _item(db, user, **fields) -> WrDocketItem:
    values = {"item_type": "pattern_new", "domain": "wr", "title_fr": "Motif", "payload": {"m": 1},
              "evidence_refs": {"events": ["e1"]}, "impact_estimate": 3, "source_worker": "w3", "confidence": 80}
    values.update(fields)
    item = docket.create_item(db, current_user=user, now=NOW, **values)
    db.commit()
    return item


def test_item_meeting_an_active_class_is_validated_at_once(db, monkeypatch) -> None:
    monkeypatch.setattr(autoaccept, "in_spotcheck", lambda _db, _id: False)
    user = _user(db)
    _agreement(db)
    row = _class(db, user)
    item = _item(db, user)
    assert (item.status, item.decided_at, item.autoaccept_class_id) == ("validated", NOW, row.id)
    event = db.scalar(select(Event).where(Event.event_type == "planning.docket.item_autoaccepted",
                                          Event.payload["item_id"].astext == str(item.id)))
    assert event.payload["class_id"] == str(row.id) and event.payload["spotcheck_item_id"] is None
    assert [entry.id for entry in docket.list_items(db, current_user=user, status="pending", now=NOW)] == []  # rien à trancher


def test_conditions_that_keep_an_item_pending(db, monkeypatch) -> None:
    monkeypatch.setattr(autoaccept, "in_spotcheck", lambda _db, _id: False)
    user = _user(db)
    _class(db, user, domain="pulse")
    _agreement(db, weeks=CLOSED_WEEKS[:2])  # deux semaines seulement
    assert _item(db, user, domain="pulse").status == "pending"
    _agreement(db, weeks=CLOSED_WEEKS[2:])
    assert _item(db, user, domain="pulse").status == "validated"
    assert _item(db, user, domain="wr").status == "pending"  # autre domaine
    assert _item(db, user, domain="pulse", confidence=60).status == "pending"  # sous le seuil
    assert _item(db, user, domain="pulse", confidence=None).status == "pending"  # sans verdict
    assert _item(db, user, domain="pulse", severity="red").status == "pending"  # jamais un rouge
    assert _item(db, user, domain="pulse", item_type="anomaly").status == "pending"  # autre type
    assert _item(db, _user(db), domain="pulse").status == "pending"  # classe d'un autre utilisateur


def test_spotcheck_is_re_presented_and_counted(db, monkeypatch) -> None:
    monkeypatch.setattr(autoaccept, "in_spotcheck", lambda _db, _id: True)
    user = _user(db)
    _agreement(db)
    row = _class(db, user)
    item = _item(db, user)
    spotcheck = db.scalar(select(WrDocketItem).where(WrDocketItem.item_type == "autoaccept_spotcheck",
                                                     WrDocketItem.user_id == user.id))
    assert (spotcheck.status, spotcheck.autoaccept_class_id) == ("pending", row.id)
    assert spotcheck.payload == {"item_id": str(item.id), "item_type": "pattern_new", "payload": {"m": 1}}
    docket.decide(db, current_user=user, item_id=spotcheck.id,
                  request=DocketDecisionRequest(decision="refused", decision_note="Motif faux."),
                  idempotency_key=uuid4().hex, request_path="/x", now=NOW)
    read = autoaccept.list_classes(db, current_user=user, now=NOW)[0]
    assert (read.auto_accepted, read.spotchecks_refused, read.spotchecks_validated, read.agreement_holds) == (1, 1, 0, True)
    assert read.enabled is True  # un refus est un label, il ne désactive rien


def test_spotcheck_draw_is_deterministic(db) -> None:
    ids = [uuid4() for _ in range(2000)]
    picks = [autoaccept.in_spotcheck(db, item_id) for item_id in ids]
    assert 120 < sum(picks) < 280  # ~10 %
    assert picks == [autoaccept.in_spotcheck(db, item_id) for item_id in ids]


def test_class_routes(db) -> None:
    user = _user(db)
    app = FastAPI()
    app.include_router(wr.router, prefix="/api/wr")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    body = {"item_type": "pattern_new", "slot_code": SLOT, "min_confidence": 75, "rationale_fr": "Sûr."}
    assert client.post("/api/wr/autoaccept-classes", json=body).status_code == 400
    key = {"Idempotency-Key": uuid4().hex}
    created = client.post("/api/wr/autoaccept-classes", json=body, headers=key)
    assert created.status_code == 201 and created.json()["agreement_holds"] is False
    assert client.post("/api/wr/autoaccept-classes", json=body, headers=key).json()["id"] == created.json()["id"]
    again = client.post("/api/wr/autoaccept-classes", json=body, headers={"Idempotency-Key": uuid4().hex})
    assert (again.status_code, again.json()["code"]) == (409, "AUTOACCEPT_CLASS_EXISTS")
    assert client.post("/api/wr/autoaccept-classes", json={**body, "slot_code": "nope.slot"},
                       headers={"Idempotency-Key": uuid4().hex}).status_code == 404
    assert client.post("/api/wr/autoaccept-classes", json={**body, "item_type": "user_question"},
                       headers={"Idempotency-Key": uuid4().hex}).status_code == 422
    class_id = created.json()["id"]
    disabled = client.post(f"/api/wr/autoaccept-classes/{class_id}/disable")
    assert disabled.json()["enabled"] is False and disabled.json()["disabled_at"] is not None
    assert client.post(f"/api/wr/autoaccept-classes/{class_id}/disable").status_code == 200
    events = db.scalars(select(Event.event_type).where(Event.user_id == user.id).order_by(Event.occurred_at)).all()
    assert events == ["planning.docket.autoaccept_class_enabled", "planning.docket.autoaccept_class_disabled"]
    # Désactivée, une nouvelle classe du même type redevient possible.
    assert client.post("/api/wr/autoaccept-classes", json=body,
                       headers={"Idempotency-Key": uuid4().hex}).status_code == 201
    assert len(client.get("/api/wr/autoaccept-classes").json()["classes"]) == 2
    assert client.post(f"/api/wr/autoaccept-classes/{uuid4()}/disable").status_code == 404
