"""PostgreSQL : réglages Path du calcul local des horaires (PAT-11, doc 41 §6.4)."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("path settings DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_path_mosques, imperium_path_settings  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.services.path.prayer import prayer_times  # noqa: E402

BASE = "/api/imperium/path"
DAY = date(2026, 7, 15)
MARSEILLE = {"name": "Marseille", "latitude": "43.296500", "longitude": "5.369800"}


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
        {"id": str(user_id), "email": f"psettings-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_path_settings.router, prefix=BASE)
    app.include_router(imperium_path_mosques.router, prefix=BASE)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def test_defaults_before_any_setting(db) -> None:
    body = _client(db, _user(db)).get(f"{BASE}/settings").json()
    assert (body["calculation_method"], body["madhhab"], body["city"], body["version"]) == ("MuslimWorldLeague", "Maliki", None, 0)
    assert (body["location_source"], body["times_source"], body["updated_at"]) == ("default", "calculated", None)
    assert body["supported_methods"] == ["MuslimWorldLeague", "Karachi", "Egypt", "ISNA"]


def test_madhhab_and_method_change_the_times_of_this_user_only(db) -> None:
    user, other = _user(db), _user(db)
    client = _client(db, user)
    before, _ = prayer_times(db, DAY, user_id=user.id)
    key = _key()
    saved = client.patch(f"{BASE}/settings", headers=key, json={"version": 0, "madhhab": "Hanafi", "calculation_method": "ISNA"})
    assert saved.status_code == 200, saved.text
    assert (saved.json()["madhhab"], saved.json()["calculation_method"], saved.json()["version"]) == ("Hanafi", "ISNA", 1)
    after, _ = prayer_times(db, DAY, user_id=user.id)
    assert after["asr"] > before["asr"]  # ombre ×2
    assert after["fajr"] > before["fajr"]  # 15° au lieu de 18°
    assert after["dhuhr"] == before["dhuhr"]
    assert prayer_times(db, DAY, user_id=other.id)[0] == before
    assert client.patch(f"{BASE}/settings", headers=key, json={"version": 0, "madhhab": "Hanafi", "calculation_method": "ISNA"}).json() == saved.json()
    event = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "path.settings.updated"))
    assert (sorted(event.payload["changed"]), event.payload["has_city"]) == (["calculation_method", "madhhab"], False)


def test_city_moves_the_calculation_and_a_mosque_wins(db) -> None:
    user = _user(db)
    client = _client(db, user)
    paris, _ = prayer_times(db, DAY, user_id=user.id)
    body = client.patch(f"{BASE}/settings", headers=_key(), json={"version": 0, "city": MARSEILLE}).json()
    assert (body["city"]["name"], body["location_source"], body["madhhab"]) == ("Marseille", "city", "Maliki")
    marseille, _ = prayer_times(db, DAY, user_id=user.id)
    assert marseille["dhuhr"] < paris["dhuhr"]  # plus à l'est, même fuseau : midi solaire plus tôt
    client.post(f"{BASE}/mosques", headers=_key(), json={"name": "Mosquée", "latitude": "48.856600", "longitude": "2.352200",
                                                          "is_default": True})
    assert client.get(f"{BASE}/settings").json()["location_source"] == "mosque"
    assert prayer_times(db, DAY, user_id=user.id)[0] == paris
    back = client.patch(f"{BASE}/settings", headers=_key(), json={"version": 1, "city": None}).json()
    assert (back["city"], back["version"]) == (None, 2)


def test_version_and_input_checks(db) -> None:
    user = _user(db)
    client = _client(db, user)
    assert client.patch(f"{BASE}/settings", json={"version": 0}).status_code == 400
    unchanged = client.patch(f"{BASE}/settings", headers=_key(), json={"version": 0, "madhhab": "Maliki"}).json()
    assert unchanged["version"] == 0  # rien n'a changé : aucune ligne créée
    client.patch(f"{BASE}/settings", headers=_key(), json={"version": 0, "madhhab": "Shafii"})
    stale = client.patch(f"{BASE}/settings", headers=_key(), json={"version": 0, "madhhab": "Hanbali"})
    assert (stale.status_code, stale.json()["code"], stale.json()["current"]["madhhab"]) == (409, "PATH_SETTINGS_VERSION_CONFLICT", "Shafii")
    assert client.patch(f"{BASE}/settings", headers=_key(), json={"version": 1, "calculation_method": "Jafari"}).status_code == 422
    assert client.patch(f"{BASE}/settings", headers=_key(),
                        json={"version": 1, "city": {"name": "X", "latitude": "91", "longitude": "0"}}).status_code == 422
    assert client.patch(f"{BASE}/settings", headers=_key(), json={"version": 1, "city": {"name": "Lyon"}}).status_code == 422
