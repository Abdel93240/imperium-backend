from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.vault import ImperiumVaultTransaction, WeeklyFinanceSummary
from app.services.events.emitter import build_event
from app.services.params import get_parameter

ZERO = Decimal("0.00")
MONEY = Decimal("0.01")
DEFAULT_CATEGORY_MAP = {
    "business_income": ["vtc", "bolt", "uber", "heetch", "autre pro", "other_professional"],
    "personal_income": ["rsa", "gift", "salaire", "side income", "leboncoin"],
    "business_expenses": [
        "fuel",
        "carburant",
        "plateformes",
        "entretien",
        "maintenance",
        "assurance pro",
        "outils vtc",
        "charges",
        "urssaf",
        "tax",
        "provision impôt",
    ],
    "personal_expenses": [
        "courses",
        "loyer",
        "restaurant",
        "loisirs",
        "vêtements",
        "telephone",
        "téléphone",
        "santé",
        "abonnements",
        "sadaqa",
    ],
}


def compute_weekly_finance_summary(
    db: Session,
    *,
    week_start: date,
    current_user: User,
    computed_at: datetime | None = None,
    emit_event: bool = True,
) -> WeeklyFinanceSummary:
    if week_start.weekday() != 0:
        raise ValueError("week_start must be a Monday.")
    computed_at = computed_at or datetime.now(UTC)
    week_end = week_start + timedelta(days=6)
    query = select(ImperiumVaultTransaction).where(
        ImperiumVaultTransaction.user_id == current_user.id,
        ImperiumVaultTransaction.local_date >= week_start,
        ImperiumVaultTransaction.local_date <= week_end,
        ImperiumVaultTransaction.currency == "EUR",
    )
    transactions = list(db.scalars(query))
    data = build_weekly_summary_detail(transactions, category_map=_category_map(db))

    summary = db.get(WeeklyFinanceSummary, (current_user.id, week_start))
    if summary is None:
        summary = WeeklyFinanceSummary(user_id=current_user.id, week_start=week_start, **data, computed_at=computed_at)
        db.add(summary)
    else:
        summary.business_revenue = data["business_revenue"]
        summary.business_expenses = data["business_expenses"]
        summary.weekly_business_profit = data["weekly_business_profit"]
        summary.personal_expenses = data["personal_expenses"]
        summary.detail = data["detail"]
        summary.computed_at = computed_at
    db.flush()

    if emit_event:
        db.add(
            build_event(
                db,
                user_id=current_user.id,
                event_type="finance.weekly_summary.created",
                payload={
                    "week_start": week_start.isoformat(),
                    "weekly_business_profit": str(summary.weekly_business_profit),
                },
                idempotency_key=f"vault.weekly_profit.{week_start.isoformat()}.{computed_at.isoformat()}",
                source_app=SourceApp.vault,
                privacy_level=PrivacyLevel.high,
            )
        )
    db.commit()
    return summary


def build_weekly_summary_detail(
    transactions: list[ImperiumVaultTransaction], *, category_map: dict
) -> dict:
    business_income_categories = _set(category_map, "business_income")
    personal_income_categories = _set(category_map, "personal_income")
    business_expense_categories = _set(category_map, "business_expenses")

    business_revenue = ZERO
    business_expenses = ZERO
    personal_expenses = ZERO
    by_category: dict[str, dict[str, str]] = {}
    by_wallet: dict[str, dict[str, str]] = {}

    for transaction in transactions:
        amount = _money(Decimal(transaction.amount_cents) / Decimal("100"))
        category = _normalize(transaction.category)
        wallet = transaction.wallet or "cash"
        book = _book_for_transaction(
            transaction.transaction_type,
            category,
            business_income_categories,
            personal_income_categories,
            business_expense_categories,
        )
        if transaction.transaction_type == "income" and book == "business":
            business_revenue += amount
        elif transaction.transaction_type == "expense" and book == "business":
            business_expenses += amount
        elif transaction.transaction_type == "expense" and book == "personal":
            personal_expenses += amount

        _add_detail(by_category, category, transaction.transaction_type, book, amount)
        _add_detail(by_wallet, wallet, transaction.transaction_type, book, amount)

    business_revenue = _money(business_revenue)
    business_expenses = _money(business_expenses)
    personal_expenses = _money(personal_expenses)
    return {
        "business_revenue": business_revenue,
        "business_expenses": business_expenses,
        "weekly_business_profit": _money(business_revenue - business_expenses),
        "personal_expenses": personal_expenses,
        "detail": {"by_category": by_category, "by_wallet": by_wallet},
    }


def backfill_weekly_finance_summaries(db: Session, *, current_user: User) -> list[WeeklyFinanceSummary]:
    query = select(func.min(ImperiumVaultTransaction.local_date), func.max(ImperiumVaultTransaction.local_date)).where(
        ImperiumVaultTransaction.user_id == current_user.id
    )
    start, end = db.execute(query).one()
    if start is None or end is None:
        return []
    week = start - timedelta(days=start.weekday())
    last_week = end - timedelta(days=end.weekday())
    summaries: list[WeeklyFinanceSummary] = []
    while week <= last_week:
        summaries.append(
            compute_weekly_finance_summary(
                db, week_start=week, current_user=current_user, emit_event=False
            )
        )
        week += timedelta(days=7)
    return summaries


def list_weekly_summaries(db: Session, *, current_user: User, from_date: date | None = None) -> list[WeeklyFinanceSummary]:
    query = (
        select(WeeklyFinanceSummary)
        .where(WeeklyFinanceSummary.user_id == current_user.id)
        .order_by(WeeklyFinanceSummary.week_start.desc())
    )
    if from_date is not None:
        query = query.where(WeeklyFinanceSummary.week_start >= from_date)
    return list(db.scalars(query))


def weekly_profit_job(ctx, window) -> None:
    user = _job_user(ctx.db)
    if user is None:
        ctx.items_in = 0
        ctx.items_out = 0
        ctx.detail = {"skip": "no_user"}
        if window.to_ts is not None:
            ctx.cursor_ts = window.to_ts
        return
    now = window.to_ts or datetime.now(UTC)
    this_monday = now.date() - timedelta(days=now.date().weekday())
    closed_week = this_monday - timedelta(days=7)
    summary = compute_weekly_finance_summary(
        ctx.db, week_start=closed_week, current_user=user, computed_at=now
    )
    ctx.items_in = 1
    ctx.items_out = 1
    ctx.detail = {
        "week_start": summary.week_start.isoformat(),
        "weekly_business_profit": str(summary.weekly_business_profit),
    }
    if window.to_ts is not None:
        ctx.cursor_ts = window.to_ts


def _category_map(db: Session) -> dict:
    value = get_parameter(db, "vault.category_map", default=DEFAULT_CATEGORY_MAP)
    if not isinstance(value, dict):
        return DEFAULT_CATEGORY_MAP
    return value


def _set(category_map: dict, key: str) -> set[str]:
    return {_normalize(value) for value in category_map.get(key, DEFAULT_CATEGORY_MAP.get(key, []))}


def _book_for_transaction(
    transaction_type: str,
    category: str,
    business_income: set[str],
    personal_income: set[str],
    business_expenses: set[str],
) -> str:
    if transaction_type == "income":
        if category in personal_income:
            return "personal"
        if category in business_income:
            return "business"
        return "business"
    if category in business_expenses:
        return "business"
    return "personal"


def _add_detail(
    target: dict[str, dict[str, str]], key: str, transaction_type: str, book: str, amount: Decimal
) -> None:
    bucket = target.setdefault(
        key,
        {
            "business_income": "0.00",
            "business_expenses": "0.00",
            "personal_expenses": "0.00",
        },
    )
    if transaction_type == "income" and book == "business":
        field = "business_income"
    elif transaction_type == "expense" and book == "business":
        field = "business_expenses"
    elif transaction_type == "expense":
        field = "personal_expenses"
    else:
        return
    bucket[field] = str(_money(Decimal(bucket[field]) + amount))


def _normalize(value: str | None) -> str:
    if value is None:
        return "uncategorized"
    stripped = value.strip().lower()
    return stripped or "uncategorized"


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def _job_user(db: Session) -> User | None:
    settings = get_settings()
    if settings.imperium_canonical_user_id is not None:
        user = db.get(User, settings.imperium_canonical_user_id)
        if user is not None:
            return user
    return db.scalar(select(User).order_by(User.created_at).limit(1))
