"""PostgreSQL : réglage versionné des barèmes df.* (spec Daily §4.5, §10.3 ; carte ACT-DLY-02)."""
from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("daily scoring settings DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import daily, imperium  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.services.daily import scoring_settings  # noqa: E402
from app.services.imperium import decision_framework as df  # noqa: E402

BASE = "/api/daily/settings/scoring"
PREVIEW = {"domain": "religious", "impact": "critical", "mission_type": "cat_a", "dependency": "many",
           "recurrence": "weekly"}


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    # Le réglage committe : tout tourne dans une transaction externe annulée (rien ne fuit vers les autres tests).
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def _setup(db):
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"dfs-{user_id}@example.test"})
    db.commit()  # savepoint relâché dans la transaction externe : survit aux rollbacks des routes
    user = db.get(User, user_id)
    app = FastAPI()
    app.include_router(daily.router, prefix="/api/daily")
    app.include_router(imperium.router, prefix="/api/imperium")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return user, TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def test_routes_are_cut_while_the_flag_is_off(db) -> None:
    assert scoring_settings.settings_enabled(db) is False  # seed
    _, client = _setup(db)
    assert client.get(BASE).json()["code"] == "DAILY_SETTINGS_DISABLED"
    assert client.get(f"{BASE}/df.impact_points/versions").status_code == 409
    body = {"changes": {"df.impact_points": dict(df.CODE_SCALES.impact, critical=25)}, "reason_fr": "Essai."}
    refused = client.put(BASE, json=body, headers=_key())
    assert (refused.status_code, refused.json()["code"]) == (409, "DAILY_SETTINGS_DISABLED")
    assert db.scalar(text("SELECT max(version) FROM parameters WHERE code = 'df.impact_points'")) == 1


def test_update_creates_versions_events_and_changes_the_score(db, monkeypatch) -> None:
    monkeypatch.setattr(scoring_settings, "settings_enabled", lambda db: True)
    user, client = _setup(db)
    current = client.get(BASE).json()
    assert current["source"] == "parameters" and len(current["parameters"]) == 8
    before = client.post("/api/imperium/decision-framework/score-preview", json=PREVIEW).json()["intrinsic_score"]

    impact = dict(df.CODE_SCALES.impact, critical=25)
    coefficients = {"1": 12, "2": 8, "3": 5, "4": 4}
    body = {"changes": {"df.impact_points": impact, "df.coefficient_by_position": coefficients,
                        "df.recurrence_points": dict(df.CODE_SCALES.recurrence)},  # inchangé : pas de version
            "reason_fr": "Le critique pèse plus que prévu."}
    key = _key()
    updated = client.put(BASE, json=body, headers=key)
    assert updated.status_code == 200
    versions = {row["code"]: row["version"] for row in updated.json()["parameters"]}
    assert (versions["df.impact_points"], versions["df.coefficient_by_position"], versions["df.recurrence_points"]) == (2, 2, 1)
    assert client.put(BASE, json=body, headers=key).json() == updated.json()  # rejeu idempotent

    after = client.post("/api/imperium/decision-framework/score-preview", json=PREVIEW).json()["intrinsic_score"]
    assert after == before + 5
    assert df.get_domain_coefficient(1, df.load_scales(db)) == 12

    history = client.get(f"{BASE}/df.impact_points/versions").json()["versions"]
    assert [(row["version"], row["origin"]) for row in history] == [(2, "user"), (1, "seed")]
    assert history[0]["rationale_fr"] == "Le critique pèse plus que prévu." and history[1]["value"]["critical"] == 20
    events = db.scalars(select(Event).where(Event.user_id == user.id, Event.event_type == "decision.scoring.updated")
                        .order_by(Event.idempotency_key)).all()
    assert sorted((e.payload["param_code"], e.payload["old_version"], e.payload["new_version"]) for e in events) == [
        ("df.coefficient_by_position", 1, 2), ("df.impact_points", 1, 2)]


def test_update_refusals(db, monkeypatch) -> None:
    monkeypatch.setattr(scoring_settings, "settings_enabled", lambda db: True)
    _, client = _setup(db)
    assert client.put(BASE, json={"changes": {"df.impact_points": {}}, "reason_fr": "Sans clé."}).status_code == 400
    assert client.put(BASE, json={"changes": {"df.impact_points": {"a": 1}}}, headers=_key()).status_code == 422
    cases = [
        ({"df.unknown": {"a": 1}}, 422, "SCORING_PARAMETER_UNKNOWN"),
        ({"df.impact_points": dict(df.CODE_SCALES.impact)}, 409, "SCORING_NO_CHANGE"),
        ({"df.impact_points": dict(df.CODE_SCALES.impact, critical=31)}, 422, "SCORING_INVALID"),
        ({"df.criterion_max": {"deadline": 40, "impact": 30, "mission_type": 20, "dependency": 10, "recurrence": 10}},
         422, "SCORING_INVALID"),
    ]
    for changes, status_code, code in cases:
        response = client.put(BASE, json={"changes": changes, "reason_fr": "Essai."}, headers=_key())
        assert (response.status_code, response.json()["code"]) == (status_code, code), changes
    assert client.get(f"{BASE}/df.nope/versions").json()["code"] == "SCORING_PARAMETER_UNKNOWN"
    assert db.scalar(text("SELECT max(version) FROM parameters WHERE code LIKE 'df.%'")) == 1
