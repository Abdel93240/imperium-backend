from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.imperium import (
    ImperiumDailyPlan,
    ImperiumDayReview,
    ImperiumMission,
    ImperiumPathItem,
    ImperiumPriorityRule,
)
from app.models.vault import VaultTransaction
from app.schemas.imperium import (
    DashboardDayReview,
    DashboardMission,
    DashboardPriority,
    DashboardSystemStatus,
    DashboardVaultWeek,
    DailyPlanResponse,
    ImperiumDashboardResponse,
    PathItemResponse,
)
from app.services.imperium.weekly_review_state import get_weekly_review_banner

PARIS_TIMEZONE = "Europe/Paris"
ZERO = Decimal("0.00")


def get_dashboard_snapshot(db: Session, *, current_user: User) -> ImperiumDashboardResponse:
    generated_at = datetime.now(UTC)
    today = generated_at.astimezone(ZoneInfo(PARIS_TIMEZONE)).date()
    week_start = _current_local_week_start(PARIS_TIMEZONE, generated_at)
    week_end = week_start + timedelta(days=6)

    # NOTE: 7 sequential queries — acceptable V1 latency.
    # Optimize with joins or async in V2 if dashboard latency > 100ms.
    current_mission = db.scalar(
        select(ImperiumMission).where(
            ImperiumMission.user_id == current_user.id,
            ImperiumMission.status == "active",
        )
    )
    recent_missions = list(
        db.scalars(
            select(ImperiumMission)
            .where(ImperiumMission.user_id == current_user.id)
            .order_by(ImperiumMission.started_at.desc())
            .limit(5)
        )
    )
    priorities = list(
        db.scalars(
            select(ImperiumPriorityRule)
            .where(
                ImperiumPriorityRule.user_id == current_user.id,
                ImperiumPriorityRule.is_active.is_(True),
            )
            .order_by(ImperiumPriorityRule.rank_order.asc(), ImperiumPriorityRule.created_at.asc())
        )
    )
    latest_day_review = db.scalar(
        select(ImperiumDayReview)
        .where(ImperiumDayReview.user_id == current_user.id)
        .order_by(ImperiumDayReview.local_date.desc(), ImperiumDayReview.created_at.desc())
        .limit(1)
    )
    vault_transactions = list(
        db.scalars(
            select(VaultTransaction).where(
                VaultTransaction.user_id == current_user.id,
                VaultTransaction.local_date >= week_start,
                VaultTransaction.local_date <= week_end,
            )
        )
    )
    path_today = list(
        db.scalars(
            select(ImperiumPathItem)
            .where(
                ImperiumPathItem.user_id == current_user.id,
                ImperiumPathItem.local_date == today,
            )
            .order_by(
                ImperiumPathItem.sort_order.asc(),
                ImperiumPathItem.planned_start.asc().nulls_last(),
                ImperiumPathItem.created_at.asc(),
            )
        )
    )
    daily_plan_today = db.scalar(
        select(ImperiumDailyPlan).where(
            ImperiumDailyPlan.user_id == current_user.id,
            ImperiumDailyPlan.local_date == today,
        )
    )

    weekly_review_banner = get_weekly_review_banner(db, current_user=current_user)

    return ImperiumDashboardResponse(
        current_mission=_dashboard_mission(current_mission) if current_mission else None,
        recent_missions=[_dashboard_mission(mission) for mission in recent_missions],
        priorities=[_dashboard_priority(priority) for priority in priorities],
        latest_day_review=_dashboard_day_review(latest_day_review) if latest_day_review else None,
        vault_week=_dashboard_vault_week(week_start, week_end, vault_transactions),
        path_today=[PathItemResponse.model_validate(item) for item in path_today],
        path_counts_today=_path_counts(path_today),
        daily_plan_today=DailyPlanResponse.model_validate(daily_plan_today) if daily_plan_today else None,
        weekly_review_banner=weekly_review_banner,
        system_status=DashboardSystemStatus(
            api_status="ok",
            db_status="ok",
            generated_at=generated_at,
        ),
    )


def _path_counts(items: list[ImperiumPathItem]) -> dict[str, int]:
    counts = {
        "planned": 0,
        "in_progress": 0,
        "completed": 0,
        "skipped": 0,
        "cancelled": 0,
    }
    for item in items:
        if item.status in counts:
            counts[item.status] += 1
    return counts


def _current_local_week_start(timezone: str, generated_at: datetime) -> date:
    local_today = generated_at.astimezone(ZoneInfo(timezone)).date()
    return local_today - timedelta(days=local_today.weekday())


def _dashboard_mission(mission: ImperiumMission) -> DashboardMission:
    completed_at = mission.ended_at if mission.status == "completed" else None
    failed_at = mission.ended_at if mission.status == "failed" else None
    return DashboardMission(
        id=mission.id,
        status=mission.status,
        title=mission.title,
        category=mission.category,
        started_at=mission.started_at,
        ended_at=mission.ended_at,
        completed_at=completed_at,
        failed_at=failed_at,
    )


def _dashboard_priority(priority: ImperiumPriorityRule) -> DashboardPriority:
    return DashboardPriority(
        priority_key=priority.priority_key,
        label=priority.label,
        rank_order=priority.rank_order,
        importance_score=priority.importance_score,
    )


def _dashboard_day_review(review: ImperiumDayReview) -> DashboardDayReview:
    return DashboardDayReview(
        id=review.id,
        local_date=review.local_date,
        timezone=review.timezone,
        day_status=review.day_status,
        energy_level=review.energy_level,
        fatigue_level=review.fatigue_level,
        sleep_quality=review.sleep_quality,
        stress_level=review.stress_level,
        mood=review.mood,
        main_win=review.main_win,
        main_problem=review.main_problem,
        notes=review.notes,
        created_at=review.created_at,
    )


def _dashboard_vault_week(
    week_start: date,
    week_end: date,
    transactions: list[VaultTransaction],
) -> DashboardVaultWeek:
    income_total = ZERO
    expense_total = ZERO
    correction_total = ZERO

    for transaction in transactions:
        amount = _money(transaction.amount)
        if transaction.transaction_type == "income":
            income_total += amount
        elif transaction.transaction_type == "expense":
            expense_total += amount
        elif transaction.transaction_type == "correction":
            correction_total += amount

    income_total = _money(income_total)
    expense_total = _money(expense_total)
    correction_total = _money(correction_total)
    return DashboardVaultWeek(
        week_start=week_start,
        week_end=week_end,
        income_total=income_total,
        expense_total=expense_total,
        net_total=_money(income_total - expense_total + correction_total),
        transaction_count=len(transactions),
    )


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))
