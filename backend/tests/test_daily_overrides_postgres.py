"""PostgreSQL : overrides capturés et agrégation hebdo au docket (spec Daily §3.4, §10 ; ACT-DLY-07, ACT-DLY-08)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("daily overrides DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import daily  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.daily import DailyOverride, DailySelectionLog  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.imperium import ImperiumMission, ImperiumMissionScore  # noqa: E402
from app.models.wr import WrDocketItem  # noqa: E402
from app.services.daily import overrides, selection  # noqa: E402
from app.services.params import set_parameter  # noqa: E402
from app.services.runner.engine import RunContext, Window  # noqa: E402

NOW = datetime(2026, 10, 21, 8, 0, tzinfo=UTC)  # mercredi 10 h à Paris


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    # Les routes et le job committent : transaction externe annulée, rien ne fuit.
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"dovr-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _enable(db, **values) -> None:
    for code, value in values.items():
        set_parameter(db, code=f"daily.{code}", value=value, origin="user", rationale_fr="Test.")
    db.commit()


def _mission(db, user, title: str, *, domain: str = "finance", score: float = 50, category: str | None = None):
    mission = ImperiumMission(user_id=user.id, title=title, domain=domain, status="backlog", started_at=NOW,
                              planned_start_at=NOW, estimated_minutes=20, mission_type_category=category)
    db.add(mission)
    db.flush()
    db.add(ImperiumMissionScore(user_id=user.id, mission_id=mission.id, domain=domain, intrinsic_score=score / 10,
                                domain_coefficient=10, weighted_score=score, explanation={},
                                source="decision_framework_v1"))
    db.commit()
    return mission


def _proposal(db, user):
    proposed = _mission(db, user, "Proposée", score=90, domain="finance", category="cat_b")
    other = _mission(db, user, "Préférée", score=40, domain="business", category="cat_c")
    log = selection.select_next(db, current_user=user, trigger="manual", now=NOW)
    db.commit()
    assert log.chosen_mission_id == proposed.id
    return log, proposed, other


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(daily.router, prefix="/api/daily")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def test_seeded_off(db) -> None:
    assert overrides.override_enabled(db) is False
    job = db.execute(text("SELECT enabled, schedule FROM job_definitions WHERE code = 'daily.override_aggregation'")).one()
    assert tuple(job) == (False, "0 17 * * 0")
    response = _client(db, _user(db)).post("/api/daily/override", json={
        "selection_log_id": str(uuid4()), "chosen_mission_id": str(uuid4()), "reason": "x"})
    assert response.status_code == 409 and response.json()["code"] == "DAILY_OVERRIDE_DISABLED"


def test_override_requires_a_reason_and_freezes_its_context(db) -> None:
    user = _user(db)
    log, proposed, other = _proposal(db, user)
    _enable(db, override_enabled=True)
    client = _client(db, user)
    body = {"selection_log_id": str(log.id), "chosen_mission_id": str(other.id)}
    for reason in (None, "   "):
        missing = client.post("/api/daily/override", json={**body, "reason": reason})
        assert missing.status_code == 400 and missing.json()["code"] == "OVERRIDE_REASON_REQUIRED"
    created = client.post("/api/daily/override", json={**body, "reason": "Le client m'attend ce matin."})
    assert created.status_code == 201, created.text
    context = created.json()["context"]
    assert context["time_slot"] == overrides.time_slot(context["hour"]) and context["scope"] == "day"
    assert context["proposed"]["mission_id"] == str(proposed.id) and context["proposed"]["score"] == 90
    assert context["proposed"]["in_selection"] is True and context["chosen"]["domain"] == "business"
    assert "df.impact_points" in context["scale_versions"]
    assert db.get(ImperiumMission, other.id).status == "backlog"  # l'override ne démarre rien
    event = db.scalar(select(Event).where(Event.user_id == user.id,
                                          Event.event_type == "planning.daily.override_recorded"))
    proposed_event = db.scalar(select(Event).where(Event.user_id == user.id,
                                                   Event.event_type == "planning.daily.next_proposed"))
    assert event.causation_id == proposed_event.event_id
    assert event.payload == {"override_id": created.json()["id"], "selection_log_id": str(log.id),
                             "proposed": str(proposed.id), "chosen": str(other.id)}
    again = client.post("/api/daily/override", json={**body, "reason": "Encore."})
    assert again.status_code == 409 and again.json()["code"] == "OVERRIDE_EXISTS"


def test_override_rejections(db) -> None:
    user = _user(db)
    log, proposed, other = _proposal(db, user)
    _enable(db, override_enabled=True)
    client = _client(db, user)
    same = client.post("/api/daily/override", json={"selection_log_id": str(log.id),
                                                    "chosen_mission_id": str(proposed.id), "reason": "x"})
    assert same.status_code == 422 and same.json()["code"] == "OVERRIDE_SAME_MISSION"
    unknown = client.post("/api/daily/override", json={"selection_log_id": str(uuid4()),
                                                       "chosen_mission_id": str(other.id), "reason": "x"})
    assert unknown.status_code == 404
    other.status = "completed"
    db.commit()
    closed = client.post("/api/daily/override", json={"selection_log_id": str(log.id),
                                                      "chosen_mission_id": str(other.id), "reason": "x"})
    assert closed.json()["code"] == "MISSION_NOT_AVAILABLE"
    empty = _user(db)
    done = selection.select_next(db, current_user=empty, trigger="manual", now=NOW)
    db.commit()
    no_proposal = _client(db, empty).post("/api/daily/override", json={
        "selection_log_id": str(done.id), "chosen_mission_id": str(other.id), "reason": "x"})
    assert no_proposal.json()["code"] == "OVERRIDE_NO_PROPOSAL"


def test_blank_reason_is_refused_by_the_database(db) -> None:
    user = _user(db)
    log, proposed, other = _proposal(db, user)
    db.add(DailyOverride(user_id=user.id, selection_log_id=log.id, proposed_mission_id=proposed.id,
                         chosen_mission_id=other.id, reason="  ", context={}))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def _override(db, user, *, at: datetime, proposed_domain="finance", chosen_domain="business", slot="morning",
              reason="Raison.", chosen_category=None, proposed_category=None) -> DailyOverride:
    proposed = _mission(db, user, "P", domain=proposed_domain)
    chosen = _mission(db, user, "C", domain=chosen_domain)
    log = DailySelectionLog(user_id=user.id, trigger="manual", at_ts=at, remaining_min=60, scope="day",
                            feasible_set=[], mandatory_set=[], chosen_mission_id=proposed.id, outcome="next_mission",
                            level=1, latency_ms=1)
    db.add(log)
    db.flush()
    row = DailyOverride(user_id=user.id, selection_log_id=log.id, proposed_mission_id=proposed.id,
                        chosen_mission_id=chosen.id, reason=reason, created_at=at, context={
                            "time_slot": slot,
                            "proposed": {"domain": proposed_domain, "mission_type_category": proposed_category},
                            "chosen": {"domain": chosen_domain, "mission_type_category": chosen_category}})
    db.add(row)
    db.commit()
    return row


def _items(db, user) -> list[WrDocketItem]:
    return list(db.scalars(select(WrDocketItem).where(WrDocketItem.user_id == user.id,
                                                      WrDocketItem.item_type == "ordering_override_pattern")
                           .order_by(WrDocketItem.created_at)))


def test_aggregation_deposits_one_item_per_pattern_at_threshold(db) -> None:
    user = _user(db)
    for days, reason in ((20, "Client urgent."), (10, "Rendez-vous banque décalé."), (2, "Devis à envoyer.")):
        _override(db, user, at=NOW - timedelta(days=days), reason=reason)
    _override(db, user, at=NOW - timedelta(days=40), reason="Hors fenêtre.")
    _override(db, user, at=NOW - timedelta(days=3), slot="evening")
    stats = overrides.aggregate(db, current_user=user, now=NOW)
    db.commit()
    assert (stats.overrides, stats.patterns, stats.items) == (4, 1, 1)
    (item,) = _items(db, user)
    assert item.domain == "daily" and item.source_worker == "w5" and item.status == "pending"
    assert item.payload["pattern"] == {"proposed_domain": "finance", "chosen_domain": "business", "time_slot": "morning"}
    assert item.payload["count"] == 3
    assert item.payload["examples"] == ["Client urgent.", "Rendez-vous banque décalé.", "Devis à envoyer."]
    assert item.payload["suggested_target"] == {"kind": "domain_coefficient", "parameter": "df.coefficient_by_position",
                                                "preferred_domain": "business", "over_domain": "finance"}
    assert len(item.evidence_refs["override_ids"]) == 3
    # Aucun ajustement automatique : les barèmes restent en version 1.
    assert db.execute(text("SELECT max(version) FROM v_parameters_current WHERE code LIKE 'df.%'")).scalar() == 1

    assert overrides.aggregate(db, current_user=user, now=NOW).skipped_open == 1  # motif encore ouvert
    item.status = "refused"
    db.commit()
    assert overrides.aggregate(db, current_user=user, now=NOW).items == 0  # rien de neuf depuis l'item
    for hours in (1, 2, 3):
        _override(db, user, at=NOW + timedelta(hours=hours))
    assert overrides.aggregate(db, current_user=user, now=NOW + timedelta(hours=4)).items == 1
    assert len(_items(db, user)) == 2


def test_suggested_target_and_time_slots() -> None:
    same = [{"time_slot": "morning", "proposed": {"domain": "finance", "mission_type_category": "cat_b"},
             "chosen": {"domain": "finance", "mission_type_category": "cat_c"}}] * 3
    assert overrides.suggested_target(same) == {"kind": "criterion_c", "parameter": "df.mission_type_points",
                                                "category": "cat_c"}
    mixed = [same[0], {**same[0], "chosen": {"domain": "finance", "mission_type_category": "cat_d"}}]
    assert overrides.suggested_target(mixed) == {"kind": "discussion"}
    assert [overrides.time_slot(h) for h in (4, 5, 11, 12, 18, 23)] == [
        "night", "morning", "morning", "afternoon", "evening", "night"]


def test_aggregation_job(db, monkeypatch) -> None:
    ctx = RunContext(db=db, job=None, run_id=uuid4(), trigger="cron", trigger_ref=None)
    monkeypatch.setattr("app.services.wr.metrics._job_user", lambda _db: None)
    overrides.aggregation_job(ctx, Window(from_ts=None, to_ts=NOW))
    assert ctx.detail == {"skip": "no_user"}
    user = _user(db)
    monkeypatch.setattr("app.services.wr.metrics._job_user", lambda _db: user)
    for days in (1, 2, 3):
        _override(db, user, at=NOW - timedelta(days=days))
    overrides.aggregation_job(ctx, Window(from_ts=None, to_ts=NOW))
    assert (ctx.items_in, ctx.items_out) == (3, 1)
