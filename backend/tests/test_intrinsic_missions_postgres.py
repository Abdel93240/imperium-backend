"""PostgreSQL : missions hors projet (paperasse, démarches…) — liste, création, modification, « Faite »."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("Intrinsic missions DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_operations  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.imperium import ImperiumMission  # noqa: E402
from app.schemas.operations import ProjectCreate, ProjectMissionCreate  # noqa: E402
from app.services.imperium import operations  # noqa: E402


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
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"im-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_operations.router, prefix="/api/imperium")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _create(client, key=None, **body) -> dict:
    response = client.post("/api/imperium/intrinsic-missions", json=body, headers={"Idempotency-Key": key or str(uuid4())})
    assert response.status_code == 201, response.text
    return response.json()


def test_project_less_missions_are_listed_created_edited_and_done(db) -> None:
    user = _user(db)
    client = _client(db, user)
    soon = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    later = (datetime.now(UTC) + timedelta(days=9)).isoformat()
    caf = _create(client, title=" Formulaire CAF ", deadline_at=later, domain="finance")
    key = str(uuid4())
    mairie = _create(client, key=key, title="Passer à la mairie", description="Carte d'identité", deadline_at=soon,
                     estimated_minutes=45)
    assert _create(client, key=key, title="Passer à la mairie")["id"] == mairie["id"]  # clé rejouée : rien de plus
    undated = _create(client, title="Trier les papiers")
    project = operations.create_project(db, current_user=user, payload=ProjectCreate(title="Site"), idempotency_key="p")
    operations.add_project_mission(db, current_user=user, project_id=project.id, idempotency_key="pm",
                                   payload=ProjectMissionCreate(title="Maquette"))

    listed = client.get("/api/imperium/intrinsic-missions").json()
    assert [m["title"] for m in listed["missions"]] == ["Passer à la mairie", "Formulaire CAF", "Trier les papiers"]
    assert listed["done"] == [] and caf["domain"] == "finance" and mairie["description"] == "Carte d'identité"
    row = db.get(ImperiumMission, mairie["id"])
    assert (row.project_id, row.status) == (None, "backlog")
    event = db.scalar(select(Event).where(Event.id == row.created_by_event_id))
    assert event.payload["project_id"] is None and event.payload["created_by"] == "manual"

    edited = client.patch(f"/api/imperium/missions/{undated['id']}",
                          json={"domain": "health", "planned_start_at": soon, "title": "Trier les papiers santé"})
    assert edited.status_code == 200 and edited.json()["title"] == "Trier les papiers santé"
    row = db.get(ImperiumMission, undated["id"])
    assert row.domain == "health" and row.planned_start_at is not None
    client.patch(f"/api/imperium/missions/{caf['id']}", json={"deadline_at": None})
    assert db.get(ImperiumMission, caf["id"]).deadline_at is None  # effacée

    done = client.post(f"/api/imperium/missions/{mairie['id']}/done")
    assert done.status_code == 200 and done.json()["status"] == "completed"
    assert client.post(f"/api/imperium/missions/{mairie['id']}/done").status_code == 409  # déjà faite
    row = db.get(ImperiumMission, mairie["id"])
    assert row.completion_note == "Faite hors du plan du jour." and row.ended_by_event_id is not None
    assert client.delete(f"/api/imperium/missions/{undated['id']}").status_code == 204
    listed = client.get("/api/imperium/intrinsic-missions").json()
    assert [m["title"] for m in listed["missions"]] == ["Formulaire CAF"]
    assert [m["title"] for m in listed["done"]] == ["Passer à la mairie"]
    assert client.post("/api/imperium/intrinsic-missions", json={"title": "x"}).status_code == 400  # clé obligatoire
    assert client.post("/api/imperium/intrinsic-missions", json={"title": " "},
                       headers={"Idempotency-Key": "k"}).status_code == 422
