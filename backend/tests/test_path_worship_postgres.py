"""PostgreSQL : prières marquées (PAT-02) et jeûne (PAT-05), et leur effet sur Pulse (doc 41 §7–§8, doc 40 §15.2)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("path worship DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import (  # noqa: E402
    imperium_path_worship,
    imperium_pulse_dashboard,
    imperium_pulse_hydration,
    imperium_pulse_meals,
)
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.path import PathPrayerLog  # noqa: E402
from app.schemas.path_worship import FastBreakRequest, FastEndRequest, PrayerMarkRequest  # noqa: E402
from app.services.path import fasting, prayer_marks  # noqa: E402

PATH = "/api/imperium/path"
PULSE = "/api/imperium/pulse"


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
        {"id": str(user_id), "email": f"path-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_path_worship.router, prefix=PATH)
    for module in (imperium_pulse_hydration, imperium_pulse_meals, imperium_pulse_dashboard):
        app.include_router(module.router, prefix=PULSE)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def _events(db, user, event_type) -> list[Event]:
    return list(db.scalars(select(Event).where(Event.user_id == user.id, Event.event_type == event_type)))


def _today():
    return fasting.paris_today()


# ---------- prières ----------

def test_day_view_lists_five_prayers_without_status(db) -> None:
    client = _client(db, _user(db))
    body = client.get(f"{PATH}/prayers", params={"day": _today().isoformat()}).json()
    assert body["times_source"] == "calculated"
    assert [p["prayer_name"] for p in body["prayers"]] == ["fajr", "dhuhr", "asr", "maghrib", "isha"]
    assert all(p["status"] is None and p["version"] is None for p in body["prayers"])
    adhans = [datetime.fromisoformat(p["adhan_at"]) for p in body["prayers"]]
    assert adhans == sorted(adhans)


def test_mark_accomplished_is_idempotent_and_event_has_no_note(db) -> None:
    user = _user(db)
    client = _client(db, user)
    yesterday = (_today() - timedelta(days=1)).isoformat()
    key = _key()
    payload = {"prayer_date": yesterday, "status": "accomplished", "note": "à la mosquée du quartier"}
    first = client.post(f"{PATH}/prayers/isha/mark", headers=key, json=payload)
    assert first.status_code == 200, first.text
    assert (first.json()["status"], first.json()["version"], first.json()["note"]) == ("accomplished", 1, "à la mosquée du quartier")
    assert first.json()["prayed_at"] is not None
    assert client.post(f"{PATH}/prayers/isha/mark", headers=key, json=payload).json() == first.json()
    assert client.post(f"{PATH}/prayers/isha/mark", headers=key, json={**payload, "note": "autre"}).status_code == 409
    events = _events(db, user, "path.prayer.logged")
    assert len(events) == 1
    assert events[0].payload["status"] == "accomplished" and "note" not in events[0].payload
    assert events[0].privacy_level == "high"
    day = client.get(f"{PATH}/prayers", params={"day": yesterday}).json()
    assert [p["status"] for p in day["prayers"]] == [None, None, None, None, "accomplished"]


def test_same_status_again_dedupes_without_new_event(db) -> None:
    user = _user(db)
    client = _client(db, user)
    payload = {"prayer_date": (_today() - timedelta(days=1)).isoformat(), "status": "accomplished"}
    client.post(f"{PATH}/prayers/fajr/mark", headers=_key(), json=payload)
    again = client.post(f"{PATH}/prayers/fajr/mark", headers=_key(), json=payload)
    assert (again.status_code, again.json()["version"]) == (200, 1)
    assert len(_events(db, user, "path.prayer.logged")) == 1


def test_changing_a_status_needs_the_read_version(db) -> None:
    user = _user(db)
    client = _client(db, user)
    day = (_today() - timedelta(days=2)).isoformat()
    client.post(f"{PATH}/prayers/asr/mark", headers=_key(), json={"prayer_date": day, "status": "accomplished"})
    stale = client.post(f"{PATH}/prayers/asr/mark", headers=_key(), json={"prayer_date": day, "status": "not_marked_as_accomplished"})
    assert stale.status_code == 409
    assert stale.json()["code"] == "PRAYER_STATUS_CONFLICT"
    assert (stale.json()["current"]["status"], stale.json()["current"]["version"]) == ("accomplished", 1)
    changed = client.post(
        f"{PATH}/prayers/asr/mark", headers=_key(),
        json={"prayer_date": day, "status": "not_marked_as_accomplished", "base_version": 1},
    )
    assert changed.status_code == 200, changed.text
    assert (changed.json()["status"], changed.json()["version"], changed.json()["prayed_at"]) == ("not_marked_as_accomplished", 2, None)
    event = _events(db, user, "path.prayer.not_marked")[0]
    assert (event.payload["previous_status"], event.payload["status"]) == ("accomplished", "not_marked_as_accomplished")


def test_clear_status_deletes_the_line(db) -> None:
    user = _user(db)
    client = _client(db, user)
    day = (_today() - timedelta(days=1)).isoformat()
    client.post(f"{PATH}/prayers/dhuhr/mark", headers=_key(), json={"prayer_date": day, "status": "accomplished"})
    assert client.post(f"{PATH}/prayers/dhuhr/clear", headers=_key(), json={"prayer_date": day, "base_version": 9}).status_code == 409
    cleared = client.post(f"{PATH}/prayers/dhuhr/clear", headers=_key(), json={"prayer_date": day, "base_version": 1})
    assert cleared.status_code == 200, cleared.text
    assert (cleared.json()["status"], cleared.json()["log_id"]) == (None, None)
    assert db.scalar(select(PathPrayerLog).where(PathPrayerLog.user_id == user.id)) is None
    assert _events(db, user, "path.prayer.cleared")[0].payload["previous_status"] == "accomplished"
    assert client.post(f"{PATH}/prayers/dhuhr/clear", headers=_key(), json={"prayer_date": day, "base_version": 1}).status_code == 404


def test_future_prayer_cannot_be_marked_not_accomplished(db) -> None:
    user = _user(db)
    client = _client(db, user)
    tomorrow = (_today() + timedelta(days=1)).isoformat()
    refused = client.post(f"{PATH}/prayers/fajr/mark", headers=_key(), json={"prayer_date": tomorrow, "status": "accomplished"})
    assert refused.status_code == 422
    early = datetime.combine(_today(), datetime.min.time(), tzinfo=fasting.PARIS) + timedelta(hours=1)
    with pytest.raises(prayer_marks.PrayerInputError, match="pas encore arrivée"):
        prayer_marks.mark_prayer(
            db, current_user=user, prayer_name="isha",
            payload=PrayerMarkRequest(prayer_date=_today(), status="not_marked_as_accomplished"),
            idempotency_key=uuid4().hex, request_path="/test", now=early,
        )
    db.rollback()
    with_time = client.post(
        f"{PATH}/prayers/fajr/mark", headers=_key(),
        json={"prayer_date": (_today() - timedelta(days=1)).isoformat(), "status": "not_marked_as_accomplished",
              "prayed_at": datetime.now(UTC).isoformat()},
    )
    assert with_time.status_code == 422


def test_unknown_prayer_is_rejected(db) -> None:
    client = _client(db, _user(db))
    assert client.post(f"{PATH}/prayers/witr/mark", headers=_key(), json={"prayer_date": _today().isoformat(), "status": "accomplished"}).status_code == 422


# ---------- jeûne ----------

def _start(client, **extra):
    return client.post(f"{PATH}/fasts", headers=_key(), json={"fasting_type": "monday_thursday", **extra})


def test_start_fast_freezes_the_window_and_refuses_a_second_one(db) -> None:
    user = _user(db)
    client = _client(db, user)
    key = _key()
    started = client.post(f"{PATH}/fasts", headers=key, json={"fasting_type": "temporary"})
    assert started.status_code == 201, started.text
    fast = started.json()
    prayers = {p["prayer_name"]: datetime.fromisoformat(p["adhan_at"]) for p in client.get(f"{PATH}/prayers").json()["prayers"]}
    assert datetime.fromisoformat(fast["suhoor_at"]) == prayers["fajr"] - timedelta(minutes=30)
    assert datetime.fromisoformat(fast["iftar_at"]) == prayers["maghrib"]
    assert (fast["status"], fast["fasting_date"], fast["times_source"]) == ("active", _today().isoformat(), "calculated")
    assert client.post(f"{PATH}/fasts", headers=key, json={"fasting_type": "temporary"}).status_code == 200
    second = _start(client)
    assert second.status_code == 409
    assert (second.json()["code"], second.json()["current"]["id"]) == ("FAST_STATE_CONFLICT", fast["id"])
    started_event = _events(db, user, "path.fasting.started")[0]
    assert started_event.payload["hydration_limits"] == {"daytime": False}
    assert client.get(f"{PATH}/fasts").json()["items"][0]["id"] == fast["id"]


def test_fast_starts_only_the_same_day(db) -> None:
    client = _client(db, _user(db))
    assert _start(client, fasting_date=(_today() + timedelta(days=1)).isoformat()).status_code == 422
    assert _start(client, fasting_date=(_today() - timedelta(days=1)).isoformat()).status_code == 422


def test_state_inside_and_after_the_window(db) -> None:
    user = _user(db)
    client = _client(db, user)
    fast = _start(client).json()
    iftar = datetime.fromisoformat(fast["iftar_at"])
    inside = fasting.state(db, current_user=user, at=iftar - timedelta(hours=1))
    assert (inside.fasting_active, inside.hydration_limits) == (True, {"daytime": False})
    assert inside.message.startswith("Jeûne en cours — iftar à ")
    after = fasting.state(db, current_user=user, at=iftar + timedelta(minutes=5))
    assert (after.fasting_active, after.hydration_limits["daytime"]) == (False, True)
    assert after.message == "L'iftar est passé : confirme la fin du jeûne."
    assert client.get(f"{PATH}/fasting/state").json()["fast"]["id"] == fast["id"]


def test_end_only_after_iftar_and_once(db) -> None:
    user = _user(db)
    client = _client(db, user)
    fast = _start(client).json()
    iftar = datetime.fromisoformat(fast["iftar_at"])
    with pytest.raises(fasting.FastInputError, match="romps le jeûne"):
        fasting.end_fast(db, current_user=user, fast_id=fast["id"], payload=FastEndRequest(ended_at=iftar - timedelta(minutes=10)),
                         idempotency_key=uuid4().hex, request_path="/t", now=iftar)
    db.rollback()
    ended, _ = fasting.end_fast(db, current_user=user, fast_id=fast["id"], payload=FastEndRequest(),
                                idempotency_key=uuid4().hex, request_path="/t", now=iftar + timedelta(minutes=3))
    assert (ended.status, ended.version) == ("ended", 2)
    assert _events(db, user, "path.fasting.ended")[0].payload["fast_id"] == fast["id"]
    assert client.post(f"{PATH}/fasts/{fast['id']}/end", headers=_key(), json={}).json()["code"] == "FAST_STATE_CONFLICT"
    assert _start(client).status_code == 409  # un jeûne par jour


def test_break_needs_confirmation_and_keeps_the_reason_out_of_events(db) -> None:
    user = _user(db)
    client = _client(db, user)
    fast = _start(client).json()
    assert client.post(f"{PATH}/fasts/{fast['id']}/break", headers=_key(), json={"confirm": False}).status_code == 422
    suhoor = datetime.fromisoformat(fast["suhoor_at"])
    broken_at = suhoor + timedelta(hours=3)
    broken, _ = fasting.break_fast(
        db, current_user=user, fast_id=fast["id"], payload=FastBreakRequest(confirm=True, broken_at=broken_at, reason="malaise"),
        idempotency_key=uuid4().hex, request_path="/t", now=broken_at + timedelta(minutes=1),
    )
    assert (broken.status, broken.break_reason) == ("broken", "malaise")
    event = _events(db, user, "path.fasting.broken")[0]
    assert event.payload["replan_prompt"] is True and "malaise" not in str(event.payload)
    assert client.post(f"{PATH}/fasts/{uuid4()}/break", headers=_key(), json={"confirm": True}).status_code == 404
    # La rupture ferme la fenêtre : l'eau bue après est acceptée, avant elle reste bloquée.
    before = client.post(f"{PULSE}/hydration-logs", headers=_key(),
                         json={"amount_ml": 250, "logged_at": (broken_at - timedelta(hours=1)).isoformat(), "decrement_stock": False})
    after = client.post(f"{PULSE}/hydration-logs", headers=_key(),
                        json={"amount_ml": 250, "logged_at": (broken_at + timedelta(minutes=30)).isoformat(), "decrement_stock": False})
    assert (before.status_code, after.status_code) == (409, 201)


# ---------- effet sur Pulse ----------

def test_hydration_is_blocked_inside_the_window_only(db) -> None:
    user = _user(db)
    client = _client(db, user)
    fast = _start(client).json()
    iftar = datetime.fromisoformat(fast["iftar_at"])
    blocked = client.post(f"{PULSE}/hydration-logs", headers=_key(),
                          json={"amount_ml": 500, "logged_at": (iftar - timedelta(hours=2)).isoformat()})
    assert blocked.status_code == 409
    assert blocked.json() == {"detail": "Jeûne en cours - hydratation hors fenêtre désactivée.", "code": "FASTING_HYDRATION_BLOCKED"}
    allowed = client.post(f"{PULSE}/hydration-logs", headers=_key(),
                          json={"amount_ml": 500, "logged_at": (iftar + timedelta(minutes=10)).isoformat(), "decrement_stock": False})
    assert allowed.status_code == 201, allowed.text


def test_daytime_water_allowed_when_chosen_at_start(db) -> None:
    user = _user(db)
    client = _client(db, user)
    fast = _start(client, hydration_daytime_allowed=True).json()
    iftar = datetime.fromisoformat(fast["iftar_at"])
    logged = client.post(f"{PULSE}/hydration-logs", headers=_key(),
                         json={"amount_ml": 300, "logged_at": (iftar - timedelta(hours=2)).isoformat(), "decrement_stock": False})
    assert logged.status_code == 201, logged.text
    assert fasting.state(db, current_user=user, at=iftar - timedelta(hours=2)).hydration_limits == {"daytime": True}


def test_meal_during_the_window_is_kept_with_a_warning_and_dashboard_banner(db) -> None:
    user = _user(db)
    client = _client(db, user)
    fast = _start(client).json()
    iftar = datetime.fromisoformat(fast["iftar_at"])
    draft = client.post(f"{PULSE}/meals/drafts", headers=_key(),
                        json={"description": "une pomme", "eaten_at": (iftar - timedelta(hours=1)).isoformat()})
    assert draft.status_code == 201, draft.text
    assert draft.json()["warnings"][0] == "Repas noté pendant les heures de jeûne."
    later = client.post(f"{PULSE}/meals/drafts", headers=_key(),
                        json={"description": "une soupe", "eaten_at": (iftar + timedelta(minutes=20)).isoformat()})
    assert "Repas noté pendant les heures de jeûne." not in later.json()["warnings"]
    banners = [b for b in client.get(f"{PULSE}/dashboard").json()["banners"] if b["kind"] == "fasting"]
    assert len(banners) == 1
    assert banners[0]["message"] in (f"Jeûne en cours — iftar à {fasting._hhmm(iftar)}.", "L'iftar est passé : confirme la fin du jeûne.")
