"""§13.9 legacy readers (C-1): parity on identical fixtures, divergence report."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select

from _postgres import require_test_database_url

pytest.importorskip("psycopg")

from sqlalchemy.orm import Session  # noqa: E402

from app.models import ai, auth, event, idempotency, imperium, path, toolbox, vault  # noqa: E402,F401
from app.models.imperium import (  # noqa: E402
    ImperiumPathCheckIn,
    ImperiumPathHabit,
    ImperiumPathItem,
)
from app.models.toolbox import Notification  # noqa: E402
from app.services.path.canonical import (  # noqa: E402
    path_today_view,
    path_week_stats,
    report_legacy_divergence,
)

DAY = date(2026, 7, 13)  # a Monday


@pytest.fixture(scope="module")
def engine():
    engine = create_engine(require_test_database_url("toolbox legacy parity tests"), future=True)
    yield engine
    engine.dispose()


@pytest.fixture()
def user(engine):
    from sqlalchemy import text

    user_id = uuid4()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                "VALUES (:id, :email, FALSE, now(), now())"
            ),
            {"id": str(user_id), "email": f"parity-{user_id}@example.test"},
        )
    from types import SimpleNamespace

    return SimpleNamespace(id=user_id)


def _seed_identical_facts(db: Session, user) -> None:
    """The same three logical facts recorded in BOTH sources: one done, one
    missed (with reason), one still planned."""
    facts = [
        ("Prière Fajr à l'heure", "completed", "done"),
        ("Lecture Coran", "skipped", "missed"),
        ("Adhkar du soir", "planned", None),
    ]
    for title, item_status, check_status in facts:
        db.add(
            ImperiumPathItem(
                id=uuid4(),
                user_id=user.id,
                local_date=DAY,
                timezone="Europe/Paris",
                title=title,
                status=item_status,
                source="manual",
                sort_order=0,
                skip_reason="fatigue" if item_status == "skipped" else None,
            )
        )
        habit = ImperiumPathHabit(
            id=uuid4(), user_id=user.id, title=title, frequency="daily", is_active=True
        )
        db.add(habit)
        db.flush()
        if check_status is not None:
            db.add(
                ImperiumPathCheckIn(
                    id=uuid4(),
                    user_id=user.id,
                    habit_id=habit.id,
                    check_date=DAY,
                    status=check_status,
                    reason="fatigue" if check_status == "missed" else None,
                )
            )
    db.flush()


def test_parity_identical_fixtures_yield_identical_displayed_numbers(engine, user) -> None:
    with Session(engine) as db:
        _seed_identical_facts(db, user)

        legacy_items = db.scalars(
            select(ImperiumPathItem).where(
                ImperiumPathItem.user_id == user.id, ImperiumPathItem.local_date == DAY
            )
        ).all()
        legacy_counts = {
            status: sum(1 for item in legacy_items if item.status == status)
            for status in ("planned", "completed", "skipped")
        }

        canonical = path_today_view(db, current_user=user, local_date=DAY)
        canonical_counts = {
            status: sum(1 for item in canonical if item.status == status)
            for status in ("planned", "completed", "skipped")
        }
        assert canonical_counts == legacy_counts  # parity lock

        week_stats = path_week_stats(
            db, current_user=user, week_start=DAY, week_end_exclusive=DAY.replace(day=DAY.day + 7)
        )
        # 3 daily habits × 7 days due; done/missed counts match the facts.
        assert week_stats["completed"] == legacy_counts["completed"]
        assert week_stats["skipped"] == legacy_counts["skipped"]
        assert week_stats["total_items"] == 21
        db.rollback()


def test_real_divergence_produces_one_normal_notification(engine, user) -> None:
    with Session(engine) as db:
        # Divergent data: legacy has one completed item, canonical has nothing.
        db.add(
            ImperiumPathItem(
                id=uuid4(),
                user_id=user.id,
                local_date=DAY,
                timezone="Europe/Paris",
                title="Item legacy seulement",
                status="completed",
                source="manual",
                sort_order=0,
            )
        )
        db.flush()

        report_legacy_divergence(db, current_user=user, local_date=DAY)
        report_legacy_divergence(db, current_user=user, local_date=DAY)  # dedup

        notifications = db.scalars(
            select(Notification).where(
                Notification.ref_type == "path_legacy_divergence",
                Notification.ref_id == user.id,
            )
        ).all()
        assert len(notifications) == 1  # once, severity normal
        assert notifications[0].severity == "normal"
        assert "legacy" in notifications[0].message_fr
        db.rollback()


def test_legacy_tables_are_not_dropped(engine) -> None:
    from sqlalchemy import text

    with engine.connect() as conn:
        names = {
            row.table_name
            for row in conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables WHERE table_name IN "
                    "('imperium_path_items', 'imperium_priority_rules', 'vault_transactions')"
                )
            )
        }
        assert names == {"imperium_path_items", "imperium_priority_rules", "vault_transactions"}


def test_no_reader_left_on_legacy_models() -> None:
    from pathlib import Path

    backend_root = Path(__file__).resolve().parents[1]
    for reader in ("dashboard.py", "weekly_report.py", "daily_plans.py"):
        text = (backend_root / "app" / "services" / "imperium" / reader).read_text(
            encoding="utf-8"
        )
        assert "ImperiumPathItem" not in text, reader
        assert "ImperiumPriorityRule" not in text, reader
        assert "LegacyVaultTransaction" not in text, reader
