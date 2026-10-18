"""PostgreSQL : détail d'une mosquée (PAT-08) et règle des 48 h du cache MAWAQIT (doc 41 §6.3)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("path mosque detail DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_path_dashboard, imperium_path_mosques, imperium_path_settings  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.path import PathMawaqitCache  # noqa: E402
from app.services.path.prayer import prayer_times  # noqa: E402

BASE = "/api/imperium/path"
DAY = date(2026, 7, 15)
TIMES = {"fajr": "03:36", "dhuhr": "13:57", "asr": "18:18", "maghrib": "21:50", "isha": "23:15"}


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
        {"id": str(user_id), "email": f"mdetail-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    for module in (imperium_path_mosques, imperium_path_settings, imperium_path_dashboard):
        app.include_router(module.router, prefix=BASE)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _mosque(client, **extra) -> dict:
    body = {"name": "Grande Mosquée", "latitude": "48.842000", "longitude": "2.355000", "is_default": True, **extra}
    response = client.post(f"{BASE}/mosques", headers={"Idempotency-Key": uuid4().hex}, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _cache(db, mosque_id, age_hours) -> None:
    db.add(PathMawaqitCache(mosque_id=mosque_id, date=DAY, prayer_times=TIMES,
                            fetched_at=datetime.now(UTC) - timedelta(hours=age_hours)))
    db.commit()


def test_fresh_mawaqit_times_with_qibla(db) -> None:
    user = _user(db)
    client = _client(db, user)
    mosque = _mosque(client)
    _cache(db, mosque["id"], 2)
    body = client.get(f"{BASE}/mosques/{mosque['id']}", params={"day": DAY.isoformat()}).json()
    assert (body["times"], body["times_source"], body["mawaqit_data_quality"], body["message"]) == (TIMES, "mawaqit", "fresh", None)
    assert (body["calculation_location"], body["qibla_direction_degrees"]) == ("mosque", 119.2)
    assert set(body["calculated_times"]) == set(TIMES) and body["calculated_times"]["asr"] != "18:18"


def test_stale_then_expired_cache(db) -> None:
    user = _user(db)
    client = _client(db, user)
    mosque = _mosque(client)
    _cache(db, mosque["id"], 30)
    stale = client.get(f"{BASE}/mosques/{mosque['id']}", params={"day": DAY.isoformat()}).json()
    assert (stale["times_source"], stale["mawaqit_data_quality"]) == ("mawaqit", "stale")
    assert stale["message"] == "Horaires MAWAQIT de plus de 24 h : à vérifier."
    assert prayer_times(db, DAY, user_id=user.id)[1] == "mawaqit"
    db.execute(text("UPDATE path_mawaqit_cache SET fetched_at = now() - interval '50 hours' WHERE mosque_id = :id"),
               {"id": mosque["id"]})
    db.commit()
    expired = client.get(f"{BASE}/mosques/{mosque['id']}", params={"day": DAY.isoformat()}).json()
    assert (expired["times_source"], expired["mawaqit_data_quality"], expired["mawaqit_times"]) == ("calculated", "expired", TIMES)
    assert expired["times"] == expired["calculated_times"]
    assert prayer_times(db, DAY, user_id=user.id)[1] == "calculated"


def test_mosque_without_coordinates_uses_the_settings_city(db) -> None:
    user = _user(db)
    client = _client(db, user)
    client.patch(f"{BASE}/settings", headers={"Idempotency-Key": uuid4().hex},
                 json={"version": 0, "city": {"name": "Marseille", "latitude": "43.296500", "longitude": "5.369800"}})
    mosque = _mosque(client, latitude=None, longitude=None, is_default=False)
    body = client.get(f"{BASE}/mosques/{mosque['id']}").json()
    assert (body["mawaqit_data_quality"], body["times_source"], body["calculation_location"]) == ("missing", "calculated", "city")
    assert (body["qibla_direction_degrees"], body["mawaqit_times"]) == (None, None)
    assert client.get(f"{BASE}/dashboard").json()["qibla"]["location_source"] == "settings_city"
    assert _client(db, _user(db)).get(f"{BASE}/mosques/{mosque['id']}").status_code == 404
    assert client.get(f"{BASE}/mosques/{uuid4()}").status_code == 404
