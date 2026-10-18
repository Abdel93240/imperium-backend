"""PostgreSQL : calendrier hégirien Path — confirmation, dates religieuses, événements personnels."""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("path calendar DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_path_calendar, imperium_path_dashboard  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.services.path import fasting  # noqa: E402

BASE = "/api/imperium/path/calendar"


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
        {"id": str(user_id), "email": f"hijri-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_path_calendar.router, prefix="/api/imperium/path")
    app.include_router(imperium_path_dashboard.router, prefix="/api/imperium/path")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def _events(client, start, end):
    return {item["code"]: item for item in client.get(f"{BASE}/events", params={"from_day": start, "to_day": end}).json()["items"]}


def test_today_and_default_window(db) -> None:
    client = _client(db, _user(db))
    today = client.get(f"{BASE}/hijri").json()
    assert today["gregorian"] == fasting.paris_today().isoformat() and today["status"] == "predicted"
    window = client.get(f"{BASE}/events").json()
    assert (date.fromisoformat(window["to_day"]) - date.fromisoformat(window["from_day"])).days == 13
    assert client.get(f"{BASE}/events", params={"from_day": "2026-01-01", "to_day": "2027-12-31"}).status_code == 422


def test_confirmation_removes_the_duplicate(db) -> None:
    user = _user(db)
    client = _client(db, user)
    before = _events(client, "2026-02-10", "2026-03-25")
    assert before["ramadan_start"]["dates"] == ["2026-02-18", "2026-02-19"]
    assert before["ramadan_start"]["status"] == "predicted"
    too_far = client.post(f"{BASE}/confirm-date", headers=_key(),
                          json={"hijri_year": 1447, "hijri_month": 9, "first_day": "2026-02-21"})
    assert too_far.status_code == 422
    confirmed = client.post(f"{BASE}/confirm-date", headers=_key(),
                            json={"hijri_year": 1447, "hijri_month": 9, "first_day": "2026-02-19"})
    assert confirmed.json() == {"hijri_year": 1447, "hijri_month": 9, "month_name": "Ramadan",
                                "first_day": "2026-02-19", "status": "confirmed"}
    after = _events(client, "2026-02-10", "2026-03-25")
    assert (after["ramadan_start"]["dates"], after["ramadan_start"]["status"]) == (["2026-02-19"], "confirmed")
    assert after["eid_al_fitr"]["dates"] == ["2026-03-20", "2026-03-21"]
    event = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "path.calendar.date_confirmed"))
    assert event.payload["first_day"] == "2026-02-19"
    corrected = client.post(f"{BASE}/confirm-date", headers=_key(),
                            json={"hijri_year": 1447, "hijri_month": 9, "first_day": "2026-02-18"})
    assert corrected.json()["first_day"] == "2026-02-18"


def test_confirmation_is_not_made_in_advance(db) -> None:
    client = _client(db, _user(db))
    future = fasting.paris_today() + timedelta(days=60)
    hijri_day = client.get(f"{BASE}/hijri", params={"day": future.isoformat()}).json()
    month = hijri_day["hijri_month"] % 12 + 1
    year = hijri_day["hijri_year"] + (1 if month == 1 else 0)
    predicted = _events(client, future.isoformat(), (future + timedelta(days=40)).isoformat())
    start = next(i for i in predicted.values() if i["hijri_month"] == month and i["hijri_day"] == 13)["dates"][0]
    first = (date.fromisoformat(start) - timedelta(days=12)).isoformat()
    refused = client.post(f"{BASE}/confirm-date", headers=_key(), json={"hijri_year": year, "hijri_month": month, "first_day": first})
    assert refused.status_code == 422


def test_personal_events_yearly_or_once(db) -> None:
    user = _user(db)
    client = _client(db, user)
    yearly = client.post(f"{BASE}/personal-events", headers=_key(),
                         json={"label": "Dars du cheikh", "hijri_month": 9, "hijri_day": 5}).json()
    once = client.post(f"{BASE}/personal-events", headers=_key(),
                       json={"label": "Rappel", "hijri_year": 1448, "hijri_month": 9, "hijri_day": 5}).json()
    in_1447 = _events(client, "2026-02-10", "2026-03-25")
    assert f"personal:{yearly['id']}" in in_1447 and f"personal:{once['id']}" not in in_1447
    assert in_1447[f"personal:{yearly['id']}"]["dates"] == ["2026-02-22", "2026-02-23"]
    added = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "path.calendar.event_added"))
    assert "Dars" not in str(added.payload)
    assert len(client.get(f"{BASE}/personal-events").json()) == 2
    assert client.delete(f"{BASE}/personal-events/{yearly['id']}").status_code == 204
    assert client.delete(f"{BASE}/personal-events/{yearly['id']}").status_code == 404
    assert client.post(f"{BASE}/personal-events", headers=_key(), json={"label": " ", "hijri_month": 1, "hijri_day": 1}).status_code == 422


def test_dashboard_shows_hijri_and_white_day_banner(db) -> None:
    client = _client(db, _user(db))
    events = _events(client, "2026-07-01", "2026-07-31")
    white = events["white_day_13"]["dates"][0]
    body = client.get("/api/imperium/path/dashboard", params={"day": white}).json()
    assert body["hijri"]["hijri_day"] == 13
    assert [b["kind"] for b in body["banners"]] == ["white_days"]
    ramadan = client.get("/api/imperium/path/dashboard", params={"day": "2026-02-25"}).json()
    assert [b["message"] for b in ramadan["banners"]] == ["Ramadan, jour 8."]
