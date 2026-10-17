"""Alertes de date limite du stock Pulse (doc 40 §11.3) — règles, bannière et job de 9 h."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest

from app.services.pulse import expiry

TODAY = date(2026, 10, 17)


@pytest.mark.parametrize(
    ("expiry_type", "offset", "level"),
    [
        ("DLC", -1, "error"), ("DLC", 0, "warning"), ("DLC", 2, "warning"), ("DLC", 3, None),
        ("DDM", -10, "info"), ("DDM", 7, "info"), ("DDM", 8, None), ("unknown", -5, None),
    ],
)
def test_rules(expiry_type, offset, level) -> None:
    assert expiry.classify(expiry_type, TODAY + timedelta(days=offset), TODAY)[0] == level


def test_no_date_means_no_alert() -> None:
    assert expiry.classify("DLC", None, TODAY) == (None, None)


def test_paris_day_and_message() -> None:
    assert expiry.paris_today(datetime(2026, 10, 16, 22, 30, tzinfo=UTC)) == date(2026, 10, 17)  # 00 h 30 à Paris
    report = expiry.ExpiryReport(today=TODAY, level="error", alerts=[
        expiry.ExpiryAlert("1", "Lait", "DLC", TODAY, -1, "error"),
        expiry.ExpiryAlert("2", "Yaourt", "DLC", TODAY, 1, "warning"),
        expiry.ExpiryAlert("3", "Riz", "DDM", TODAY, 5, "info"),
    ])
    assert report.message_fr == "Stock : 1 produit dépassé, 1 à consommer rapidement, 1 à consommer cette semaine."
    assert report.to_consume == 2
    assert expiry.ExpiryReport(today=TODAY).message_fr is None


def test_job_does_nothing_outside_9h_paris() -> None:
    ctx = SimpleNamespace(db=None, items_in=None, items_out=None, detail={})
    # 8 h UTC en été = 10 h à Paris : le second créneau ne fait rien.
    expiry.food_stock_expiry_job(ctx, SimpleNamespace(from_ts=None, to_ts=datetime(2026, 7, 1, 8, 0, tzinfo=UTC)))
    assert ctx.detail == {"skip": "not_9h_paris"}


# ---------- PostgreSQL ----------

def _db_url():
    import os

    url = os.environ.get("IMPERIUM_TEST_DATABASE_URL")
    if not url:
        pytest.skip("IMPERIUM_TEST_DATABASE_URL not set.")
    return url


@pytest.fixture()
def db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    engine = create_engine(_db_url(), future=True)
    with Session(engine) as session:
        yield session
        session.rollback()
    engine.dispose()


def _user(db):
    from sqlalchemy import text

    from app.models.auth import User

    user_id = uuid4()
    db.execute(
        text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) VALUES (:id, :email, FALSE, now(), now())"),
        {"id": str(user_id), "email": f"expiry-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _stock(db, user, name, expiry_type, offset, status="active"):
    from app.models.imperium import FoodStockItem

    db.add(FoodStockItem(user_id=user.id, name=name, quantity=1, unit="piece", expiry_type=expiry_type,
                         expiry_date=None if offset is None else TODAY + timedelta(days=offset), source="manual",
                         status=status, version=1))
    db.commit()


@pytest.mark.postgres
def test_alerts_route_orders_by_urgency_and_ignores_inactive(db) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_user, get_db
    from app.api.v1.routes import imperium_pulse_stock as routes

    user = _user(db)
    _stock(db, user, "Riz", "DDM", 3)
    _stock(db, user, "Yaourt", "DLC", 1)
    _stock(db, user, "Lait", "DLC", -2)
    _stock(db, user, "Pâtes", "DDM", 200)
    _stock(db, user, "Crème", "DLC", -1, status="consumed")
    _stock(db, user, "Sel", "unknown", None)
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/imperium/pulse")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    original = expiry.paris_today
    expiry.paris_today = lambda now=None: TODAY
    try:
        body = TestClient(app).get("/api/imperium/pulse/food-stock/alerts").json()
    finally:
        expiry.paris_today = original
    assert [(a["name"], a["level"], a["days_left"]) for a in body["alerts"]] == [
        ("Lait", "error", -2), ("Yaourt", "warning", 1), ("Riz", "info", 3)]
    assert body["level"] == "error" and body["to_consume"] == 2 and body["message_fr"].startswith("Stock : 1 produit dépassé")


@pytest.mark.postgres
def test_job_sends_one_notification_per_day_at_the_highest_level(db, monkeypatch) -> None:
    from sqlalchemy import select

    from app.models.toolbox import Notification

    user = _user(db)
    _stock(db, user, "Yaourt", "DLC", 1)
    _stock(db, user, "Lait", "DLC", -1)
    monkeypatch.setattr(expiry, "_job_user", lambda session: user)
    nine_paris = SimpleNamespace(from_ts=None, to_ts=datetime(2026, 10, 17, 7, 0, tzinfo=UTC))  # 9 h CEST
    for _ in range(2):
        ctx = SimpleNamespace(db=db, items_in=None, items_out=None, detail={})
        expiry.food_stock_expiry_job(ctx, nine_paris)
        db.commit()
    ref_id = uuid5(NAMESPACE_URL, f"imperium:food_stock_expiry:{user.id}:{TODAY}")
    mine = list(db.scalars(select(Notification).where(Notification.ref_type == "food_stock_expiry_day",
                                                      Notification.ref_id == ref_id)))
    assert len(mine) == 1 and mine[0].severity == "red" and mine[0].domain == "pulse"
    assert mine[0].message_fr == "Stock : 1 produit dépassé, 1 à consommer rapidement."


@pytest.mark.postgres
def test_job_is_silent_when_nothing_expires(db, monkeypatch) -> None:
    user = _user(db)
    _stock(db, user, "Pâtes", "DDM", 200)
    monkeypatch.setattr(expiry, "_job_user", lambda session: user)
    ctx = SimpleNamespace(db=db, items_in=None, items_out=None, detail={})
    expiry.food_stock_expiry_job(ctx, SimpleNamespace(from_ts=None, to_ts=datetime(2026, 12, 1, 8, 0, tzinfo=UTC)))  # 9 h CET
    assert ctx.detail == {"level": "none", "alerts": 0, "notified": 0}


def test_seeded_job_handler_resolves() -> None:
    from app.services.runner.engine import resolve_handler

    assert resolve_handler("app.services.pulse.expiry:food_stock_expiry_job") is expiry.food_stock_expiry_job
