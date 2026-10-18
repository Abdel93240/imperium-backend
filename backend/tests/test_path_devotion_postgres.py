"""PostgreSQL : adhkar (doc 41 §11) et progression du Coran (doc 41 §12)."""
from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("path devotion DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_path_devotion  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.services.path import adhkar, quran_index  # noqa: E402

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
        {"id": str(user_id), "email": f"devotion-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_path_devotion.router, prefix=BASE)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def _routine(client, **extra) -> dict:
    payload = {"label": "Istighfar", "adhkar_type": "istighfar", "target_count": 100, **extra}
    response = client.post(f"{BASE}/adhkar/routines", headers=_key(), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


# ---------- adhkar ----------

def test_suggestions_create_nothing(db) -> None:
    client = _client(db, _user(db))
    assert len(client.get(f"{BASE}/adhkar/suggestions").json()) == 7
    assert client.get(f"{BASE}/adhkar/routines").json()["items"] == []


def test_increments_merge_by_key_and_reach_the_target(db) -> None:
    user = _user(db)
    client = _client(db, user)
    routine = _routine(client, target_count=33)
    url = f"{BASE}/adhkar/routines/{routine['id']}/increment"
    key = _key()
    first = client.post(url, headers=key, json={"amount": 30})
    assert first.json()["count"] == 30 and first.json()["target_reached"] is False
    assert client.post(url, headers=key, json={"amount": 30}).json()["count"] == 30  # même clé : rejeu
    assert client.post(url, headers=key, json={"amount": 5}).status_code == 409
    second = client.post(url, headers=_key(), json={"amount": 5}).json()
    assert (second["count"], second["target_reached"], second["period_key"]) == (35, True, adhkar.paris_today().isoformat())
    listed = client.get(f"{BASE}/adhkar/routines").json()["items"][0]
    assert listed["counters"] == [second]
    events = list(db.scalars(select(Event).where(Event.user_id == user.id, Event.event_type == "path.adhkar.incremented")))
    assert [event.payload["target_reached"] for event in events] == [False, True]
    yesterday = (adhkar.paris_today() - timedelta(days=1)).isoformat()
    assert client.post(url, headers=_key(), json={"day": yesterday}).json()["count"] == 1
    tomorrow = (adhkar.paris_today() + timedelta(days=1)).isoformat()
    assert client.post(url, headers=_key(), json={"day": tomorrow}).status_code == 422


def test_per_prayer_and_weekly_periods(db) -> None:
    client = _client(db, _user(db))
    tasbih = _routine(client, label="Subhan Allah", adhkar_type="tasbih", target_count=33, frequency="per_prayer")
    url = f"{BASE}/adhkar/routines/{tasbih['id']}/increment"
    assert client.post(url, headers=_key(), json={}).status_code == 422
    assert client.post(url, headers=_key(), json={"prayer": "asr", "amount": 33}).json()["target_reached"] is True
    counters = client.get(f"{BASE}/adhkar/routines").json()["items"][0]["counters"]
    assert [c["count"] for c in counters] == [0, 0, 33, 0, 0]
    weekly = _routine(client, label="Personnel", adhkar_type="personal", target_count=7, frequency="weekly")
    key = client.post(f"{BASE}/adhkar/routines/{weekly['id']}/increment", headers=_key(), json={}).json()["period_key"]
    monday = adhkar.paris_today() - timedelta(days=adhkar.paris_today().weekday())
    assert key == f"week:{monday.isoformat()}"
    daily = _routine(client)
    assert client.post(f"{BASE}/adhkar/routines/{daily['id']}/increment", headers=_key(), json={"prayer": "isha"}).status_code == 422


def test_low_confidence_voice_needs_validation(db) -> None:
    client = _client(db, _user(db))
    url = f"{BASE}/adhkar/routines/{_routine(client)['id']}/increment"
    assert client.post(url, headers=_key(), json={"amount": 40, "source": "voice", "confidence": 0.6}).status_code == 422
    assert client.post(url, headers=_key(), json={"amount": 40, "source": "voice", "confidence": 0.6, "validated": True}).json()["count"] == 40
    assert client.post(url, headers=_key(), json={"amount": 2, "source": "voice", "confidence": 0.95}).json()["count"] == 42
    assert client.post(url, headers=_key(), json={"amount": 2, "source": "voice"}).status_code == 422


def test_reset_needs_the_displayed_count(db) -> None:
    client = _client(db, _user(db))
    routine = _routine(client)
    client.post(f"{BASE}/adhkar/routines/{routine['id']}/increment", headers=_key(), json={"amount": 12})
    stale = client.post(f"{BASE}/adhkar/routines/{routine['id']}/reset", headers=_key(), json={"expected_count": 10})
    assert (stale.status_code, stale.json()["code"], stale.json()["current"]["count"]) == (409, "ADHKAR_RESET_CONFLICT", 12)
    done = client.post(f"{BASE}/adhkar/routines/{routine['id']}/reset", headers=_key(), json={"expected_count": 12})
    assert (done.status_code, done.json()["count"]) == (200, 0)


def test_routine_limit_versions_pause_and_delete(db) -> None:
    client = _client(db, _user(db))
    routines = [_routine(client, label=f"R{n}") for n in range(8)]
    over = client.post(f"{BASE}/adhkar/routines", headers=_key(), json={"label": "R9", "adhkar_type": "personal", "target_count": 1})
    assert over.status_code == 409
    first = routines[0]
    stale = client.patch(f"{BASE}/adhkar/routines/{first['id']}", headers=_key(), json={"version": 9, "active": False})
    assert (stale.status_code, stale.json()["code"]) == (409, "ADHKAR_VERSION_CONFLICT")
    paused = client.patch(f"{BASE}/adhkar/routines/{first['id']}", headers=_key(), json={"version": 1, "active": False})
    assert (paused.json()["active"], paused.json()["version"]) == (False, 2)
    assert client.post(f"{BASE}/adhkar/routines/{first['id']}/increment", headers=_key(), json={}).status_code == 409
    _routine(client, label="R9")
    again = client.patch(f"{BASE}/adhkar/routines/{first['id']}", headers=_key(), json={"version": 2, "active": True})
    assert again.status_code == 409
    assert client.delete(f"{BASE}/adhkar/routines/{first['id']}").status_code == 204
    assert client.delete(f"{BASE}/adhkar/routines/{first['id']}").status_code == 404


# ---------- Coran ----------

def test_reference_tables_are_consistent() -> None:
    assert len(quran_index.SURAH_START_PAGES) == 114 and len(quran_index.JUZ_START_PAGES) == 30
    assert list(quran_index.SURAH_START_PAGES) == sorted(quran_index.SURAH_START_PAGES)
    assert list(quran_index.JUZ_START_PAGES) == sorted(set(quran_index.JUZ_START_PAGES))
    assert (quran_index.juz_of(1), quran_index.juz_of(21), quran_index.juz_of(22), quran_index.juz_of(604)) == (1, 1, 2, 30)
    assert (quran_index.surah_of(49), quran_index.surah_of(50), quran_index.surahs_on(604)) == (2, 3, [112, 113, 114])


def test_progress_by_page_surah_or_juz_and_regression(db) -> None:
    user = _user(db)
    client = _client(db, user)
    assert client.get(f"{BASE}/quran/continuation").json()["started"] is False
    first = client.post(f"{BASE}/quran/progress", headers=_key(), json={"surah": 3})
    assert first.status_code == 200, first.text
    body = first.json()
    assert (body["location"], body["resume_page"], body["version"]) == (
        {"page": 50, "juz": 3, "surah": 3, "surahs_on_page": [3]}, 51, 1,
    )
    assert client.post(f"{BASE}/quran/progress", headers=_key(), json={"page": 60}).json()["code"] == "QURAN_VERSION_CONFLICT"
    ahead = client.post(f"{BASE}/quran/progress", headers=_key(), json={"juz": 5, "base_version": 1}).json()
    assert ahead["location"]["page"] == 82
    back = client.post(f"{BASE}/quran/progress", headers=_key(), json={"page": 70, "base_version": 2})
    assert (back.status_code, back.json()["code"], back.json()["current"]["location"]["page"]) == (409, "QURAN_REGRESSION", 82)
    confirmed = client.post(f"{BASE}/quran/progress", headers=_key(), json={"page": 70, "base_version": 2, "confirm_regression": True})
    assert confirmed.json()["location"]["page"] == 70
    assert client.post(f"{BASE}/quran/progress", headers=_key(), json={"page": 1, "surah": 2, "base_version": 3}).status_code == 422
    event = list(db.scalars(select(Event).where(Event.user_id == user.id, Event.event_type == "path.quran.progress.updated")))[-1]
    assert (event.payload["regression"], event.payload["previous_page"]) == (True, 82)


def test_khatm_is_confirmed_at_page_604_only(db) -> None:
    client = _client(db, _user(db))
    assert client.post(f"{BASE}/quran/khatm", headers=_key(), json={"confirm": True, "base_version": 1}).status_code == 422
    client.post(f"{BASE}/quran/progress", headers=_key(), json={"page": 604})
    state = client.get(f"{BASE}/quran/continuation").json()
    assert (state["khatm_available"], state["resume_page"]) == (True, 604)
    done = client.post(f"{BASE}/quran/khatm", headers=_key(), json={"confirm": True, "base_version": 1}).json()
    assert (done["khatm_count"], done["location"]["page"]) == (1, 604)


def test_objective_and_plans(db) -> None:
    client = _client(db, _user(db))
    assert client.patch(f"{BASE}/quran/objective", headers=_key(), json={"daily_objective_pages": 4}).status_code == 422
    client.post(f"{BASE}/quran/progress", headers=_key(), json={"page": 100})
    assert client.patch(f"{BASE}/quran/objective", headers=_key(), json={"daily_objective_pages": 4}).json()["daily_objective_pages"] == 4
    daily = client.post(f"{BASE}/quran/plans", headers=_key(), json={"plan_type": "daily_pages", "pages_per_day": 5})
    assert daily.status_code == 201, daily.text
    assert (daily.json()["start_page"], daily.json()["pages_per_day"]) == (101, 5)
    assert client.get(f"{BASE}/quran/continuation").json()["plan"]["page_planned_today"] == 105
    end = (adhkar.paris_today() + timedelta(days=9)).isoformat()
    finish = client.post(f"{BASE}/quran/plans", headers=_key(), json={"plan_type": "finish_in_days", "end_date": end}).json()
    assert finish["pages_per_day"] == 51  # 504 pages restantes / 10 jours, arrondi au-dessus
    assert client.get(f"{BASE}/quran/continuation").json()["plan"]["plan"]["id"] == finish["id"]
    juz = client.post(f"{BASE}/quran/plans", headers=_key(), json={"plan_type": "juz_based", "juz_per_day": 1}).json()
    assert juz["pages_per_day"] == 20
    assert client.post(f"{BASE}/quran/plans", headers=_key(), json={"plan_type": "daily_pages"}).status_code == 422
    stopped = client.post(f"{BASE}/quran/plans/{juz['id']}/stop").json()
    assert stopped["active"] is False
    assert client.get(f"{BASE}/quran/continuation").json()["plan"] is None
