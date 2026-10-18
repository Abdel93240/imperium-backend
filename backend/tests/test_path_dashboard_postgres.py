"""PostgreSQL : tableau de bord Path (PAT-01) et annulation d'un jeûne démarré par erreur."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("path dashboard DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import (  # noqa: E402
    imperium_path_dashboard,
    imperium_path_devotion,
    imperium_path_ghusl,
    imperium_path_sadaqa,
    imperium_path_worship,
    imperium_pulse_hydration,
)
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.path import PathFast  # noqa: E402
from app.services.path import dashboard, fasting  # noqa: E402

PATH = "/api/imperium/path"


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
        {"id": str(user_id), "email": f"pathdash-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    for module in (imperium_path_dashboard, imperium_path_devotion, imperium_path_ghusl, imperium_path_sadaqa,
                   imperium_path_worship):
        app.include_router(module.router, prefix=PATH)
    app.include_router(imperium_pulse_hydration.router, prefix="/api/imperium/pulse")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def test_empty_dashboard_has_times_and_no_judgement(db) -> None:
    client = _client(db, _user(db))
    body = client.get(f"{PATH}/dashboard").json()
    assert body["day"] == fasting.paris_today().isoformat()
    assert [p["status"] for p in body["prayers"]["prayers"]] == [None] * 5
    assert body["next_prayer"]["countdown_seconds"] > 0
    assert (body["fasting"]["fasting_active"], body["ghusl"]["ghusl_required"], body["adhkar"]) == (False, False, [])
    assert (body["quran"]["started"], body["sadaqa"]["target"]) == (False, "0.00")
    assert body["qibla"] == {"direction_degrees": 119.2, "location_source": "default_city"}
    assert body["banners"] == []


def test_dashboard_gathers_each_domain(db) -> None:
    client = _client(db, _user(db))
    client.post(f"{PATH}/fasts", headers=_key(), json={"fasting_type": "temporary"})
    client.post(f"{PATH}/ghusl/activate", headers=_key())
    routine = client.post(f"{PATH}/adhkar/routines", headers=_key(),
                          json={"label": "Istighfar", "adhkar_type": "istighfar", "target_count": 100}).json()
    client.post(f"{PATH}/adhkar/routines/{routine['id']}/increment", headers=_key(), json={"amount": 40})
    client.post(f"{PATH}/quran/progress", headers=_key(), json={"page": 12})
    yesterday = (fasting.paris_today() - timedelta(days=1)).isoformat()
    client.post(f"{PATH}/prayers/fajr/mark", headers=_key(), json={"prayer_date": yesterday, "status": "accomplished"})
    body = client.get(f"{PATH}/dashboard").json()
    assert [b["kind"] for b in body["banners"]] == ["ghusl_required", "fasting"]
    assert body["adhkar"][0]["counters"][0]["count"] == 40
    assert body["quran"]["resume_page"] == 13
    past = client.get(f"{PATH}/dashboard", params={"day": yesterday}).json()
    assert past["next_prayer"] is None and past["prayers"]["prayers"][0]["status"] == "accomplished"


def test_next_prayer_rolls_to_tomorrow_fajr_after_isha(db) -> None:
    late = datetime.combine(fasting.paris_today(), datetime.max.time(), tzinfo=fasting.PARIS) - timedelta(minutes=1)
    upcoming = dashboard.next_prayer(db, late)
    assert upcoming.prayer_name == "fajr" and upcoming.adhan_at.astimezone(fasting.PARIS).date() > late.date()


def test_cancel_a_fast_started_by_mistake(db) -> None:
    user = _user(db)
    client = _client(db, user)
    fast = client.post(f"{PATH}/fasts", headers=_key(), json={"fasting_type": "temporary"}).json()
    iftar = datetime.fromisoformat(fast["iftar_at"])
    assert client.post(f"{PATH}/fasts/{fast['id']}/cancel", headers=_key(), json={"confirm": False}).status_code == 422
    key = _key()
    cancelled = client.post(f"{PATH}/fasts/{fast['id']}/cancel", headers=key, json={"confirm": True})
    assert cancelled.json() == {"cancelled": True, "fast_id": fast["id"]}
    assert client.post(f"{PATH}/fasts/{fast['id']}/cancel", headers=key, json={"confirm": True}).json() == cancelled.json()
    assert db.get(PathFast, fast["id"]) is None
    assert db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "path.fasting.cancelled")) is not None
    water = client.post("/api/imperium/pulse/hydration-logs", headers=_key(),
                        json={"amount_ml": 250, "logged_at": (iftar - timedelta(hours=2)).isoformat(), "decrement_stock": False})
    assert water.status_code == 201
    assert client.post(f"{PATH}/fasts", headers=_key(), json={"fasting_type": "monday_thursday"}).status_code == 201


def test_only_an_active_fast_can_be_cancelled(db) -> None:
    user = _user(db)
    client = _client(db, user)
    fast = client.post(f"{PATH}/fasts", headers=_key(), json={"fasting_type": "temporary"}).json()
    row = db.get(PathFast, fast["id"])
    row.status, row.ended_at = "ended", datetime.now(UTC)
    db.commit()
    refused = client.post(f"{PATH}/fasts/{fast['id']}/cancel", headers=_key(), json={"confirm": True})
    assert (refused.status_code, refused.json()["code"]) == (409, "FAST_STATE_CONFLICT")
    assert client.post(f"{PATH}/fasts/{uuid4()}/cancel", headers=_key(), json={"confirm": True}).status_code == 404
