"""PostgreSQL : mosquées enregistrées (PAT-09) — référence des horaires, propre à chaque utilisateur."""
from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("path mosques DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_path_dashboard, imperium_path_mosques, imperium_path_worship  # noqa: E402
from app.models.auth import User  # noqa: E402

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


def _client(db) -> TestClient:
    user_id = uuid4()
    db.execute(
        text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) VALUES (:id, :email, FALSE, now(), now())"),
        {"id": str(user_id), "email": f"mosque-{user_id}@example.test"},
    )
    db.commit()
    user = db.get(User, user_id)
    app = FastAPI()
    for module in (imperium_path_mosques, imperium_path_worship, imperium_path_dashboard):
        app.include_router(module.router, prefix=BASE)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def test_default_mosque_drives_times_for_its_owner_only(db) -> None:
    marseille, paris = _client(db), _client(db)
    before = marseille.get(f"{BASE}/prayers").json()["prayers"]
    created = marseille.post(f"{BASE}/mosques", headers=_key(), json={
        "name": "Mosquée du quartier", "latitude": "43.296500", "longitude": "5.369800", "is_default": True,
    })
    assert created.status_code == 201, created.text
    after = marseille.get(f"{BASE}/prayers").json()["prayers"]
    assert [p["adhan_at"] for p in after] != [p["adhan_at"] for p in before]
    assert marseille.get(f"{BASE}/dashboard").json()["qibla"]["location_source"] == "reference_mosque"
    assert [p["adhan_at"] for p in paris.get(f"{BASE}/prayers").json()["prayers"]] == [p["adhan_at"] for p in before]
    assert paris.get(f"{BASE}/dashboard").json()["qibla"] == {"direction_degrees": 119.2, "location_source": "default_city"}
    assert marseille.get(f"{BASE}/mosques").json()["times_source"] == "calculated"
    assert marseille.delete(f"{BASE}/mosques/{created.json()['id']}").status_code == 204


def test_one_default_versions_and_checks(db) -> None:
    client = _client(db)
    first = client.post(f"{BASE}/mosques", headers=_key(), json={"name": "A", "is_default": True}).json()
    key = _key()
    second = client.post(f"{BASE}/mosques", headers=key, json={"name": "B", "is_default": True})
    assert client.post(f"{BASE}/mosques", headers=key, json={"name": "B", "is_default": True}).status_code == 200
    items = {m["name"]: m for m in client.get(f"{BASE}/mosques").json()["items"]}
    assert (items["B"]["is_default"], items["A"]["is_default"], items["A"]["version"]) == (True, False, 2)
    stale = client.patch(f"{BASE}/mosques/{first['id']}", headers=_key(), json={"version": 1, "name": "A2"})
    assert (stale.status_code, stale.json()["code"]) == (409, "MOSQUE_VERSION_CONFLICT")
    renamed = client.patch(f"{BASE}/mosques/{first['id']}", headers=_key(), json={"version": 2, "name": "A2", "mawaqit_id": " abc "})
    assert (renamed.json()["name"], renamed.json()["mawaqit_id"], renamed.json()["version"]) == ("A2", "abc", 3)
    assert client.patch(f"{BASE}/mosques/{first['id']}", headers=_key(), json={"version": 3, "latitude": "1"}).status_code == 422
    assert client.post(f"{BASE}/mosques", headers=_key(), json={"name": " "}).status_code == 422
    assert client.delete(f"{BASE}/mosques/{second.json()['id']}").status_code == 204
    assert client.delete(f"{BASE}/mosques/{second.json()['id']}").status_code == 404
    for mosque in client.get(f"{BASE}/mosques").json()["items"]:
        client.delete(f"{BASE}/mosques/{mosque['id']}")
