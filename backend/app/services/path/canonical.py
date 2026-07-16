"""Canonical Path read source (C-1, passe 0): habits + check-ins.

dashboard.py, weekly_report.py and daily_plans.py stop reading the legacy
imperium_path_items table and read habits/check-ins through this module.
The legacy tables are NOT dropped (PHASE_0): they only lose their last readers.

Mapping (consigned in SOCLE_MAPPING.md):
- a habit due today with no check-in  → status 'planned'
- check-in status 'done'              → status 'completed'
- check-in status 'missed'            → status 'skipped' (reason = skip_reason)
- weekly due slots: daily habit = one per day, weekly habit = one per week.
'in_progress' and 'cancelled' do not exist canonically (always 0).

Where real data DIVERGES between legacy and canonical (the reason this
migration exists), report_legacy_divergence() emits ONE 'normal' notification
(deduplicated by notify()'s 24 h window).
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.imperium import ImperiumPathCheckIn, ImperiumPathHabit, ImperiumPathItem

logger = logging.getLogger(__name__)

_STATUS_FROM_CHECK_IN = {"done": "completed", "missed": "skipped"}


@dataclass
class CanonicalPathToday:
    """PathItemResponse-compatible view of one habit's state today."""

    id: UUID
    local_date: date
    timezone: str
    title: str
    description: str | None
    category: str | None
    priority_key: str | None
    planned_start: datetime | None
    planned_end: datetime | None
    status: str
    source: str
    sort_order: int
    skip_reason: str | None
    completed_at: datetime | None
    skipped_at: datetime | None
    cancelled_at: datetime | None
    item_metadata: dict = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    idempotency_key: str | None = None


def path_today_view(
    db: Session, *, current_user: User, local_date: date, timezone: str = "Europe/Paris"
) -> list[CanonicalPathToday]:
    habits = list(
        db.scalars(
            select(ImperiumPathHabit)
            .where(
                ImperiumPathHabit.user_id == current_user.id,
                ImperiumPathHabit.is_active.is_(True),
            )
            .order_by(ImperiumPathHabit.created_at.asc())
        )
    )
    check_ins = {
        check_in.habit_id: check_in
        for check_in in db.scalars(
            select(ImperiumPathCheckIn).where(
                ImperiumPathCheckIn.user_id == current_user.id,
                ImperiumPathCheckIn.check_date == local_date,
            )
        )
    }
    view: list[CanonicalPathToday] = []
    for sort_order, habit in enumerate(habits):
        check_in = check_ins.get(habit.id)
        status = _STATUS_FROM_CHECK_IN.get(check_in.status, "planned") if check_in else "planned"
        view.append(
            CanonicalPathToday(
                id=habit.id,
                local_date=local_date,
                timezone=timezone,
                title=habit.title,
                description=habit.description,
                category=habit.domain,
                priority_key=None,
                planned_start=None,
                planned_end=None,
                status=status,
                source="canonical_habit",
                sort_order=sort_order,
                skip_reason=check_in.reason if check_in and status == "skipped" else None,
                completed_at=check_in.updated_at if check_in and status == "completed" else None,
                skipped_at=check_in.updated_at if check_in and status == "skipped" else None,
                cancelled_at=None,
                created_at=habit.created_at,
                updated_at=habit.updated_at,
            )
        )
    return view


def path_week_stats(
    db: Session, *, current_user: User, week_start: date, week_end_exclusive: date
) -> dict[str, int]:
    """Weekly status counts from the canonical source (feeds WeeklyReportPath)."""
    habits = list(
        db.scalars(
            select(ImperiumPathHabit).where(
                ImperiumPathHabit.user_id == current_user.id,
                ImperiumPathHabit.is_active.is_(True),
            )
        )
    )
    check_ins = list(
        db.scalars(
            select(ImperiumPathCheckIn).where(
                ImperiumPathCheckIn.user_id == current_user.id,
                ImperiumPathCheckIn.check_date >= week_start,
                ImperiumPathCheckIn.check_date < week_end_exclusive,
            )
        )
    )
    days = (week_end_exclusive - week_start).days
    total_due = sum(days if habit.frequency == "daily" else 1 for habit in habits)
    completed = sum(1 for check_in in check_ins if check_in.status == "done")
    skipped = sum(1 for check_in in check_ins if check_in.status == "missed")
    total = max(total_due, completed + skipped)
    return {
        "total_items": total,
        "planned": max(total - completed - skipped, 0),
        "in_progress": 0,
        "completed": completed,
        "skipped": skipped,
        "cancelled": 0,
    }


def report_legacy_divergence(
    db: Session,
    *,
    current_user: User,
    local_date: date,
    canonical: list[CanonicalPathToday] | None = None,
) -> None:
    """Compare legacy path_items vs canonical for the day; notify once on gaps."""
    legacy_items = list(
        db.scalars(
            select(ImperiumPathItem).where(
                ImperiumPathItem.user_id == current_user.id,
                ImperiumPathItem.local_date == local_date,
            )
        )
    )
    if canonical is None:
        canonical = path_today_view(db, current_user=current_user, local_date=local_date)
    legacy_counts = _counts(item.status for item in legacy_items)
    canonical_counts = _counts(item.status for item in canonical)
    if legacy_counts == canonical_counts:
        return
    from app.services.notifications import notify

    try:
        notify(
            db,
            severity="normal",
            domain="path",
            message_fr=(
                f"Écart legacy↔canonique Path le {local_date} : "
                f"legacy={legacy_counts}, canonique={canonical_counts}. "
                "Les lecteurs affichent désormais le canonique (C-1)."
            ),
            ref=("path_legacy_divergence", current_user.id),
        )
    except Exception:  # noqa: BLE001 - a report must never break a read path
        logger.exception("Legacy divergence report failed.")


def _counts(statuses) -> dict[str, int]:
    counts: dict[str, int] = {}
    for status in statuses:
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def week_start_of(day: date) -> date:
    return day - timedelta(days=day.weekday())
