"""PostgreSQL : règles rouges RF1-RF5, vue v_pulse_active_blocks et porte Daily G5 (spec Pulse §11 ;
ACT-PLS-09, ACT-DLY-05)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("pulse red flags DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_pulse_health  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.imperium import ImperiumMission, ImperiumMissionScore  # noqa: E402
from app.models.pulse import PulseRedFlagEvent  # noqa: E402
from app.models.toolbox import Notification  # noqa: E402
from app.services.daily import selection  # noqa: E402
from app.services.params import set_parameter  # noqa: E402
from app.services.pulse import dashboard  # noqa: E402

P = "/api/imperium/pulse"
NOW = datetime.now(UTC)
RULES = ("RF_lab_out_of_range", "RF_rhr_sustained", "RF_severe_pain", "RF_symptom_keywords", "RF_weight_drop")


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    # Les routes committent : transaction externe annulée, rien ne fuit (règles réactivées comprises).
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
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"prf-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _activate_rules(db) -> None:
    db.execute(text("UPDATE pulse_red_flag_rules SET active = true WHERE code = ANY(:codes)"), {"codes": list(RULES)})
    db.commit()


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_pulse_health.router, prefix=P)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    for domain in ("pain", "body"):
        version = next(c for c in client.get(f"{P}/consents").json()["items"] if c["domain"] == domain)["text_version"]
        assert client.post(f"{P}/consents/{domain}", json={"text_version": version}).status_code == 200
    return client


def _pain(client, **fields) -> dict:
    response = client.post(f"{P}/pain-logs", json={"body_zone": "knee", **fields}, headers={"Idempotency-Key": str(uuid4())})
    assert response.status_code == 201, response.text
    return response.json()


def _weigh(client, kg: str, days_ago: float) -> None:
    response = client.post(f"{P}/body-snapshots", json={"measured_at": (NOW - timedelta(days=days_ago)).isoformat(),
                                                         "weight_kg": kg}, headers={"Idempotency-Key": str(uuid4())})
    assert response.status_code == 201, response.text


def _blocks(db, user) -> list:
    return db.execute(text("SELECT block_kind, min_physical_load, source_ref FROM v_pulse_active_blocks "
                           "WHERE user_id = :u"), {"u": user.id}).all()


def test_seeded_inactive_so_nothing_is_raised(db) -> None:
    rows = db.execute(text("SELECT code, active, severity, action FROM pulse_red_flag_rules ORDER BY code")).all()
    assert [row.code for row in rows] == sorted(RULES) and not any(row.active for row in rows)
    assert {row.code for row in rows if row.action == "advise_doctor_and_pause_training"} == {
        "RF_severe_pain", "RF_symptom_keywords"}
    assert selection.g5_enabled(db) is False
    user = _user(db)
    client = _client(db, user)
    _pain(client, severity=9)
    assert client.get(f"{P}/red-flags").json()["items"] == [] and _blocks(db, user) == []


def test_severe_pain_raises_once_notifies_verbatim_and_blocks_training(db) -> None:
    _activate_rules(db)
    user = _user(db)
    client = _client(db, user)
    _pain(client, severity=5)
    assert client.get(f"{P}/red-flags").json()["items"] == []
    log = _pain(client, severity=8, limitation_notes="Genou bloqué")
    _pain(client, severity=2)  # nouvelle écriture : pas de doublon pour la même douleur
    items = client.get(f"{P}/red-flags").json()["items"]
    assert len(items) == 1
    flag = items[0]
    assert flag["rule_code"] == "RF_severe_pain" and flag["severity"] == "urgent" and flag["blocks_training"] is True
    assert flag["evidence"] == {"pain_log_id": log["id"], "severity": 8, "body_zone": "knee", "rule_version": 1}
    message = db.execute(text("SELECT message_fr FROM pulse_red_flag_rules WHERE code = 'RF_severe_pain'")).scalar()
    assert flag["message_fr"] == message
    notification = db.scalar(select(Notification).where(Notification.ref_id == flag["id"]))
    assert notification.severity == "red" and notification.message_fr == message
    event = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "pulse.red_flag.raised"))
    assert event.payload == {"red_flag_id": flag["id"], "rule_code": "RF_severe_pain", "severity": "urgent",
                             "action": "advise_doctor_and_pause_training"}
    assert "Genou" not in str(event.payload) and event.privacy_level == "high"
    assert [(row.block_kind, row.min_physical_load, str(row.source_ref)) for row in _blocks(db, user)] == [
        ("pause_training", 4, flag["id"])]
    banners = dashboard.build_dashboard(db, current_user=user, day=NOW.date()).banners
    assert (banners[0].kind, banners[0].level, banners[0].message) == ("red_flag", "error", message)


def test_symptom_keywords_match_without_accents_and_keep_no_free_text(db) -> None:
    _activate_rules(db)
    user = _user(db)
    client = _client(db, user)
    log = _pain(client, body_zone="chest", severity=3, limitation_notes="Douleur THORACIQUE en montant l'escalier")
    flags = client.get(f"{P}/red-flags").json()["items"]
    assert [f["rule_code"] for f in flags] == ["RF_symptom_keywords"]
    assert flags[0]["evidence"] == {"pain_log_id": log["id"], "keywords": ["douleur thoracique"], "rule_version": 1}
    _pain(client, severity=1, pain_type="malaise")
    assert len(client.get(f"{P}/red-flags").json()["items"]) == 2


def test_weight_drop_advises_without_blocking_and_keeps_one_open_flag(db) -> None:
    _activate_rules(db)
    user = _user(db)
    client = _client(db, user)
    _weigh(client, "80.00", days_ago=20)
    _weigh(client, "79.80", days_ago=10)
    assert client.get(f"{P}/red-flags").json()["items"] == []  # -0.25 % sur 10 j : rien
    _weigh(client, "78.00", days_ago=0)
    _weigh(client, "77.50", days_ago=0)
    flags = client.get(f"{P}/red-flags").json()["items"]
    assert len(flags) == 1 and flags[0]["rule_code"] == "RF_weight_drop" and flags[0]["blocks_training"] is False
    assert flags[0]["evidence"]["first_kg"] == 80.0 and flags[0]["evidence"]["pct_per_month"] < -1.5
    assert db.scalar(select(Notification.severity).where(Notification.ref_id == flags[0]["id"])) == "normal"
    assert _blocks(db, user) == []


def test_unavailable_sources_never_raise(db) -> None:
    _activate_rules(db)
    user = _user(db)
    client = _client(db, user)
    _pain(client, severity=1)
    codes = db.scalars(select(PulseRedFlagEvent.rule_id).where(PulseRedFlagEvent.user_id == user.id)).all()
    assert codes == []
    paths = [route.path for route in imperium_pulse_health.router.routes]
    assert not any("rule" in path and "red" in path for path in paths)  # aucune route ne touche aux règles


def test_acknowledge_keeps_the_block_and_only_resolution_lifts_it(db) -> None:
    _activate_rules(db)
    user = _user(db)
    client = _client(db, user)
    _pain(client, severity=10)
    flag_id = client.get(f"{P}/red-flags").json()["items"][0]["id"]
    acked = client.post(f"{P}/red-flags/{flag_id}/acknowledge")
    assert acked.status_code == 200 and acked.json()["acknowledged_at"] is not None
    assert len(_blocks(db, user)) == 1
    no_reason = client.post(f"{P}/red-flags/{flag_id}/resolve", json={"resolution": "dismissed_with_reason"})
    assert no_reason.status_code == 409
    resolved = client.post(f"{P}/red-flags/{flag_id}/resolve", json={"resolution": "doctor_consulted"})
    assert resolved.status_code == 200 and resolved.json()["blocks_training"] is False
    assert client.post(f"{P}/red-flags/{flag_id}/resolve", json={"resolution": "resolved"}).status_code == 409
    assert _blocks(db, user) == []
    _pain(client, severity=1)  # même douleur toujours ouverte : pas de nouvelle levée
    assert client.get(f"{P}/red-flags").json()["items"] == []
    assert len(client.get(f"{P}/red-flags", params={"include_resolved": True}).json()["items"]) == 1
    assert client.post(f"{P}/red-flags/{uuid4()}/acknowledge").status_code == 404
    stranger = _client(db, _user(db))
    assert stranger.post(f"{P}/red-flags/{flag_id}/acknowledge").status_code == 404


def _mission(db, user, title: str, *, load: int | None, score: float):
    mission = ImperiumMission(user_id=user.id, title=title, domain="finance", status="backlog", started_at=NOW,
                              planned_start_at=NOW, estimated_minutes=20, physical_load=load)
    db.add(mission)
    db.flush()
    db.add(ImperiumMissionScore(user_id=user.id, mission_id=mission.id, domain="finance", intrinsic_score=score / 10,
                                domain_coefficient=10, weighted_score=score, explanation={},
                                source="decision_framework_v1"))
    db.commit()
    return mission


def test_g5_rejects_heavy_missions_with_the_gate_in_the_log(db) -> None:
    _activate_rules(db)
    user = _user(db)
    client = _client(db, user)
    heavy = _mission(db, user, "Séance lourde", load=5, score=90)
    light = _mission(db, user, "Lecture", load=1, score=40)
    _pain(client, severity=9)
    flag_id = client.get(f"{P}/red-flags").json()["items"][0]["id"]
    now = NOW + timedelta(minutes=1)

    stub = selection.compute(db, current_user=user, now=now, origin=None)
    assert stub.chosen.mission.id == heavy.id and {c.notes["g5"] for c in stub.candidates} == {"stub"}

    set_parameter(db, code="daily.g5_enabled", value=True, origin="user", rationale_fr="Test.")
    db.commit()
    log = selection.select_next(db, current_user=user, trigger="manual", now=now)
    entries = {entry["mission_id"]: entry for entry in log.feasible_set}
    assert log.chosen_mission_id == light.id
    assert entries[str(heavy.id)]["blocked_by"] == "G5" and entries[str(heavy.id)]["g5"] == "blocked"
    assert entries[str(heavy.id)]["g5_blocks"] == [flag_id]
    assert entries[str(heavy.id)]["gates_passed"] == ["G1", "G2", "G3", "G4"]
    assert entries[str(light.id)]["blocked_by"] is None
    db.rollback()

    client.post(f"{P}/red-flags/{flag_id}/resolve", json={"resolution": "resolved"})
    clear = selection.compute(db, current_user=user, now=now, origin=None)
    assert clear.chosen.mission.id == heavy.id and {c.notes["g5"] for c in clear.candidates} == {"clear"}
