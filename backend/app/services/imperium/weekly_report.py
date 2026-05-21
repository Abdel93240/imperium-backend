from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
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
    WeeklyReportDailyPlans,
    WeeklyReportDays,
    WeeklyReportMissionItem,
    WeeklyReportMissions,
    WeeklyReportPath,
    WeeklyReportPriority,
    WeeklyReportResponse,
    WeeklyReportSignals,
    WeeklyReportVault,
    WeeklyReportVaultCategory,
)

PARIS_TIMEZONE = "Europe/Paris"
ZERO = Decimal("0.00")


class InvalidWeekStartError(ValueError):
    pass


def get_weekly_report(
    db: Session,
    *,
    current_user: User,
    week_start: date,
    timezone: str = PARIS_TIMEZONE,
) -> WeeklyReportResponse:
    if week_start.weekday() != 0:
        raise InvalidWeekStartError("week_start must be a Monday.")

    week_end_exclusive = week_start + timedelta(days=7)
    week_end_inclusive = week_start + timedelta(days=6)
    week_start_dt = datetime.combine(week_start, time.min, tzinfo=ZoneInfo(timezone))
    week_end_dt = week_start_dt + timedelta(days=7)

    day_reviews = list(
        db.scalars(
            select(ImperiumDayReview).where(
                ImperiumDayReview.user_id == current_user.id,
                ImperiumDayReview.local_date >= week_start,
                ImperiumDayReview.local_date < week_end_exclusive,
            )
        )
    )
    missions = list(
        db.scalars(
            select(ImperiumMission)
            .where(
                ImperiumMission.user_id == current_user.id,
                ImperiumMission.started_at >= week_start_dt,
                ImperiumMission.started_at < week_end_dt,
            )
            .order_by(ImperiumMission.started_at.desc())
        )
    )
    path_items = list(
        db.scalars(
            select(ImperiumPathItem).where(
                ImperiumPathItem.user_id == current_user.id,
                ImperiumPathItem.local_date >= week_start,
                ImperiumPathItem.local_date < week_end_exclusive,
            )
        )
    )
    daily_plans = list(
        db.scalars(
            select(ImperiumDailyPlan).where(
                ImperiumDailyPlan.user_id == current_user.id,
                ImperiumDailyPlan.local_date >= week_start,
                ImperiumDailyPlan.local_date < week_end_exclusive,
            )
        )
    )
    transactions = list(
        db.scalars(
            select(VaultTransaction).where(
                VaultTransaction.user_id == current_user.id,
                VaultTransaction.local_date >= week_start,
                VaultTransaction.local_date < week_end_exclusive,
            )
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

    days = _build_days(day_reviews)
    path = _build_path(path_items)
    vault = _build_vault(transactions)
    signals = _build_signals(days=days, path=path, vault=vault, transaction_count=len(transactions))

    return WeeklyReportResponse(
        week_start=week_start,
        week_end=week_end_inclusive,
        timezone=timezone,
        days=days,
        missions=_build_missions(missions),
        path=path,
        daily_plans=_build_daily_plans(daily_plans),
        vault=vault,
        priorities=[
            WeeklyReportPriority(
                rank_order=priority.rank_order,
                priority_key=priority.priority_key,
                label=priority.label,
                importance_score=priority.importance_score,
            )
            for priority in priorities
        ],
        signals=signals,
    )


def _build_days(day_reviews: list[ImperiumDayReview]) -> WeeklyReportDays:
    completed_days = sum(1 for review in day_reviews if review.day_status == "completed")
    partial_days = sum(1 for review in day_reviews if review.day_status == "partial")
    failed_days = sum(1 for review in day_reviews if review.day_status == "failed")
    return WeeklyReportDays(
        total_days=7,
        reviewed_days=len(day_reviews),
        completed_days=completed_days,
        partial_days=partial_days,
        failed_days=failed_days,
        average_energy_level=_average([review.energy_level for review in day_reviews]),
        average_fatigue_level=_average([review.fatigue_level for review in day_reviews]),
        average_sleep_quality=_average([review.sleep_quality for review in day_reviews]),
        average_stress_level=_average([review.stress_level for review in day_reviews]),
    )


def _build_missions(missions: list[ImperiumMission]) -> WeeklyReportMissions:
    return WeeklyReportMissions(
        total=len(missions),
        active=sum(1 for mission in missions if mission.status == "active"),
        completed=sum(1 for mission in missions if mission.status == "completed"),
        failed=sum(1 for mission in missions if mission.status == "failed"),
        cancelled=sum(1 for mission in missions if mission.status == "cancelled"),
        recent=[
            WeeklyReportMissionItem(
                id=mission.id,
                status=mission.status,
                title=mission.title,
                category=mission.category,
                started_at=mission.started_at,
                ended_at=mission.ended_at,
            )
            for mission in missions[:5]
        ],
    )


def _build_path(path_items: list[ImperiumPathItem]) -> WeeklyReportPath:
    total = len(path_items)
    completed = sum(1 for item in path_items if item.status == "completed")
    completion_rate = None if total == 0 else _round2(Decimal(completed) / Decimal(total) * Decimal("100"))
    return WeeklyReportPath(
        total_items=total,
        planned=sum(1 for item in path_items if item.status == "planned"),
        in_progress=sum(1 for item in path_items if item.status == "in_progress"),
        completed=completed,
        skipped=sum(1 for item in path_items if item.status == "skipped"),
        cancelled=sum(1 for item in path_items if item.status == "cancelled"),
        completion_rate=completion_rate,
    )


def _build_daily_plans(daily_plans: list[ImperiumDailyPlan]) -> WeeklyReportDailyPlans:
    return WeeklyReportDailyPlans(
        total=len(daily_plans),
        draft=sum(1 for plan in daily_plans if plan.plan_status == "draft"),
        active=sum(1 for plan in daily_plans if plan.plan_status == "active"),
        completed=sum(1 for plan in daily_plans if plan.plan_status == "completed"),
        cancelled=sum(1 for plan in daily_plans if plan.plan_status == "cancelled"),
    )


def _build_vault(transactions: list[VaultTransaction]) -> WeeklyReportVault:
    income_total = ZERO
    expense_total = ZERO
    correction_total = ZERO
    by_category: dict[str, dict[str, Decimal]] = {}
    currency = "EUR"

    for transaction in transactions:
        currency = transaction.currency or currency
        amount = _money(transaction.amount)
        category = transaction.category
        bucket = by_category.setdefault(
            category,
            {
                "income_total": ZERO,
                "expense_total": ZERO,
                "correction_total": ZERO,
            },
        )

        if transaction.transaction_type == "income":
            income_total += amount
            bucket["income_total"] += amount
        elif transaction.transaction_type == "expense":
            expense_total += amount
            bucket["expense_total"] += amount
        elif transaction.transaction_type == "correction":
            correction_total += amount
            bucket["correction_total"] += amount

    income_total = _money(income_total)
    expense_total = _money(expense_total)
    correction_total = _money(correction_total)
    net_total = _money(income_total - expense_total + correction_total)

    categories = []
    for category, totals in sorted(by_category.items()):
        category_income = _money(totals["income_total"])
        category_expense = _money(totals["expense_total"])
        category_correction = _money(totals["correction_total"])
        category_net = _money(category_income - category_expense + category_correction)
        categories.append(
            WeeklyReportVaultCategory(
                category=category,
                income_total=_money_str(category_income),
                expense_total=_money_str(category_expense),
                correction_total=_money_str(category_correction),
                net_total=_money_str(category_net),
            )
        )

    return WeeklyReportVault(
        income_total=_money_str(income_total),
        expense_total=_money_str(expense_total),
        net_total=_money_str(net_total),
        currency=currency,
        by_category=categories,
    )


def _build_signals(
    *,
    days: WeeklyReportDays,
    path: WeeklyReportPath,
    vault: WeeklyReportVault,
    transaction_count: int,
) -> WeeklyReportSignals:
    fatigue_signal = _fatigue_signal(days.average_fatigue_level)
    financial_signal = _financial_signal(vault.net_total, transaction_count)
    discipline_signal = _discipline_signal(path, days)

    return WeeklyReportSignals(
        discipline_signal=discipline_signal,
        fatigue_signal=fatigue_signal,
        financial_signal=financial_signal,
        execution_summary=(
            f"{days.reviewed_days}/7 days reviewed, "
            f"{path.completed}/{path.total_items} path items completed, "
            f"net {vault.net_total} {vault.currency}."
        ),
    )


def _fatigue_signal(average_fatigue: Decimal | None) -> str:
    if average_fatigue is None:
        return "unknown"
    if average_fatigue >= Decimal("7"):
        return "high"
    if average_fatigue >= Decimal("4"):
        return "medium"
    return "low"


def _financial_signal(net_total: str, transaction_count: int) -> str:
    if transaction_count == 0:
        return "unknown"
    net = Decimal(net_total)
    if net > ZERO:
        return "positive"
    if net < ZERO:
        return "negative"
    return "neutral"


def _discipline_signal(path: WeeklyReportPath, days: WeeklyReportDays) -> str:
    if path.total_items == 0 and days.reviewed_days == 0:
        return "unknown"
    if (path.completion_rate is not None and path.completion_rate >= Decimal("80")) or days.completed_days >= 5:
        return "strong"
    if (path.completion_rate is not None and path.completion_rate >= Decimal("50")) or days.reviewed_days >= 3:
        return "medium"
    return "weak"


def _average(values: list[int | None]) -> Decimal | None:
    filtered = [Decimal(value) for value in values if value is not None]
    if not filtered:
        return None
    return _round2(sum(filtered) / Decimal(len(filtered)))


def _round2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _money(value: Decimal) -> Decimal:
    return _round2(value)


def _money_str(value: Decimal) -> str:
    return f"{_money(value):.2f}"
