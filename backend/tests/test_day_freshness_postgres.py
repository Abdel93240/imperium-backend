"""PostgreSQL : vérification de fraîcheur au démarrage de journée (DECISION_demarrage_journee, doc 52 §9.1)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("day freshness DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.imperium import ImperiumCalendarEvent, ImperiumDailyPlan, ImperiumMission, PlanningDay  # noqa: E402
from app.models.path import PathFast, PathGhuslState  # noqa: E402
from app.services.events.emitter import build_event  # noqa: E402
from app.services.imperium.day_freshness import check_freshness  # noqa: E402

BASE = "/api/imperium"
START = datetime(2026, 10, 18, 7, 0, tzinfo=UTC)
GENERATED = datetime(2026, 10, 17, 22, 0, tzinfo=UTC)


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
        {"id": str(user_id), "email": f"fresh-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium.router, prefix=BASE)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _day(db, user, started_at, finished_at=None) -> PlanningDay:
    day = PlanningDay(user_id=user.id, started_at=started_at, finished_at=finished_at, start_local_date=started_at.date(),
                      timezone="Europe/Paris", felt_energy=3, idempotency_key=uuid4().hex)
    db.add(day)
    db.flush()
    return day


def _mission(db, user, title, status, started_at, ended_at=None) -> ImperiumMission:
    mission = ImperiumMission(user_id=user.id, title=title, status=status, started_at=started_at, ended_at=ended_at)
    db.add(mission)
    db.flush()
    return mission


def _event(db, user, title, starts_at, *, created, updated, deleted=None, blocks=True, ends_at=None) -> None:
    db.add(ImperiumCalendarEvent(user_id=user.id, event_type="event", title=title, starts_at=starts_at, ends_at=ends_at,
                                 blocks_time=blocks, deleted_at=deleted, created_at=created, updated_at=updated))


def test_freshness_needs_an_open_day(db) -> None:
    response = _client(db, _user(db)).get(f"{BASE}/day/freshness")
    assert (response.status_code, response.json()["detail"]) == (409, "Journée non démarrée.")


def test_first_day_without_plan_is_fresh(db) -> None:
    user = _user(db)
    day = _day(db, user, datetime.now(UTC) - timedelta(minutes=5))
    db.commit()
    body = _client(db, user).get(f"{BASE}/day/freshness").json()
    assert (body["planning_day_id"], body["status"], body["reasons"], body["plan_id"]) == (str(day.id), "fresh", [], None)
    assert (body["calendar_changes"], body["constraints"], body["message"]) == ([], [], "Programme à jour.")


def test_changes_since_the_plan_and_the_prior_day_are_reported(db) -> None:
    user = _user(db)
    prior = _day(db, user, START - timedelta(hours=24), finished_at=START - timedelta(hours=10))
    failed = _mission(db, user, "Appeler le garage", "failed", prior.started_at, ended_at=prior.started_at + timedelta(hours=3))
    _mission(db, user, "Ancien échec", "failed", prior.started_at - timedelta(days=3), ended_at=prior.started_at - timedelta(days=2))
    standby = _mission(db, user, "Dossier URSSAF", "standby", prior.started_at)
    db.add(build_event(db, user_id=user.id, event_type="day.finished", idempotency_key=uuid4().hex,
                       payload={"planning_day_id": str(prior.id), "standby_mission_ids": [str(standby.id)],
                                "missions_returned_to_backlog": 2}))
    stale = _mission(db, user, "Mission restée active", "active", START - timedelta(hours=30))
    db.add(ImperiumDailyPlan(user_id=user.id, local_date=START.date(), plan_status="draft",
                             created_at=GENERATED, updated_at=GENERATED))
    after = GENERATED + timedelta(hours=2)
    _event(db, user, "Avant le plan", START + timedelta(hours=3), created=GENERATED - timedelta(days=1), updated=GENERATED - timedelta(hours=1))
    _event(db, user, "Rendez-vous déplacé", START + timedelta(hours=4), created=GENERATED - timedelta(days=1), updated=after)
    _event(db, user, "Nouveau rendez-vous", START + timedelta(hours=2), created=after, updated=after)
    _event(db, user, "Rendez-vous annulé", START + timedelta(hours=6), created=GENERATED - timedelta(days=2), updated=after, deleted=after)
    _event(db, user, "Créé puis annulé", START + timedelta(hours=5), created=after, updated=after, deleted=after)
    _event(db, user, "Hors journée", START + timedelta(hours=40), created=after, updated=after)
    _event(db, user, "Fini avant le démarrage", START - timedelta(hours=3), ends_at=START - timedelta(hours=2), created=after, updated=after)
    _event(db, user, "Sans blocage", START + timedelta(hours=1), created=after, updated=after, blocks=False)
    _day(db, user, START)
    db.commit()

    body = check_freshness(db, current_user=user, now=START + timedelta(minutes=1)).model_dump(mode="json")
    assert body["status"] == "review"
    assert body["reasons"] == ["calendar_changed", "stale_active_mission", "prior_day_unfinished", "constraints"]
    assert [(c["title"], c["change"]) for c in body["calendar_changes"]] == [
        ("Nouveau rendez-vous", "created"), ("Rendez-vous déplacé", "updated"), ("Rendez-vous annulé", "deleted"),
    ]
    assert body["stale_active_mission"]["id"] == str(stale.id)
    assert [m["id"] for m in body["prior_day_failed"]] == [str(failed.id)]
    assert ([m["title"] for m in body["prior_day_standby"]], body["prior_day_returned_to_backlog"]) == (["Dossier URSSAF"], 2)
    assert [c["code"] for c in body["constraints"]] == ["standby_decision"]
    assert body["message"] == "Des changements touchent ta journée : vérifie le programme."


def test_without_plan_the_calendar_is_compared_to_the_prior_closing(db) -> None:
    user = _user(db)
    closed = START - timedelta(hours=10)
    _day(db, user, START - timedelta(hours=24), finished_at=closed)
    _event(db, user, "Ajouté la nuit", START + timedelta(hours=2), created=closed + timedelta(hours=1), updated=closed + timedelta(hours=1))
    _event(db, user, "Ajouté avant la clôture", START + timedelta(hours=3), created=closed - timedelta(hours=1), updated=closed - timedelta(hours=1))
    _day(db, user, START)
    db.commit()
    body = check_freshness(db, current_user=user, now=START)
    assert ([c.title for c in body.calendar_changes], body.reasons) == (["Ajouté la nuit"], ["calendar_changed"])


def test_path_constraints_are_reported(db) -> None:
    user = _user(db)
    now = datetime.now(UTC)
    db.add(PathGhuslState(user_id=user.id, status="required", required_since=now - timedelta(hours=1), next_prayer="dhuhr",
                          replan_status="pending", idempotency_key=uuid4().hex, request_hash="x"))
    db.add(PathFast(user_id=user.id, fasting_date=date.today(), fasting_type="custom", status="active",
                    started_at=now - timedelta(hours=4), suhoor_at=now - timedelta(hours=4), iftar_at=now + timedelta(hours=6),
                    times_source="calculated", hydration_daytime_allowed=False, version=1, idempotency_key=uuid4().hex,
                    request_hash="y"))
    _day(db, user, now - timedelta(minutes=2))
    db.commit()
    body = _client(db, user).get(f"{BASE}/day/freshness").json()
    assert ([c["code"] for c in body["constraints"]], body["reasons"]) == (["ghusl_required", "fasting_active"], ["constraints"])
