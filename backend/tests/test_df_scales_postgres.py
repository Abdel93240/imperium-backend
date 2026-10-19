"""PostgreSQL : le service lit les barèmes `df.*` semés (spec Daily §4, carte ACT-DLY-01)."""
from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("df scales DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.services.imperium import decision_framework as df  # noqa: E402
from app.services.params import set_parameter  # noqa: E402

PREVIEW = {"domain": "religious", "impact": "critical", "mission_type": "cat_a", "dependency": "many",
           "recurrence": "weekly"}


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


def _client(db) -> TestClient:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"df-{user_id}@example.test"})
    user = db.get(User, user_id)
    app = FastAPI()
    app.include_router(imperium.router, prefix="/api/imperium")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def test_seeded_parameters_load_as_the_code_scales(db) -> None:
    assert df.load_scales(db) == df.CODE_SCALES
    assert df.load_scales(db) is df.load_scales(db)  # cache par version


def test_a_new_version_changes_the_score_and_invalid_falls_back(db) -> None:
    client = _client(db)
    before = client.post("/api/imperium/decision-framework/score-preview", json=PREVIEW).json()
    assert before["intrinsic_score"] == 20 + 20 + 10 + 3  # sans échéance
    impact = dict(df.CODE_SCALES.impact, critical=25)
    set_parameter(db, code="df.impact_points", value=impact, origin="user", rationale_fr="Test : critique à 25.")
    after = client.post("/api/imperium/decision-framework/score-preview", json=PREVIEW).json()
    assert after["intrinsic_score"] == before["intrinsic_score"] + 5  # cache invalidé par la nouvelle version
    set_parameter(db, code="df.impact_points", value={"critical": 99}, origin="user", rationale_fr="Test invalide.")
    assert df.load_scales(db) == df.CODE_SCALES  # repli journalisé sur les constantes
    db.rollback()
    assert df.load_scales(db) == df.CODE_SCALES
