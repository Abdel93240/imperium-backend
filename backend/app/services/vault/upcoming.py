from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.vault import ImperiumVaultTransaction, UpcomingExpense
from app.services.notifications import notify


def list_upcoming_expenses(db: Session, *, active: bool | None = True) -> list[UpcomingExpense]:
    query = select(UpcomingExpense).order_by(UpcomingExpense.due_date, UpcomingExpense.label_fr)
    if active is not None:
        query = query.where(UpcomingExpense.active.is_(active))
    return list(db.scalars(query))


def create_upcoming_expense(db: Session, *, payload) -> UpcomingExpense:
    expense = UpcomingExpense(**payload.model_dump(exclude_unset=True))
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


def update_upcoming_expense(db: Session, *, expense_id: UUID, payload) -> UpcomingExpense | None:
    expense = db.get(UpcomingExpense, expense_id)
    if expense is None:
        return None
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(expense, key, value)
    db.commit()
    db.refresh(expense)
    return expense


def deactivate_upcoming_expense(db: Session, *, expense_id: UUID) -> UpcomingExpense | None:
    expense = db.get(UpcomingExpense, expense_id)
    if expense is None:
        return None
    expense.active = False
    db.commit()
    db.refresh(expense)
    return expense


def next_due_date(due_date: date, recurrence: str | None) -> date | None:
    if recurrence is None:
        return None
    if recurrence == "monthly":
        return _add_months(due_date, 1)
    if recurrence == "quarterly":
        return _add_months(due_date, 3)
    if recurrence == "yearly":
        return _add_months(due_date, 12)
    raise ValueError(f"Unknown recurrence '{recurrence}'.")


def ensure_next_occurrence(db: Session, *, expense: UpcomingExpense) -> UpcomingExpense | None:
    next_date = next_due_date(expense.due_date, expense.recurrence)
    if next_date is None:
        return None
    existing = db.scalar(
        select(UpcomingExpense).where(
            UpcomingExpense.label_fr == expense.label_fr,
            UpcomingExpense.amount == expense.amount,
            UpcomingExpense.category == expense.category,
            UpcomingExpense.wallet == expense.wallet,
            UpcomingExpense.due_date == next_date,
        )
    )
    if existing is not None:
        return existing
    generated = UpcomingExpense(
        label_fr=expense.label_fr,
        amount=expense.amount,
        due_date=next_date,
        recurrence=expense.recurrence,
        category=expense.category,
        wallet=expense.wallet,
        mandatory=expense.mandatory,
        active=expense.active,
    )
    db.add(generated)
    db.flush()
    return generated


def expenses_horizon_job(ctx, window) -> None:
    today = (window.to_ts.date() if window.to_ts is not None else date.today())
    expenses = list(
        ctx.db.scalars(
            select(UpcomingExpense).where(
                UpcomingExpense.active.is_(True),
                or_(
                    UpcomingExpense.due_date.in_(
                        [today + timedelta(days=7), today + timedelta(days=1)]
                    ),
                    UpcomingExpense.due_date < today,
                ),
            )
        )
    )
    balances = _wallet_balances(ctx.db)
    sent = 0
    generated = 0
    for expense in expenses:
        days_left = (expense.due_date - today).days
        if days_left == 7:
            if notify(
                ctx.db,
                severity="normal",
                domain="vault",
                message_fr=f"Échéance à J-7 : {expense.label_fr} ({expense.amount} EUR).",
                ref=("upcoming_expense", expense.id),
            ) is not None:
                sent += 1
        elif days_left == 1:
            wallet = expense.wallet or "cash"
            severity = "red" if balances.get(wallet, Decimal("0.00")) < Decimal(expense.amount) else "normal"
            if notify(
                ctx.db,
                severity=severity,
                domain="vault",
                message_fr=f"Échéance demain : {expense.label_fr} ({expense.amount} EUR).",
                ref=("upcoming_expense", expense.id),
            ) is not None:
                sent += 1
        if expense.due_date < today and expense.recurrence is not None:
            if ensure_next_occurrence(ctx.db, expense=expense) is not None:
                generated += 1
    ctx.items_in = len(expenses)
    ctx.items_out = sent + generated
    ctx.detail = {"notifications": sent, "generated_occurrences": generated}
    if window.to_ts is not None:
        ctx.cursor_ts = window.to_ts


def _wallet_balances(db: Session) -> dict[str, Decimal]:
    balances: dict[str, Decimal] = {}
    transactions = list(db.scalars(select(ImperiumVaultTransaction)))
    for transaction in transactions:
        amount = Decimal(transaction.amount_cents) / Decimal("100")
        if transaction.transaction_type == "expense":
            amount = -amount
        balances.setdefault(transaction.wallet, Decimal("0.00"))
        balances[transaction.wallet] += amount
    return balances


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)
