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
)
from app.services.imperium.dashboard import CANONICAL_PRIORITY_LABELS
from app.services.imperium.decision_framework import get_canonical_priority_order
from app.services.path.canonical import path_week_stats
from app.models.vault import ImperiumVaultTransaction
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
    WeeklyReportVaultWallet,
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
    # C-1 (passe 0): canonical Path source = habits/check-ins.
    path_stats = path_week_stats(
        db, current_user=current_user, week_start=week_start, week_end_exclusive=week_end_exclusive
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
            select(ImperiumVaultTransaction).where(
                ImperiumVaultTransaction.user_id == current_user.id,
                ImperiumVaultTransaction.local_date >= week_start,
                ImperiumVaultTransaction.local_date < week_end_exclusive,
            )
        )
    )
    # C-1 (passe 0): canonical priorities = imperium_user_priorities.
    priorities = get_canonical_priority_order(db, current_user=current_user)

    days = _build_days(day_reviews)
    path = _build_path(path_stats)
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
                rank_order=priority.position,
                priority_key=priority.domain,
                label=CANONICAL_PRIORITY_LABELS.get(
                    priority.domain, priority.domain.replace("_", " ").title()
                ),
                importance_score=None,
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


def _build_path(path_stats: dict[str, int]) -> WeeklyReportPath:
    total = path_stats["total_items"]
    completed = path_stats["completed"]
    completion_rate = None if total == 0 else _round2(Decimal(completed) / Decimal(total) * Decimal("100"))
    return WeeklyReportPath(
        total_items=total,
        planned=path_stats["planned"],
        in_progress=path_stats["in_progress"],
        completed=completed,
        skipped=path_stats["skipped"],
        cancelled=path_stats["cancelled"],
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


def _build_vault(transactions: list[ImperiumVaultTransaction]) -> WeeklyReportVault:
    income_total = ZERO
    expense_total = ZERO
    reversal_total = ZERO
    reversal_count = 0
    by_category: dict[str, dict[str, Decimal | int]] = {}
    by_wallet: dict[str, dict[str, Decimal | int]] = {}
    currency = "EUR"

    for transaction in transactions:
        currency = transaction.currency or currency
        amount = _cents_to_money(transaction.amount_cents)
        category = _label_or_uncategorized(transaction.category)
        wallet = _label_or_default(transaction.wallet, "cash")
        category_bucket = _summary_bucket(by_category, category)
        wallet_bucket = _summary_bucket(by_wallet, wallet)
        category_bucket["transaction_count"] = int(category_bucket["transaction_count"]) + 1
        wallet_bucket["transaction_count"] = int(wallet_bucket["transaction_count"]) + 1
        if transaction.transaction_type == "income":
            income_total += amount
            category_bucket["income_total"] = Decimal(category_bucket["income_total"]) + amount
            wallet_bucket["income_total"] = Decimal(wallet_bucket["income_total"]) + amount
            category_bucket["income_count"] = int(category_bucket["income_count"]) + 1
            wallet_bucket["income_count"] = int(wallet_bucket["income_count"]) + 1
        elif transaction.transaction_type == "expense":
            expense_total += amount
            category_bucket["expense_total"] = Decimal(category_bucket["expense_total"]) + amount
            wallet_bucket["expense_total"] = Decimal(wallet_bucket["expense_total"]) + amount
            category_bucket["expense_count"] = int(category_bucket["expense_count"]) + 1
            wallet_bucket["expense_count"] = int(wallet_bucket["expense_count"]) + 1
        if transaction.is_reversal:
            reversal_total += amount
            reversal_count += 1
            category_bucket["reversal_total"] = Decimal(category_bucket["reversal_total"]) + amount
            category_bucket["reversal_count"] = int(category_bucket["reversal_count"]) + 1
            wallet_bucket["reversal_total"] = Decimal(wallet_bucket["reversal_total"]) + amount
            wallet_bucket["reversal_count"] = int(wallet_bucket["reversal_count"]) + 1

    income_total = _money(income_total)
    expense_total = _money(expense_total)
    reversal_total = _money(reversal_total)
    net_total = _money(income_total - expense_total)

    categories = []
    for category, totals in sorted(by_category.items()):
        category_income = _money(Decimal(totals["income_total"]))
        category_expense = _money(Decimal(totals["expense_total"]))
        category_reversal = _money(Decimal(totals["reversal_total"]))
        category_net = _money(category_income - category_expense)
        categories.append(
            WeeklyReportVaultCategory(
                category=category,
                income_total=_money_str(category_income),
                expense_total=_money_str(category_expense),
                reversal_total=_money_str(category_reversal),
                reversal_count=int(totals["reversal_count"]),
                transaction_count=int(totals["transaction_count"]),
                income_count=int(totals["income_count"]),
                expense_count=int(totals["expense_count"]),
                net_total=_money_str(category_net),
            )
        )

    wallets = []
    for wallet, totals in sorted(by_wallet.items()):
        wallet_income = _money(Decimal(totals["income_total"]))
        wallet_expense = _money(Decimal(totals["expense_total"]))
        wallet_reversal = _money(Decimal(totals["reversal_total"]))
        wallet_net = _money(wallet_income - wallet_expense)
        wallets.append(
            WeeklyReportVaultWallet(
                wallet=wallet,
                income_total=_money_str(wallet_income),
                expense_total=_money_str(wallet_expense),
                reversal_total=_money_str(wallet_reversal),
                reversal_count=int(totals["reversal_count"]),
                transaction_count=int(totals["transaction_count"]),
                income_count=int(totals["income_count"]),
                expense_count=int(totals["expense_count"]),
                net_total=_money_str(wallet_net),
            )
        )

    return WeeklyReportVault(
        income_total=_money_str(income_total),
        expense_total=_money_str(expense_total),
        reversal_total=_money_str(reversal_total),
        reversal_count=reversal_count,
        net_total=_money_str(net_total),
        currency=currency,
        by_category=categories,
        by_wallet=wallets,
    )


def _summary_bucket(
    summary: dict[str, dict[str, Decimal | int]],
    key: str,
) -> dict[str, Decimal | int]:
    return summary.setdefault(
        key,
        {
            "income_total": ZERO,
            "expense_total": ZERO,
            "reversal_total": ZERO,
            "reversal_count": 0,
            "transaction_count": 0,
            "income_count": 0,
            "expense_count": 0,
        },
    )


def _cents_to_money(amount_cents: int) -> Decimal:
    return _money(Decimal(amount_cents) / Decimal("100"))


def _label_or_uncategorized(value: str | None) -> str:
    return _label_or_default(value, "uncategorized")


def _label_or_default(value: str | None, default: str) -> str:
    if value is None:
        return default
    stripped = value.strip()
    return stripped or default


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
