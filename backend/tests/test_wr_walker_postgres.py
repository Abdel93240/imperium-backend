"""PostgreSQL : walker du docket, modes et budget d'attention (spec WR §9 P4, carte V18 ACT-WR-06)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("wr walker DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import wr  # noqa: E402
from app.models import ai  # noqa: E402,F401 - FK de la session WR vers ai_tasks
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.imperium import ImperiumWeeklyReviewSession  # noqa: E402
from app.schemas.wr import DocketDecisionRequest  # noqa: E402
from app.services.wr import docket, metrics, walker  # noqa: E402


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
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"walk-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _session(db, user) -> ImperiumWeeklyReviewSession:
    week_start = date.today() - timedelta(days=date.today().weekday())
    session = ImperiumWeeklyReviewSession(user_id=user.id, week_start=week_start, week_end=week_start + timedelta(days=6),
                                          status="conversation_active", launched_at=datetime.now(UTC))
    db.add(session)
    db.commit()
    return session


def _item(db, user, *, item_type="anomaly", severity="normal", impact=3, title="Point"):
    item = docket.create_item(db, current_user=user, item_type=item_type, domain="vault", title_fr=title, payload={},
                              evidence_refs={"k": uuid4().hex}, impact_estimate=impact, source_worker="w4",
                              severity=severity)
    db.commit()
    return item


def _decide(db, user, item, decision, **fields):
    docket.decide(db, current_user=user, item_id=item.id, request=DocketDecisionRequest(decision=decision, **fields),
                  idempotency_key=uuid4().hex, request_path="/x")


def test_walk_serves_by_priority_and_never_reserves_a_deferral(db) -> None:
    user = _user(db)
    with pytest.raises(walker.WalkStateError) as no_session:
        walker.start_walk(db, current_user=user, mode="full")
    assert no_session.value.code == "WR_NOT_OPEN"
    _session(db, user)
    low = _item(db, user, impact=1, title="bas")
    high = _item(db, user, impact=5, title="haut")
    walk, created = walker.start_walk(db, current_user=user, mode="full")
    again, created_again = walker.start_walk(db, current_user=user, mode="light")
    assert (created, created_again, again.id, again.mode, walk.budget_min) == (True, False, walk.id, "full", 45)

    now = walk.started_at + timedelta(minutes=5)
    first = walker.next_item(db, current_user=user, now=now)
    assert (first.item.id, first.remaining_items, first.remaining_min) == (high.id, 2, 40)
    _decide(db, user, high, "deferred")
    second = walker.next_item(db, current_user=user, now=now)
    assert second.item.id == low.id  # le report n'est plus resservi pendant la marche
    _decide(db, user, low, "refused", decision_note="Bruit.")
    done = walker.next_item(db, current_user=user, now=now)
    assert (done.item, done.remaining_items, done.decided_in_walk) == (None, 0, 2)


def test_light_mode_and_budget_exhaustion(db) -> None:
    user = _user(db)
    _session(db, user)
    _item(db, user, item_type="anomaly", impact=5)
    contradiction = _item(db, user, item_type="pattern_contradiction", impact=2)
    red = _item(db, user, item_type="red_flag_ref", severity="red", impact=1)
    walk, _ = walker.start_walk(db, current_user=user, mode="light")
    assert walk.budget_min == 15
    served = walker.next_item(db, current_user=user, now=walk.started_at)
    assert served.remaining_items == 2 and served.item.id in {red.id, contradiction.id}  # pas l'anomalie
    late = walker.next_item(db, current_user=user, now=walk.started_at + timedelta(minutes=16))
    assert late.budget_exhausted and (late.item.id, late.remaining_items, late.remaining_min) == (red.id, 1, 0)


def test_close_carries_items_and_records_light_mode(db) -> None:
    user = _user(db)
    session = _session(db, user)
    _item(db, user)
    walker.start_walk(db, current_user=user, mode="light")
    closed = walker.close_walk(db, current_user=user)
    assert walker.close_walk(db, current_user=user).closed_at == closed.closed_at  # idempotente
    with pytest.raises(walker.WalkStateError) as after_close:
        walker.next_item(db, current_user=user)
    assert after_close.value.code == "WALK_CLOSED"
    event = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "planning.wr_walk.closed"))
    assert (event.payload["mode"], event.payload["carried"], event.payload["decided"]) == ("light", 1, 0)
    week = metrics.compute_week(db, current_user=user, week_start=session.week_start)
    assert week.wr_mode == "light"


def test_walk_routes(db) -> None:
    user = _user(db)
    app = FastAPI()
    app.include_router(wr.router, prefix="/api/wr")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    refused = client.post("/api/wr/walk", json={"mode": "full"})
    assert (refused.status_code, refused.json()["code"]) == (409, "WR_NOT_OPEN")
    _session(db, user)
    assert client.get("/api/wr/walk/next").json()["code"] == "WALK_NOT_STARTED"
    item = _item(db, user)
    assert client.post("/api/wr/walk", json={"mode": "light"}).status_code == 201
    assert client.post("/api/wr/walk", json={"mode": "full"}).status_code == 200
    assert client.post("/api/wr/walk", json={"mode": "court"}).status_code == 422
    body = client.get("/api/wr/walk/next").json()
    assert body["item"] is None and body["walk"]["mode"] == "light"  # anomalie hors mode light
    decision = client.post(f"/api/wr/docket/{item.id}/decision", headers={"Idempotency-Key": uuid4().hex},
                           json={"decision": "refused"})
    assert decision.status_code == 422  # refus sans explication
    closed = client.post("/api/wr/walk/close")
    assert closed.status_code == 200 and closed.json()["closed_at"] is not None
