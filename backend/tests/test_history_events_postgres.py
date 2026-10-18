"""PostgreSQL : chronologie de l'historique Imperium (IMP.HISTORY.MAIN, doc 65 §7)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("history events DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_history  # noqa: E402
from app.models import ai  # noqa: E402,F401 - tables référencées par les sessions WR
from app.models.auth import User  # noqa: E402
from app.models.imperium import (  # noqa: E402
    ImperiumMission,
    ImperiumProject,
    ImperiumWeeklyReviewFinalReport,
    ImperiumWeeklyReviewSession,
)
from app.services.events.emitter import build_event  # noqa: E402

BASE = "/api/imperium/history/events"
T0 = datetime(2026, 10, 10, 8, 0, tzinfo=UTC)


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
        {"id": str(user_id), "email": f"history-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_history.router, prefix="/api/imperium")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _event(db, user, event_type, payload, minutes) -> str:
    event = build_event(db, user_id=user.id, event_type=event_type, payload=payload, idempotency_key=uuid4().hex,
                        occurred_at=T0 + timedelta(minutes=minutes))
    db.add(event)
    db.flush()
    return event.event_id


def _seed(db, user) -> dict:
    done = ImperiumMission(user_id=user.id, title="Déclarer la TVA", status="completed", started_at=T0)
    failed = ImperiumMission(user_id=user.id, title="Séance de sport", status="failed", started_at=T0)
    cancelled = ImperiumMission(user_id=user.id, title="Appeler le garage", status="cancelled", started_at=T0)
    active = ImperiumMission(user_id=user.id, title="Préparer le devis", status="active", started_at=T0)
    project = ImperiumProject(user_id=user.id, title="Camping-car", rank_order=1, status="open", source="manual")
    db.add_all([done, failed, cancelled, active, project])
    db.flush()
    ids = {
        "day": _event(db, user, "planning.day.started", {"planning_day_id": str(uuid4()), "felt_energy": 4}, 0),
        "done": _event(db, user, "mission.completed", {"mission_id": str(done.id), "outcome": "completed"}, 10),
        "failed": _event(db, user, "mission.failed", {"mission_id": str(failed.id), "failure_reason": "Fatigue après VTC",
                                                      "user_reported_signals": {"x": 1}}, 20),
        "cancelled": _event(db, user, "mission.abandoned", {"mission_id": str(cancelled.id), "reason": "cancelled",
                                                            "cancellation_reason": "Plus utile"}, 30),
        "active": _event(db, user, "mission.started", {"mission_id": str(active.id)}, 40),
        "deleted": _event(db, user, "mission.abandoned", {"mission_id": str(cancelled.id), "reason": "deleted_by_user"}, 41),
        "coded": _event(db, user, "mission.failed", {"mission_id": str(failed.id), "reason": "too_tired",
                                                     "failure_reason_code": "too_tired"}, 42),
        "priorities": _event(db, user, "priority.rules.updated", {"priorities": []}, 50),
        "project": _event(db, user, "planning.project.created", {"project_id": str(project.id), "source": "manual", "rank": 1}, 60),
        "finished": _event(db, user, "day.finished", {"planning_day_id": str(uuid4()), "missions_returned_to_backlog": 1}, 70),
    }
    _event(db, user, "finance.transaction.created", {"amount_cents": 100}, 80)  # hors historique Imperium
    session = ImperiumWeeklyReviewSession(user_id=user.id, week_start=date(2026, 10, 5), week_end=date(2026, 10, 11),
                                          status="approved")
    db.add(session)
    db.flush()
    report = ImperiumWeeklyReviewFinalReport(session_id=session.id, user_id=user.id, week_start=session.week_start,
                                             week_end=session.week_end, status="approved", report_payload={},
                                             report_markdown="# WR", approved_at=T0 + timedelta(minutes=90))
    draft_session = ImperiumWeeklyReviewSession(user_id=user.id, week_start=date(2026, 10, 12), week_end=date(2026, 10, 18),
                                                status="draft_ready")
    db.add_all([report, draft_session])
    db.flush()
    db.add(ImperiumWeeklyReviewFinalReport(session_id=draft_session.id, user_id=user.id, week_start=draft_session.week_start,
                                           week_end=draft_session.week_end, status="draft", report_payload={}, report_markdown="#"))
    db.commit()
    ids["weekly"] = f"weekly_report:{report.id}"
    ids["active_mission"] = str(active.id)
    return ids


def test_timeline_projects_imperium_facts_newest_first(db) -> None:
    user = _user(db)
    ids = _seed(db, user)
    body = _client(db, user).get(BASE).json()
    assert [(i["type"], i["title"], i["status"], i["source"]) for i in body["items"]] == [
        ("weekly_review", "Weekly Review du 05/10/2026", "approved", "weekly"),
        ("day_finished", "Journée terminée", "finished", "day"),
        ("project_created", "Camping-car", "created", "project"),
        ("priorities_updated", "Priorités modifiées", "updated", "decision"),
        ("mission_failed", "Séance de sport", "failed", "mission"),
        ("mission_cancelled", "Appeler le garage", "cancelled", "mission"),
        ("mission_started", "Préparer le devis", "active", "mission"),
        ("mission_cancelled", "Appeler le garage", "cancelled", "mission"),
        ("mission_failed", "Séance de sport", "failed", "mission"),
        ("mission_completed", "Déclarer la TVA", "completed", "mission"),
        ("day_started", "Journée démarrée", "started", "day"),
    ]
    by_id = {i["id"]: i for i in body["items"]}
    assert (by_id[ids["active"]]["linked_route"], by_id[ids["active"]]["linked_mission_id"]) == ("IMP.MISSION.ACTIVE", ids["active_mission"])
    assert (by_id[ids["failed"]]["reason"], by_id[ids["cancelled"]]["reason"]) == ("Fatigue après VTC", "Plus utile")
    assert (by_id[ids["weekly"]]["linked_route"], by_id[ids["day"]]["linked_route"]) == ("IMP.WR.READ_ONLY", "IMP.PLAN.HISTORY")
    assert (by_id[ids["deleted"]]["reason"], by_id[ids["coded"]]["reason"]) == ("Supprimée par l'utilisateur", "too_tired")
    assert (body["count"], body["has_more"], body["filter"]) == (11, False, "all")


def test_filters_search_and_pages(db) -> None:
    user = _user(db)
    _seed(db, user)
    client = _client(db, user)

    def types(**params):
        return [i["type"] for i in client.get(BASE, params=params).json()["items"]]

    assert types(filter="failed") == ["mission_failed", "mission_failed"]
    assert types(filter="weekly") == ["weekly_review"]
    assert types(filter="decisions") == ["project_created", "priorities_updated"]
    assert len(types(filter="missions")) == 6
    assert types(query="garage") == ["mission_cancelled", "mission_cancelled"]
    page = client.get(BASE, params={"limit": 2, "offset": 2}).json()
    assert ([i["type"] for i in page["items"]], page["has_more"]) == (["project_created", "priorities_updated"], True)
    assert client.get(BASE, params={"filter": "other"}).status_code == 422
    assert _client(db, _user(db)).get(BASE).json()["items"] == []


def test_detail_card_and_isolation(db) -> None:
    user = _user(db)
    ids = _seed(db, user)
    client = _client(db, user)
    failed = client.get(f"{BASE}/{ids['failed']}").json()
    assert failed["event"]["type"] == "mission_failed"
    assert failed["details"] == {"failure_reason": "Fatigue après VTC"}  # signaux bruts non exposés
    weekly = client.get(f"{BASE}/{ids['weekly']}").json()
    assert (weekly["details"]["week_start"], weekly["details"]["week_end"]) == ("2026-10-05", "2026-10-11")
    other = _client(db, _user(db))
    assert other.get(f"{BASE}/{ids['failed']}").status_code == 404
    assert other.get(f"{BASE}/{ids['weekly']}").status_code == 404
    assert client.get(f"{BASE}/weekly_report:pas-un-uuid").status_code == 404
    assert client.get(f"{BASE}/evt_inconnu").status_code == 404
