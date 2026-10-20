"""PostgreSQL : signaux Pulse hors montre, signalements subjectifs et board (spec Pulse §3.1, §4, §14 ;
ACT-PLS-08, ACT-PLS-05)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("pulse signals DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_pulse_health, imperium_pulse_signals  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.imperium import ImperiumMission, PulseMeal, PulseWorkout  # noqa: E402
from app.models.toolbox import SignalValue  # noqa: E402
from app.services.params import set_parameter  # noqa: E402
from app.services.pulse import signals  # noqa: E402
from app.services.runner.engine import RunContext, Window  # noqa: E402

P = "/api/imperium/pulse"
NOW = datetime.now(UTC).replace(microsecond=0)
CODES = ("pulse.pain_active", "pulse.fatigue_reported", "pulse.mood_reported", "pulse.stress_reported",
         "pulse.last_meal_hours", "pulse.training_adherence_7d", "pulse.workload_today_h")


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    # Les routes committent : transaction externe annulée, rien ne fuit (signaux réactivés compris).
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
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"psig-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _turn_on(db, *codes: str, **flags) -> None:
    db.execute(text("UPDATE signal_definitions SET active = true WHERE code = ANY(:codes)"),
               {"codes": list(codes or CODES)})
    for code, value in flags.items():
        set_parameter(db, code=f"pulse.{code}", value=value, origin="user", rationale_fr="Test.")
    db.commit()


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_pulse_signals.router, prefix=P)
    app.include_router(imperium_pulse_health.router, prefix=P)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _report(client, kind: str, level: int, **extra):
    return client.post(f"{P}/reports", json={"kind": kind, "level": level, **extra},
                       headers={"Idempotency-Key": str(uuid4())})


def _values(db, user, code: str) -> list[SignalValue]:
    return list(db.scalars(select(SignalValue).where(SignalValue.signal_code == code,
                                                     SignalValue.detail["user_id"].astext == str(user.id))
                           .order_by(SignalValue.measured_at)))


def _board(client) -> dict:
    response = client.get(f"{P}/board")
    assert response.status_code == 200, response.text
    return {signal["code"]: signal for signal in response.json()["signals"]}


def test_band_rules() -> None:
    high = {"kind": "high", "yellow": 3, "orange": 4, "red": 5}
    assert [signals.band_for(v, high) for v in (1, 3, 4, 5)] == ["green", "yellow", "orange", "red"]
    assert signals.band_for(20, {"kind": "high", "orange": 18}) == "orange"
    assert signals.band_for(17.9, {"kind": "high", "orange": 18}) == "green"
    low = {"kind": "low", "green": 0.8, "yellow": 0.6, "floor": "orange"}
    assert [signals.band_for(v, low) for v in (0.8, 0.7, 0.2)] == ["green", "yellow", "orange"]
    assert signals.band_for(3, {"kind": "info"}) is None


def test_seeded_off(db) -> None:
    rows = db.execute(text("SELECT code, active, domain FROM signal_definitions WHERE code LIKE 'pulse.%' "
                           "ORDER BY code")).all()
    assert [row.code for row in rows] == sorted(CODES) and not any(row.active for row in rows)
    job = db.execute(text("SELECT enabled, schedule FROM job_definitions WHERE code = 'pulse.signals_refresh'")).one()
    assert tuple(job) == (False, "*/15 * * * *")
    user = _user(db)
    client = _client(db, user)
    assert client.get(f"{P}/board").json()["code"] == "PULSE_BOARD_DISABLED"
    assert _report(client, "fatigue", 4).json()["code"] == "PULSE_REPORTS_DISABLED"
    assert signals.refresh(db, current_user=user).computed == 0  # signaux inactifs : rien n'est calculé


def test_report_is_on_the_board_at_once_and_replays(db) -> None:
    _turn_on(db, board_enabled=True, reports_enabled=True)
    user = _user(db)
    client = _client(db, user)
    assert _board(client)["pulse.fatigue_reported"]["state"] == "no_data"
    key = {"Idempotency-Key": "same"}
    first = client.post(f"{P}/reports", json={"kind": "fatigue", "level": 4}, headers=key)
    assert first.status_code == 201, first.text
    assert client.post(f"{P}/reports", json={"kind": "fatigue", "level": 4}, headers=key).status_code == 200
    assert client.post(f"{P}/reports", json={"kind": "fatigue", "level": 2}, headers=key).status_code == 409
    assert _report(client, "mood", 9).status_code == 422
    assert _report(client, "pain", 3).status_code == 422  # la douleur passe par pain-logs
    future = (NOW + timedelta(hours=2)).isoformat()
    assert _report(client, "stress", 2, reported_at=future).status_code == 422
    fatigue = _board(client)["pulse.fatigue_reported"]
    assert (fatigue["state"], fatigue["value"], fatigue["band"], fatigue["flag"]) == ("fresh", 4, "orange", True)
    assert fatigue["detail"] == {"report_id": first.json()["id"]} and "user_id" not in fatigue["detail"]
    event = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "pulse.report.logged"))
    assert event.payload == {"report_id": first.json()["id"], "kind": "fatigue"} and event.privacy_level == "high"
    _report(client, "fatigue", 1)
    assert _board(client)["pulse.fatigue_reported"]["band"] == "green"
    assert len(client.get(f"{P}/reports").json()["items"]) == 2


def test_pain_signal_follows_writes_and_real_deletion(db) -> None:
    _turn_on(db, board_enabled=True)
    user = _user(db)
    client = _client(db, user)
    version = next(c for c in client.get(f"{P}/consents").json()["items"] if c["domain"] == "pain")["text_version"]
    client.post(f"{P}/consents/pain", json={"text_version": version})
    log = client.post(f"{P}/pain-logs", json={"body_zone": "knee", "severity": 6},
                      headers={"Idempotency-Key": str(uuid4())}).json()
    pain = _board(client)["pulse.pain_active"]
    assert (pain["value"], pain["band"]) == (6, "orange") and pain["detail"]["pain_log_ids"] == [log["id"]]
    client.post(f"{P}/pain-logs/{log['id']}/resolve")
    assert (_board(client)["pulse.pain_active"]["value"], _board(client)["pulse.pain_active"]["band"]) == (0, "green")
    assert client.delete(f"{P}/pain-logs/{log['id']}").status_code == 204
    assert all(log["id"] not in (row.detail.get("pain_log_ids") or []) for row in _values(db, user, "pulse.pain_active"))


def test_unchanged_refresh_only_touches_the_timestamp_and_staleness_shows(db) -> None:
    _turn_on(db, "pulse.workload_today_h", board_enabled=True)
    user = _user(db)
    at = datetime(2026, 10, 21, 8, 0, tzinfo=UTC)  # heure fixe : pas de bascule de jour pendant le test
    db.add(ImperiumMission(user_id=user.id, title="Dossier", domain="finance", status="backlog", started_at=at,
                           planned_start_at=at, estimated_minutes=90))
    db.commit()
    assert signals.refresh(db, current_user=user, now=at).written == 1
    stale = {s.code: s for s in signals.board(db, current_user=user, now=at + timedelta(hours=3)).signals}
    workload = stale["pulse.workload_today_h"]
    assert (workload.state, workload.flag, workload.band, workload.age_min) == ("stale", False, None, 180)
    stats = signals.refresh(db, current_user=user, now=at + timedelta(minutes=1))
    db.commit()
    assert (stats.written, stats.unchanged) == (0, 1)
    rows = _values(db, user, "pulse.workload_today_h")
    assert len(rows) == 1 and rows[0].measured_at == at + timedelta(minutes=1) and float(rows[0].value) == 1.5
    fresh = {s.code: s for s in signals.board(db, current_user=user, now=at + timedelta(minutes=30)).signals}
    assert fresh["pulse.workload_today_h"].state == "fresh"


def test_meal_and_training_signals(db, monkeypatch) -> None:
    _turn_on(db, "pulse.last_meal_hours", "pulse.training_adherence_7d")
    user = _user(db)
    db.add(PulseMeal(user_id=user.id, status="confirmed", label="Dîner", description="Riz", source="manual",
                     eaten_at=NOW - timedelta(hours=20), idempotency_key=str(uuid4()), request_hash="h"))
    for status, days in (("completed", 1), ("completed", 2), ("skipped", 3), ("planned", 4), ("planned", 9)):
        db.add(PulseWorkout(user_id=user.id, title="Séance", status=status, planned_at=NOW - timedelta(days=days),
                            idempotency_key=str(uuid4()), request_hash="h"))
    db.commit()
    signals.refresh(db, current_user=user, now=NOW)
    meal = _values(db, user, "pulse.last_meal_hours")[-1]
    assert (float(meal.value), meal.band, meal.detail["fasting"]) == (20.0, "orange", False)
    training = _values(db, user, "pulse.training_adherence_7d")[-1]
    assert (float(training.value), training.band) == (0.5, "orange")
    assert (training.detail["completed"], training.detail["planned"]) == (2, 4)
    monkeypatch.setattr(signals.fasting, "window_fast", lambda db, user, at: object())
    signals.refresh(db, current_user=user, now=NOW + timedelta(minutes=1))
    assert _values(db, user, "pulse.last_meal_hours")[-1].band == "green"  # jeûne : délai attendu


def test_deleting_reports_removes_their_signal_values(db) -> None:
    _turn_on(db, board_enabled=True, reports_enabled=True)
    user = _user(db)
    client = _client(db, user)
    report = _report(client, "stress", 5).json()
    assert len(_values(db, user, "pulse.stress_reported")) == 1
    assert client.delete(f"{P}/reports/{report['id']}").status_code == 204
    assert _values(db, user, "pulse.stress_reported") == []
    _report(client, "mood", 3)
    assert client.delete(f"{P}/reports").json() == {"deleted": 1}
    assert _values(db, user, "pulse.mood_reported") == []
    assert client.delete(f"{P}/reports/{uuid4()}").status_code == 404


def test_refresh_job(db, monkeypatch) -> None:
    _turn_on(db, "pulse.workload_today_h")
    user = _user(db)
    monkeypatch.setattr("app.services.wr.metrics._job_user", lambda db: user)
    job = db.execute(text("SELECT * FROM job_definitions WHERE code = 'pulse.signals_refresh'")).one()
    ctx = RunContext(db=db, job=job, run_id=uuid4(), trigger="cron", trigger_ref=None)
    signals.refresh_job(ctx, Window(from_ts=NOW - timedelta(minutes=15), to_ts=NOW))
    assert ctx.detail["computed"] == 1 and ctx.items_out == 1
