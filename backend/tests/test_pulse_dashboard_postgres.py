"""PostgreSQL : tableau de bord Pulse du jour (PUL-01, doc 40 §9)."""
from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("pulse dashboard DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import (  # noqa: E402
    imperium_pulse,
    imperium_pulse_dashboard,
    imperium_pulse_hydration,
    imperium_pulse_meals,
    imperium_pulse_stock,
)
from app.models.auth import User  # noqa: E402

P = "/api/imperium/pulse"


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
        {"id": str(user_id), "email": f"dash-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    for module in (imperium_pulse, imperium_pulse_dashboard, imperium_pulse_hydration, imperium_pulse_meals, imperium_pulse_stock):
        app.include_router(module.router, prefix="/api/imperium/pulse")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def test_empty_day_shows_zeros_and_hides_the_health_score(db) -> None:
    body = _client(db, _user(db)).get(f"{P}/dashboard", params={"day": "2026-10-17"}).json()
    assert body["day"] == "2026-10-17" and body["entry"] is None
    assert body["meals"] == {"count": 0, "totals": {"calories": "0.0", "protein_g": "0.0", "carbs_g": "0.0", "fat_g": "0.0"},
                             "without_macros": 0, "drafts_pending": 0}
    assert body["hydration"] == {"total_ml": 0, "target": None, "target_message": "Objectif personnalisé pas encore calculé."}
    assert body["stock"]["level"] == "none" and body["health_score"] is None
    assert body["banners"] == [{"kind": "health_score_incomplete", "level": "info",
                                "message": "Score santé masqué : pas encore assez de données pour l'expliquer."}]


def test_day_combines_entry_meals_water_and_stock(db) -> None:
    client = _client(db, _user(db))
    client.post(f"{P}/entries", headers=_key(), json={"entry_date": "2026-10-17", "sleep_hours": 7.5, "energy_level": 7})
    for description, calories in [("Déjeuner", 700), ("Dîner", None)]:
        draft = client.post(f"{P}/meals/drafts", headers=_key(),
                            json={"description": description, "eaten_at": "2026-10-17T12:00:00+00:00"}).json()
        client.post(f"{P}/meals/{draft['id']}/confirm", headers=_key(), json={"calories": calories} if calories else {})
    client.post(f"{P}/meals/drafts", headers=_key(), json={"description": "Goûter", "eaten_at": "2026-10-17T15:00:00+00:00"})
    client.post(f"{P}/meals/drafts", headers=_key(), json={"description": "Veille", "eaten_at": "2026-10-16T12:00:00+00:00"})
    client.post(f"{P}/hydration-logs", headers=_key(), json={"amount_ml": 500, "logged_at": "2026-10-17T09:00:00+00:00"})
    client.post(f"{P}/food-stock", headers=_key(), json={"name": "Yaourt", "quantity": 4, "expiry_type": "DLC",
                                                        "expiry_date": "2026-10-18"})
    body = client.get(f"{P}/dashboard", params={"day": "2026-10-17"}).json()
    assert (body["entry"]["sleep_hours"], body["entry"]["energy_level"]) == (7.5, 7)
    assert (body["meals"]["count"], body["meals"]["totals"]["calories"], body["meals"]["without_macros"],
            body["meals"]["drafts_pending"]) == (2, "700.0", 1, 1)
    assert body["hydration"]["total_ml"] == 500
    assert body["stock"]["to_consume"] == 1 and body["stock"]["alerts"][0]["name"] == "Yaourt"
    assert [b["kind"] for b in body["banners"]] == ["stock_expiry", "meal_drafts", "meals_without_macros",
                                                     "health_score_incomplete"]
    assert body["banners"][1]["message"] == "1 repas en brouillon à valider."
    assert body["banners"][2]["message"] == "1 repas sans macros : les totaux sont incomplets."


def test_dashboard_is_scoped_to_the_user(db) -> None:
    owner, other = _user(db), _user(db)
    _client(db, owner).post(f"{P}/hydration-logs", headers=_key(), json={"amount_ml": 1000})
    assert _client(db, other).get(f"{P}/dashboard").json()["hydration"]["total_ml"] == 0
