"""PostgreSQL : audit décroissant des slots IA (doc 78 F1-13 ; spec WR §3.7, §10, §13.1)."""
from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("ai audit loop DB tests")

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
from app.models.toolbox import AIAuditSample, AISlotTransition, JobDefinition, Notification  # noqa: E402
from app.services.ai import audit_loop  # noqa: E402
from app.services.runner.engine import RunContext, Window  # noqa: E402
from app.services.wr import metrics  # noqa: E402

PARIS = ZoneInfo("Europe/Paris")
SLOT = "test.audit_slot"
NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)  # mercredi ; semaine en cours = lundi 19/10
CLOSED_WEEKS = (date(2026, 10, 12), date(2026, 10, 5), date(2026, 9, 28))


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


def _cleanup(session: Session) -> None:
    session.execute(delete(AIAuditSample).where(AIAuditSample.slot_code == SLOT))
    session.execute(delete(AISlotTransition).where(AISlotTransition.slot_code == SLOT))
    session.execute(delete(Notification).where(Notification.ref_type == "ai_audit_decay"))
    session.commit()


@pytest.fixture()
def db(engine):
    with Session(engine) as session:
        _cleanup(session)
        session.add(AISlotTransition(slot_code=SLOT, domain="wr", tier="local_default", audit_sample_pct=100,
                                     agreement_target_pct=92, updated_at=datetime(2026, 9, 1, tzinfo=UTC)))
        session.commit()
        yield session
        session.rollback()
        _cleanup(session)


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"audit-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _samples(db, week_start: date, *, agreed: int, disagreed: int = 0) -> None:
    at = datetime.combine(week_start + timedelta(days=2), time(10), tzinfo=PARIS)
    for index in range(agreed + disagreed):
        sample, _ = audit_loop.record_sample(
            db, slot_code=SLOT, run_ref=uuid4(), local_output={"v": 1}, cloud_output={"v": 1 if index < agreed else 2},
            cloud_model="cloud-role", agreement=index < agreed,
            disagreement_class=None if index < agreed else "wrong_label",
        )
        sample.created_at = at
    db.commit()


def _state(db, now: datetime = NOW):
    return next(state for state in audit_loop.slot_states(db, now=now) if state.slot_code == SLOT)


def test_seeded_slots_and_disabled_job(db) -> None:
    seeded = {row.slot_code: row for row in db.scalars(
        select(AISlotTransition).where(AISlotTransition.domain.in_(("wr", "daily")), AISlotTransition.slot_code != SLOT))}
    assert len(seeded) == 13  # + wr.conversation (migration 0120)
    assert {code for code, row in seeded.items() if row.tier == "local_default"} == {
        "wr.probe_gen", "wr.pair_verdict", "wr.pattern_extract", "wr.identity", "wr.conversation",
        "daily.disruption_classify", "daily.conflict_arbitrate"}
    assert all((row.audit_sample_pct, row.agreement_target_pct) == (100, 92) for row in seeded.values())
    job = db.scalar(select(JobDefinition).where(JobDefinition.code == "wr.audit_weekly"))
    assert job is not None and job.enabled is False


def test_sampling_is_deterministic_and_skips_cloud_slots(db) -> None:
    assert audit_loop.should_audit(db, slot_code=SLOT, sample_key="a") is True  # 100 %
    assert audit_loop.should_audit(db, slot_code="wr.exit_audit", sample_key="a") is False  # cloud_forced
    slot = db.scalar(select(AISlotTransition).where(AISlotTransition.slot_code == SLOT))
    slot.audit_sample_pct = 30
    db.commit()
    picks = [audit_loop.should_audit(db, slot_code=SLOT, sample_key=str(index)) for index in range(1000)]
    assert 250 < sum(picks) < 350
    assert picks == [audit_loop.should_audit(db, slot_code=SLOT, sample_key=str(index)) for index in range(1000)]
    slot.audit_sample_pct = 0
    db.commit()
    assert not any(audit_loop.should_audit(db, slot_code=SLOT, sample_key=str(index)) for index in range(50))
    with pytest.raises(audit_loop.UnknownSlotError):
        audit_loop.should_audit(db, slot_code="nope.slot", sample_key="a")


def test_record_sample_is_idempotent_and_feeds_training_pairs(db) -> None:
    run = uuid4()
    first, created = audit_loop.record_sample(
        db, slot_code=SLOT, run_ref=run, local_output={"c": "a"}, cloud_output={"c": "b"}, cloud_model="cloud-role",
        agreement=False, disagreement_class="wrong_category",
    )
    again, created_again = audit_loop.record_sample(
        db, slot_code=SLOT, run_ref=run, local_output={"c": "a"}, cloud_output={"c": "b"}, cloud_model="cloud-role",
        agreement=False, disagreement_class="wrong_category",
    )
    db.commit()
    assert (created, created_again, again.id) == (True, False, first.id)
    pairs = db.execute(text("SELECT sample_id FROM v_ai_training_pairs WHERE slot_code = :slot"), {"slot": SLOT}).all()
    assert [row.sample_id for row in pairs] == [first.id]
    with pytest.raises(ValueError):
        audit_loop.record_sample(db, slot_code=SLOT, run_ref=None, local_output={}, cloud_output={},
                                 cloud_model="m", agreement=True, disagreement_class="x")


def test_decay_is_proposed_after_three_closed_weeks_at_target(db) -> None:
    _samples(db, CLOSED_WEEKS[0], agreed=10)
    _samples(db, CLOSED_WEEKS[1], agreed=12, disagreed=1)  # 92,3 %
    _samples(db, CLOSED_WEEKS[2], agreed=4)  # sous le minimum de 5
    _samples(db, date(2026, 10, 19), agreed=1, disagreed=5)  # semaine en cours : ignorée
    state = _state(db)
    assert [week.week_start for week in state.weeks] == list(CLOSED_WEEKS)
    assert state.decay_proposed is False
    _samples(db, CLOSED_WEEKS[2], agreed=2)
    state = _state(db)
    assert (state.decay_proposed, state.proposed_audit_sample_pct) == (True, 50)
    # Une semaine sous la cible casse la série.
    _samples(db, CLOSED_WEEKS[0], agreed=0, disagreed=2)
    assert _state(db).decay_proposed is False


def test_user_decision_route_job_and_metrics(db, monkeypatch) -> None:
    for week in CLOSED_WEEKS:
        _samples(db, week, agreed=6)
    user = _user(db)

    ctx = RunContext(db=db, job=None, run_id=uuid4(), trigger="manual", trigger_ref=None)
    audit_loop.audit_weekly_job(ctx, Window(from_ts=None, to_ts=NOW))
    audit_loop.audit_weekly_job(ctx, Window(from_ts=None, to_ts=NOW + timedelta(hours=1)))
    notes = db.scalars(select(Notification).where(Notification.ref_type == "ai_audit_decay")).all()
    assert len(notes) == 1 and SLOT in notes[0].message_fr  # une fois par semaine
    assert db.scalar(select(AISlotTransition.audit_sample_pct).where(AISlotTransition.slot_code == SLOT)) == 100

    row = metrics.compute_week(db, current_user=user, week_start=CLOSED_WEEKS[0], now=NOW)
    assert row.agreement_by_slot[SLOT] == 100.0

    monkeypatch.setattr(audit_loop, "datetime", _FrozenDatetime)
    app = FastAPI()
    app.include_router(wr.router, prefix="/api/wr")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    listed = {slot["slot_code"]: slot for slot in client.get("/api/wr/admin/transition").json()["slots"]}
    assert listed[SLOT]["decay_proposed"] is True and listed["wr.exit_audit"]["decay_proposed"] is False

    body = {"slot_code": SLOT, "audit_sample_pct": 50, "reason_fr": "Agreement stable trois semaines."}
    assert client.post("/api/wr/admin/transition", json=body).status_code == 400  # sans Idempotency-Key
    key = {"Idempotency-Key": uuid4().hex}
    updated = client.post("/api/wr/admin/transition", json=body, headers=key)
    assert updated.status_code == 200
    assert (updated.json()["audit_sample_pct"], updated.json()["version"], updated.json()["decay_proposed"]) == (50, 2, False)
    assert client.post("/api/wr/admin/transition", json=body, headers=key).json() == updated.json()  # rejeu
    assert client.post("/api/wr/admin/transition", json={**body, "audit_sample_pct": 40}, headers=key).status_code == 409
    events = db.scalars(select(Event).where(Event.user_id == user.id, Event.event_type == "decision.ai_audit.updated")).all()
    assert len(events) == 1 and events[0].payload["previous"]["audit_sample_pct"] == 100
    assert client.post("/api/wr/admin/transition", json={**body, "slot_code": "nope.slot"},
                       headers={"Idempotency-Key": uuid4().hex}).status_code == 404
    assert client.post("/api/wr/admin/transition", json={"slot_code": SLOT, "reason_fr": "x"},
                       headers={"Idempotency-Key": uuid4().hex}).status_code == 422
    assert client.post("/api/wr/admin/transition", json={**body, "tier": "cloud_forced"},
                       headers={"Idempotency-Key": uuid4().hex}).json()["tier"] == "local_default"  # tier ignoré


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW if tz is None else NOW.astimezone(tz)
