"""PostgreSQL : ghusl Path — état requis, mission et replanification Imperium, adresses (doc 41 §10)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("path ghusl DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_path_ghusl  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.imperium import ImperiumDailyPlan, ImperiumMission, PlanningDay, PlanningReplanEvent  # noqa: E402
from app.schemas.imperium import ReplanRequestCreate  # noqa: E402
from app.services.imperium import replan  # noqa: E402
from app.services.path import fasting  # noqa: E402

BASE = "/api/imperium/path"


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
        {"id": str(user_id), "email": f"ghusl-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_path_ghusl.router, prefix=BASE)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def _open_day(db, user) -> None:
    today = fasting.paris_today()
    db.add(PlanningDay(user_id=user.id, started_at=datetime.now(UTC) - timedelta(hours=3), start_local_date=today,
                       timezone="Europe/Paris", felt_energy=3, idempotency_key=f"day-{uuid4().hex}"))
    db.add(ImperiumDailyPlan(user_id=user.id, local_date=today, timezone="Europe/Paris", plan_status="active",
                             generated_from={}, plan_blocks=[{"block_type": "mission", "title": "Lecture"}]))
    db.commit()


def _events(db, user, event_type) -> list[Event]:
    return list(db.scalars(select(Event).where(Event.user_id == user.id, Event.event_type == event_type)))


def test_activation_creates_the_mission_even_without_an_open_day(db) -> None:
    user = _user(db)
    client = _client(db, user)
    assert client.get(f"{BASE}/ghusl").json() == {"ghusl_required": False, "state": None, "message": None}
    activated = client.post(f"{BASE}/ghusl/activate", headers=_key())
    assert activated.status_code == 201, activated.text
    state = activated.json()
    assert (state["status"], state["replan_status"], state["replan_event_id"]) == ("required", "no_open_day", None)
    assert state["next_prayer"] in ("fajr", "dhuhr", "asr", "maghrib", "isha")
    mission = db.get(ImperiumMission, state["mission_id"])
    assert (mission.status, mission.domain, mission.priority_level) == ("backlog", "religious", 9)
    assert mission.title.startswith("Faire le ghusl avant ")
    event = _events(db, user, "path.ghusl.required")[0]
    assert set(event.payload) == {"ghusl_state_id", "required_since", "source"}
    assert event.privacy_level == "very_high"
    current = client.get(f"{BASE}/ghusl").json()
    assert current["ghusl_required"] is True and current["state"]["id"] == state["id"]
    assert current["message"] == "Ghusl requis : mission créée. Aucune journée ouverte, pas de replanification."


def test_activation_replans_immediately_despite_the_debounce(db) -> None:
    user = _user(db)
    client = _client(db, user)
    _open_day(db, user)
    manual, _ = replan.request_replan(
        db, current_user=user, payload=ReplanRequestCreate(reason_category="fatigue", reason_detail="Longue nuit, j'allège."),
        idempotency_key=uuid4().hex, request_method="POST", request_path="/t",
    )
    replan.cancel_replan(db, current_user=user, replan_id=manual.id)
    state = client.post(f"{BASE}/ghusl/activate", headers=_key()).json()
    assert state["replan_status"] == "requested"
    row = db.get(PlanningReplanEvent, state["replan_event_id"])
    assert (row.trigger, row.hook_type, row.status) == ("hook", "ghusl_required", "requested")


def test_replan_already_in_progress_is_reported(db) -> None:
    user = _user(db)
    client = _client(db, user)
    _open_day(db, user)
    replan.request_replan(
        db, current_user=user, payload=ReplanRequestCreate(reason_category="fatigue", reason_detail="Longue nuit, j'allège."),
        idempotency_key=uuid4().hex, request_method="POST", request_path="/t",
    )
    state = client.post(f"{BASE}/ghusl/activate", headers=_key()).json()
    assert (state["replan_status"], state["mission_id"] is not None) == ("replan_in_progress", True)


def test_second_activation_conflicts_and_replay_dedupes(db) -> None:
    user = _user(db)
    client = _client(db, user)
    key = _key()
    first = client.post(f"{BASE}/ghusl/activate", headers=key).json()
    replay = client.post(f"{BASE}/ghusl/activate", headers=key)
    assert (replay.status_code, replay.json()["id"]) == (200, first["id"])
    second = client.post(f"{BASE}/ghusl/activate", headers=_key())
    assert (second.status_code, second.json()["code"], second.json()["current"]["id"]) == (409, "GHUSL_STATE_CONFLICT", first["id"])
    assert len(list(db.scalars(select(ImperiumMission).where(ImperiumMission.user_id == user.id)))) == 1


def test_completion_finishes_the_mission_without_replan(db) -> None:
    user = _user(db)
    client = _client(db, user)
    state = client.post(f"{BASE}/ghusl/activate", headers=_key()).json()
    key = _key()
    done = client.post(f"{BASE}/ghusl/complete", headers=key, json={"state_id": state["id"]})
    assert done.status_code == 200, done.text
    assert (done.json()["status"], done.json()["completed_at"] is not None) == ("completed", True)
    assert client.post(f"{BASE}/ghusl/complete", headers=key, json={"state_id": state["id"]}).json() == done.json()
    mission = db.get(ImperiumMission, state["mission_id"])
    db.refresh(mission)
    assert (mission.status, mission.completion_note) == ("completed", "Ghusl fait (Path).")
    assert _events(db, user, "planning.mission.completed")[0].payload["mission_id"] == state["mission_id"]
    assert _events(db, user, "path.ghusl.completed")[0].payload["mission_completed"] is True
    again = client.post(f"{BASE}/ghusl/complete", headers=_key(), json={"state_id": state["id"]})
    assert (again.status_code, again.json()["code"]) == (409, "GHUSL_STATE_CONFLICT")
    assert client.get(f"{BASE}/ghusl").json()["ghusl_required"] is False
    assert client.post(f"{BASE}/ghusl/activate", headers=_key()).status_code == 201  # nouvelle activation possible
    assert db.scalar(select(PlanningReplanEvent).where(PlanningReplanEvent.user_id == user.id)) is None


def test_completion_leaves_a_closed_mission_alone(db) -> None:
    user = _user(db)
    client = _client(db, user)
    state = client.post(f"{BASE}/ghusl/activate", headers=_key()).json()
    db.get(ImperiumMission, state["mission_id"]).status = "cancelled"
    db.commit()
    done = client.post(f"{BASE}/ghusl/complete", headers=_key(), json={"state_id": state["id"]})
    assert done.status_code == 200
    assert db.get(ImperiumMission, state["mission_id"]).status == "cancelled"
    assert _events(db, user, "path.ghusl.completed")[0].payload["mission_completed"] is False
    assert client.post(f"{BASE}/ghusl/complete", headers=_key(), json={"state_id": str(uuid4())}).status_code == 404


def test_addresses_default_versions_and_delete(db) -> None:
    user = _user(db)
    client = _client(db, user)
    home = client.post(f"{BASE}/ghusl-addresses", headers=_key(),
                       json={"label": "Maison", "address_type": "home", "is_default": True}).json()
    gym = client.post(f"{BASE}/ghusl-addresses", headers=_key(),
                      json={"label": "Salle", "address_type": "gym", "latitude": "48.85", "longitude": "2.35", "is_default": True})
    assert gym.status_code == 201, gym.text
    items = {item["label"]: item for item in client.get(f"{BASE}/ghusl-addresses").json()["items"]}
    assert (items["Salle"]["is_default"], items["Maison"]["is_default"], items["Maison"]["version"]) == (True, False, 2)
    stale = client.patch(f"{BASE}/ghusl-addresses/{home['id']}", headers=_key(), json={"version": 1, "label": "Chez moi"})
    assert (stale.status_code, stale.json()["code"]) == (409, "GHUSL_ADDRESS_VERSION_CONFLICT")
    renamed = client.patch(f"{BASE}/ghusl-addresses/{home['id']}", headers=_key(),
                           json={"version": 2, "label": "Chez moi", "is_default": True})
    assert (renamed.status_code, renamed.json()["label"], renamed.json()["version"]) == (200, "Chez moi", 3)
    assert {i["label"]: i["is_default"] for i in client.get(f"{BASE}/ghusl-addresses").json()["items"]} == {"Chez moi": True, "Salle": False}
    half = client.patch(f"{BASE}/ghusl-addresses/{home['id']}", headers=_key(), json={"version": 3, "latitude": "48.8"})
    assert half.status_code == 422
    assert client.post(f"{BASE}/ghusl-addresses", headers=_key(),
                       json={"label": "X", "address_type": "other", "latitude": "1"}).status_code == 422
    assert client.delete(f"{BASE}/ghusl-addresses/{home['id']}").status_code == 204
    assert client.delete(f"{BASE}/ghusl-addresses/{home['id']}").status_code == 404
    event = _events(db, user, "path.ghusl_address.updated")[0]
    assert "Maison" not in str(event.payload)
