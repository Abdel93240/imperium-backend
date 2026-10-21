"""PostgreSQL : la journée menée par la sélection — démarrer la proposition, programme du jour, Replanifier
(imprévu, mauvaise estimation, fatigue, autre priorité, autre ; décision utilisateur 2026-10-21)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("daily day flow DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import daily  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.daily import DailySelectionLog  # noqa: E402
from app.models.imperium import ImperiumMission, ImperiumMissionScore, PlanningReplanEvent  # noqa: E402
from app.schemas.daily import DayReplanRequest  # noqa: E402
from app.schemas.imperium import StartPlanningDayRequest  # noqa: E402
from app.services.daily import day_flow, selection  # noqa: E402
from app.services.imperium.planning_days import start_planning_day  # noqa: E402
from app.services.params import set_parameter  # noqa: E402

PARIS = selection.PARIS
NOW = datetime(2026, 10, 21, 8, 0, tzinfo=UTC)  # mercredi 10 h à Paris


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
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
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"dflow-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _mission(db, user, title: str, *, score: float = 50, minutes: int = 20, planned=NOW, **fields) -> ImperiumMission:
    mission = ImperiumMission(user_id=user.id, title=title, domain="finance", status="backlog", started_at=NOW,
                              planned_start_at=planned, estimated_minutes=minutes, **fields)
    db.add(mission)
    db.flush()
    db.add(ImperiumMissionScore(user_id=user.id, mission_id=mission.id, domain="finance", intrinsic_score=score / 10,
                                domain_coefficient=10, weighted_score=score, explanation={},
                                source="decision_framework_v1"))
    db.commit()
    return mission


def _day(db, user) -> None:
    set_parameter(db, code="daily.selection_enabled", value=True, origin="user", rationale_fr="Test.")
    db.commit()
    start_planning_day(db, current_user=user, payload=StartPlanningDayRequest(felt_energy=3, idempotency_key=str(uuid4())),
                       request_method="POST", request_path="/api/imperium/day/start")


def _replan(db, user, now=NOW, **body):
    return day_flow.replan(db, current_user=user, payload=DayReplanRequest(reason_detail="Ça change.", **body),
                           idempotency_key=str(uuid4()), now=now)


def test_start_programme_and_wrong_estimation(db) -> None:
    user = _user(db)
    _day(db, user)
    report = _mission(db, user, "Rapport", score=80, minutes=45)
    _mission(db, user, "Courrier", score=40, minutes=10)
    row = selection.select_next(db, current_user=user, trigger="day_start", now=NOW)
    db.commit()
    assert row.chosen_mission_id == report.id
    programme = day_flow.programme(db, current_user=user, now=NOW)
    assert [(i.title, i.state) for i in programme.items] == [("Rapport", "next")] and programme.outcome == "next_mission"

    started = day_flow.start_mission(db, current_user=user, mission_id=report.id, idempotency_key=str(uuid4()), now=NOW)
    assert started.status == "active" and started.planned_end_at - started.planned_start_at == timedelta(minutes=45)
    assert [(i.title, i.state) for i in day_flow.programme(db, current_user=user, now=NOW).items] == [("Rapport", "active")]
    with pytest.raises(day_flow.DayFlowError) as busy:  # la suite ne bouge pas tant qu'une mission est en cours
        _replan(db, user, reason_category="fatigue")
    assert busy.value.code == "MISSION_ACTIVE"
    read = _replan(db, user, NOW + timedelta(minutes=6), reason_category="wrong_estimation", extend_minutes=30)
    assert started.planned_end_at - started.planned_start_at == timedelta(minutes=75)
    assert read.rationale.startswith("J'ai prolongé « Rapport » de 30 min") and read.selection is None
    event = db.scalar(select(PlanningReplanEvent).where(PlanningReplanEvent.user_id == user.id))
    assert (event.status, event.reason_category, event.trigger) == ("accepted", "wrong_estimation", "manual")


def test_replan_reasons_change_the_next_proposal(db) -> None:
    user = _user(db)
    _day(db, user)
    long = _mission(db, user, "Dossier long", score=90, minutes=120)
    short = _mission(db, user, "Appel court", score=30, minutes=15)
    later = _mission(db, user, "Banque", score=95, minutes=20,
                     window_start=datetime(2026, 1, 1, 14, 0).time(), window_end=datetime(2026, 1, 1, 17, 0).time())
    project = _mission(db, user, "Mission de projet sans date", score=10, planned=None)

    tired = _replan(db, user, reason_category="fatigue")  # 10 h
    assert tired.selection.next_mission.id == short.id and "mission courte" in tired.rationale
    other = _replan(db, user, NOW + timedelta(minutes=6), reason_category="other", other_reason="Envie de changer")
    assert other.selection.next_mission.id == long.id  # la banque n'ouvre qu'à 14 h
    busy = _replan(db, user, NOW + timedelta(minutes=12), reason_category="new_event",
                   busy_until=datetime(2026, 10, 21, 12, 30, tzinfo=UTC))
    assert busy.selection.next_mission.id == later.id and "fin vers 14:30" in busy.rationale
    chosen = _replan(db, user, NOW + timedelta(minutes=18), reason_category="priority_shift", mission_id=project.id)
    assert chosen.selection.next_mission.id == project.id and chosen.rationale == "C'est noté : « Mission de projet sans date » passe maintenant."
    log = db.scalar(select(DailySelectionLog).where(DailySelectionLog.id == chosen.selection.selection_log_id))
    assert (log.trigger, log.tiebreak_applied["forced_by"]) == ("replan", "user_replan")
    with pytest.raises(day_flow.DayFlowError) as late:
        _replan(db, user, NOW + timedelta(minutes=24), reason_category="new_event",
                busy_until=datetime(2026, 10, 22, 9, 0, tzinfo=UTC))
    assert late.value.code == "BAD_BUSY_UNTIL"
    assert db.scalar(select(PlanningReplanEvent.id).where(PlanningReplanEvent.user_id == user.id).limit(1)) is not None


class _TenAm(datetime):
    """Les routes lisent l'heure réelle : on la fige à 10 h de Paris, le test ne dépend pas de l'heure du jour."""

    @classmethod
    def now(cls, tz=None):
        return NOW if tz is None else NOW.astimezone(tz)


def test_routes_cooldown_and_validation(db, monkeypatch) -> None:
    monkeypatch.setattr(day_flow, "datetime", _TenAm)
    user = _user(db)
    _day(db, user)
    first = _mission(db, user, "Courses", minutes=30, planned=NOW - timedelta(hours=1))
    app = FastAPI()
    app.include_router(daily.router, prefix="/api/daily")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    body = {"reason_category": "other", "reason_detail": "Je rentre plus tôt.", "other_reason": "Retour"}
    replanned = client.post("/api/daily/replan", json=body, headers={"Idempotency-Key": "k1"})
    assert replanned.status_code == 200 and replanned.json()["selection"]["next_mission"]["title"] == "Courses"
    assert client.post("/api/daily/replan", json=body, headers={"Idempotency-Key": "k1"}).status_code == 200  # rejouée
    cooldown = client.post("/api/daily/replan", json=body, headers={"Idempotency-Key": "k2"})
    assert cooldown.status_code == 429 and cooldown.json()["code"] == "REPLAN_COOLDOWN"
    assert client.post("/api/daily/replan", json={**body, "reason_detail": "  "},
                       headers={"Idempotency-Key": "k3"}).status_code == 422
    assert client.post("/api/daily/replan", json={"reason_category": "new_event", "reason_detail": "RDV"},
                       headers={"Idempotency-Key": "k4"}).status_code == 422  # busy_until manquant
    started = client.post(f"/api/daily/start/{first.id}", headers={"Idempotency-Key": "s1"})
    assert started.status_code == 200 and started.json()["active_mission_id"] == str(first.id)
    programme = client.get("/api/daily/programme").json()
    assert [(i["title"], i["state"]) for i in programme["items"]] == [("Courses", "active")]
    assert client.post(f"/api/daily/start/{first.id}", headers={"Idempotency-Key": "s2"}).json()["code"] == "MISSION_STATE"


def test_a_day_started_late_does_not_end_at_midnight(db) -> None:
    from app.models.imperium import PlanningDay

    user = _user(db)
    set_parameter(db, code="daily.selection_enabled", value=True, origin="user", rationale_fr="Test.")
    started = datetime(2026, 10, 21, 21, 46, tzinfo=UTC)  # 23 h 46 à Paris
    db.add(PlanningDay(user_id=user.id, started_at=started, start_local_date=started.date(), timezone="Europe/Paris",
                       felt_energy=3, idempotency_key=str(uuid4())))
    db.commit()
    insurance = _mission(db, user, "Payer l'assurance moto", minutes=30, planned=started - timedelta(hours=1))
    now = started + timedelta(minutes=7)  # 23 h 53 : avant, 7 minutes restaient et rien ne tenait
    assert selection.day_end(db, user, now) == started + timedelta(hours=16)
    row = selection.select_next(db, current_user=user, trigger="manual", now=now)
    assert row.outcome == "next_mission" and row.chosen_mission_id == insurance.id and row.remaining_min > 800
