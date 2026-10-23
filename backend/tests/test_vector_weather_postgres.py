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
from sqlalchemy import create_engine, delete, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_vector  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.rides import RidesWeatherCellReading  # noqa: E402
from app.services.vector import weather  # noqa: E402

BASE = "/api/imperium/vector"


def _fetcher(rain_cells: set[str], *, past_mm: float = 0.0, next_mm: float = 0.0, code: int = 61, at: datetime):
    """Faux Open-Meteo : pluie maintenant sur `rain_cells`, quarts d'heure autour de `at` (heure de Paris)."""
    local = at.astimezone(weather.PARIS).replace(second=0, microsecond=0, tzinfo=None)
    start = local.replace(minute=local.minute - local.minute % 15) - timedelta(minutes=30)
    times = [(start + timedelta(minutes=15 * i)).isoformat(timespec="minutes") for i in range(10)]

    def fetch(batch):
        out = []
        for cell in batch:
            wet = cell.code in rain_cells
            out.append({
                "current": {"temperature_2m": 11.4, "precipitation": 1.2 if wet else 0.0, "weather_code": code if wet else 2,
                            "wind_speed_10m": 18.0},
                "minutely_15": {"time": times, "precipitation": [past_mm, past_mm] + [next_mm] * 8,
                                "weather_code": [2] * 10},
            })
        return out
    return fetch


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    with Session(engine) as session:
        session.execute(delete(RidesWeatherCellReading))
        session.commit()
        yield session
        session.rollback()
        session.execute(delete(RidesWeatherCellReading))
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


def _offer(client, session_id, at: datetime, **extra) -> dict:
    response = client.post(f"{BASE}/sessions/{session_id}/offers", headers={"Idempotency-Key": uuid4().hex},
                           json={"price_cents": 2000, "estimated_duration_min": 25, "offered_at": at.isoformat(), **extra})
    assert response.status_code == 201, response.text
    return response.json()["features"]


NOTRE_DAME = {"driver_lat": "48.853400", "driver_lng": "2.348800"}


def test_grid_covers_the_region() -> None:
    grid = weather.cells()
    assert len(grid) == 192 and len({c.code for c in grid}) == 192
    assert weather.cell_at(48.8534, 2.3488).ring == "A"          # Paris : case fine
    assert weather.cell_at(48.40, 2.70).ring == "B"              # Fontainebleau : case large
    assert weather.cell_at(49.0097, 2.5479).code == "AP-CDG"


def test_offer_gets_the_weather_of_its_own_cell(db) -> None:
    client, session_id = _client(db)
    now = datetime.now(UTC)
    assert _offer(client, session_id, now, **NOTRE_DAME)["weather_pickup_is_rain"] is None  # aucun relevé
    here = weather.cell_at(48.8534, 2.3488).code
    weather.refresh(db, now=now - timedelta(minutes=10), fetcher=_fetcher({here}, next_mm=0.4, at=now))
    db.commit()
    f = _offer(client, session_id, now, **NOTRE_DAME)
    assert (f["weather_pickup_cell"], f["weather_pickup_is_rain"], f["weather_pickup_rain_onset"]) == (here, True, True)
    assert (f["weather_pickup_rain_last_30min"], f["weather_pickup_rain_next_60min_mm"]) == (False, 1.6)
    assert f["weather_paris_is_rain"] is False                    # il pleut sur une case, pas au centre
    assert f["weather_rain_share_paris"] == round(1 / 72, 3) and f["weather_rain_share_idf"] == 0.0
    far = _offer(client, session_id, now, driver_lat="48.400000", driver_lng="2.700000")
    assert (far["weather_pickup_is_rain"], far["weather_pickup_temp_c"]) == (False, 11.4)
    blind = _offer(client, session_id, now)                      # sans position : seulement la région
    assert blind["weather_pickup_cell"] is None and blind["weather_rain_share_paris"] is not None


def test_stale_pass_is_ignored_and_feed_reports_it(db) -> None:
    client, session_id = _client(db)
    assert client.get(f"{BASE}/feeds/weather").json()["status"] == "unavailable"
    now = datetime.now(UTC)
    weather.refresh(db, now=now - timedelta(hours=1), fetcher=_fetcher({weather.CENTER_CELL}, past_mm=0.5, at=now))
    db.commit()
    assert _offer(client, session_id, now, **NOTRE_DAME)["weather_pickup_is_rain"] is None
    feed = client.get(f"{BASE}/feeds/weather").json()
    assert (feed["status"], feed["cells"], feed["cells_paris"], len(feed["hours"])) == ("stale", 192, 72, 10)
    assert feed["now"]["precipitation_mm"] == 1.2


def test_job_calls_only_during_a_session(db, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(weather, "fetch", lambda batch: calls.append(len(batch)) or _fetcher(set(), at=datetime.now(UTC))(batch))

    class Ctx:
        def __init__(self): self.db, self.items_in, self.items_out, self.detail = db, 0, 0, None

    db.execute(text("UPDATE rides_sessions SET status = 'completed', ended_at = now(), paused_at = NULL "
                    "WHERE status IN ('active', 'paused')"))
    db.commit()
    ctx = Ctx()
    weather.weather_refresh_job(ctx, None)
    assert (ctx.detail, calls) == ({"skipped": "no_open_session"}, [])
    _client(db)  # ouvre une session
    weather.weather_refresh_job(ctx, None)
    assert ctx.detail == {"cells": 192} and calls == [100, 92]
