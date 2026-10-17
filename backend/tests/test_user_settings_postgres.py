"""PostgreSQL : réglages Imperium (doc 43 §15, doc 65 §8.5, décisions 2026-10-15/16/17)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("user settings DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models.auth import User  # noqa: E402
from app.models.imperium import ImperiumDailyPlan, PlanningDay  # noqa: E402
from app.schemas.imperium import ReplanRequestCreate  # noqa: E402
from app.schemas.settings import UserSettingsUpdate  # noqa: E402
from app.services.imperium import settings as user_settings  # noqa: E402
from app.services.imperium.replan import ReplanCooldownError, cancel_replan, request_replan  # noqa: E402


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
        {"id": str(user_id), "email": f"settings-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def test_defaults_follow_the_docs(db) -> None:
    user = _user(db)
    read = user_settings.get_settings(db, current_user=user)
    assert read.model_dump() == {
        "bubble_enabled": True,
        "notifications_enabled": True,
        "notify_weekly_review": True,
        "notify_mission_reminders": True,
        "notify_red_alerts": True,
        "morning_popup_enabled": True,
        "ai_mode": "equilibre",
        "replan_on_failure_urgent": "replan",
        "replan_on_failure_other": "ask",
        "replan_debounce_minutes": 5,
        "chat_retention_days": 90,
    }


def test_partial_update_persists_and_keeps_other_values(db) -> None:
    user = _user(db)
    user_settings.update_settings(db, current_user=user, payload=UserSettingsUpdate(ai_mode="strict", notify_red_alerts=False))
    read = user_settings.get_settings(db, current_user=user)
    assert (read.ai_mode, read.notify_red_alerts, read.bubble_enabled) == ("strict", False, True)


def test_settings_are_user_scoped(db) -> None:
    user, other = _user(db), _user(db)
    user_settings.update_settings(db, current_user=user, payload=UserSettingsUpdate(chat_retention_days=30))
    assert user_settings.get_settings(db, current_user=other).chat_retention_days == 90


def test_one_settings_row_per_user_and_db_constraints(db) -> None:
    user = _user(db)
    user_settings.get_settings(db, current_user=user)
    with pytest.raises(IntegrityError):
        db.execute(text("INSERT INTO imperium_user_settings (id, user_id) VALUES (gen_random_uuid(), :u)"), {"u": str(user.id)})
    db.rollback()
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE imperium_user_settings SET ai_mode = 'turbo' WHERE user_id = :u"), {"u": str(user.id)})
    db.rollback()
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE imperium_user_settings SET chat_retention_days = 45 WHERE user_id = :u"), {"u": str(user.id)})


def test_replan_debounce_reads_the_user_setting(db) -> None:
    user = _user(db)
    t0 = datetime(2026, 10, 17, 8, 0, tzinfo=UTC)
    db.add(PlanningDay(user_id=user.id, started_at=t0 - timedelta(hours=2), start_local_date=date(2026, 10, 17),
                       timezone="Europe/Paris", felt_energy=3, idempotency_key=f"d-{uuid4().hex}"))
    db.add(ImperiumDailyPlan(user_id=user.id, local_date=date(2026, 10, 17), timezone="Europe/Paris", plan_status="active",
                             generated_from={}, plan_blocks=[]))
    db.commit()
    user_settings.update_settings(db, current_user=user, payload=UserSettingsUpdate(replan_debounce_minutes=10))

    def ask(now):
        return request_replan(db, current_user=user, payload=ReplanRequestCreate(reason_category="fatigue", reason_detail="Longue nuit."),
                              idempotency_key=f"k-{uuid4().hex}", request_method="POST", request_path="/x", now=now)

    first, _ = ask(t0)
    cancel_replan(db, current_user=user, replan_id=first.id, now=t0)
    with pytest.raises(ReplanCooldownError) as err:
        ask(t0 + timedelta(minutes=7))
    assert err.value.eligible_at == t0 + timedelta(minutes=10)
