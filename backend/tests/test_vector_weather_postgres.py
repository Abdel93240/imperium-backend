"""PostgreSQL : relevés météo Open-Meteo, variables météo des offres, flux du tableau de bord (doc 57 §5.5)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("vector weather DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, delete, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_vector  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.rides import RidesWeatherReading  # noqa: E402
from app.services.vector import weather  # noqa: E402

BASE = "/api/imperium/vector"


def _body(precip: float, code: int) -> dict:
    return {
        "current": {"temperature_2m": 11.4, "precipitation": precip, "weather_code": code, "wind_speed_10m": 18.0,
                    "visibility": 24000},
        "hourly": {"time": ["2026-10-14T12:00", "2026-10-14T13:00"], "temperature_2m": [11.4, 12.0],
                   "precipitation": [precip, 0.0], "precipitation_probability": [80, 20], "weather_code": [code, 3]},
    }


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    with Session(engine) as session:
        session.execute(delete(RidesWeatherReading))
        session.commit()
        yield session
        session.rollback()
        session.execute(delete(RidesWeatherReading))
        session.commit()


def _client(db) -> tuple[TestClient, str]:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"w-{user_id}@example.test"})
    db.commit()
    user = db.get(User, user_id)
    app = FastAPI()
    app.include_router(imperium_vector.router, prefix=BASE)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    session = client.post(f"{BASE}/sessions", headers={"Idempotency-Key": uuid4().hex}, json={}).json()
    return client, session["id"]


def _offer(client, session_id, at: datetime) -> dict:
    response = client.post(f"{BASE}/sessions/{session_id}/offers", headers={"Idempotency-Key": uuid4().hex},
                           json={"price_cents": 2000, "estimated_duration_min": 25, "offered_at": at.isoformat()})
    assert response.status_code == 201, response.text
    return response.json()["features"]


def test_offer_reads_the_weather_of_its_time(db) -> None:
    client, session_id = _client(db)
    now = datetime.now(UTC)
    assert _offer(client, session_id, now)["weather_is_rain"] is None  # aucun relevé : rien d'inventé
    weather.refresh(db, now=now - timedelta(minutes=20), fetcher=lambda lat, lng: _body(1.2, 61))
    db.commit()
    f = _offer(client, session_id, now)
    assert (f["weather_temp_c"], f["weather_precip_mm"], f["weather_is_rain"], f["weather_is_snow"]) == (11.4, 1.2, True, False)
    assert (f["weather_visibility_km"], f["weather_wind_kmh"], f["weather_rain_next_hour_pct"]) == (24.0, 18.0, 80)
    late = _offer(client, session_id, now - timedelta(hours=3))  # relevé postérieur à l'offre : pas utilisé
    assert late["weather_temp_c"] is None


def test_stale_reading_is_not_used_and_feed_says_so(db) -> None:
    client, session_id = _client(db)
    assert client.get(f"{BASE}/feeds/weather").json()["status"] == "unavailable"
    now = datetime.now(UTC)
    weather.refresh(db, now=now - timedelta(hours=2), fetcher=lambda lat, lng: _body(0.0, 73))
    db.commit()
    assert _offer(client, session_id, now)["weather_is_snow"] is None
    feed = client.get(f"{BASE}/feeds/weather").json()
    assert (feed["status"], feed["now"]["weather_code"], len(feed["hours"])) == ("stale", 73, 2)
    weather.refresh(db, now=now, fetcher=lambda lat, lng: _body(0.0, 73))
    db.commit()
    assert client.get(f"{BASE}/feeds/weather").json()["status"] == "ok"
    assert _offer(client, session_id, now)["weather_is_snow"] is True


def test_bad_answer_and_old_readings(db) -> None:
    with pytest.raises(weather.WeatherUnavailableError):
        weather.refresh(db, fetcher=lambda lat, lng: {"current": None})
    db.rollback()
    now = datetime.now(UTC)
    weather.refresh(db, now=now - timedelta(days=9), fetcher=lambda lat, lng: _body(0.0, 1))
    weather.refresh(db, now=now, fetcher=lambda lat, lng: _body(0.0, 1))
    db.commit()
    assert len(list(db.scalars(select(RidesWeatherReading)))) == 1  # plus de 7 jours : effacé
