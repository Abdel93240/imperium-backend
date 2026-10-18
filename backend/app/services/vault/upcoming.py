from __future__ import annotations

from calendar import monthrange
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.vault import ImperiumVaultTransaction, UpcomingExpense
from app.schemas.vault import (
    ImperiumVaultTransactionCreate,
    ImperiumVaultTransactionRead,
    UpcomingExpensePayResult,
    UpcomingExpenseRead,
)
from app.services.imperium.vault_transactions import create_vault_transaction
from app.services.notifications import notify


def list_upcoming_expenses(db: Session, *, current_user: User, active: bool | None = True) -> list[UpcomingExpense]:
    query = (
        select(UpcomingExpense)
        .where(UpcomingExpense.user_id == current_user.id)
        .order_by(UpcomingExpense.due_date, UpcomingExpense.label_fr)
    )
    if active is not None:
        query = query.where(UpcomingExpense.active.is_(active))
    return list(db.scalars(query))


def create_upcoming_expense(db: Session, *, current_user: User, payload) -> UpcomingExpense:
    expense = UpcomingExpense(user_id=current_user.id, **payload.model_dump(exclude_unset=True))
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


def update_upcoming_expense(db: Session, *, current_user: User, expense_id: UUID, payload) -> UpcomingExpense | None:
    expense = db.scalar(
        select(UpcomingExpense).where(
            UpcomingExpense.id == expense_id,
            UpcomingExpense.user_id == current_user.id,
        )
    )
    if expense is None:
        return None
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(expense, key, value)
    db.commit()
    db.refresh(expense)
    return expense


def deactivate_upcoming_expense(db: Session, *, current_user: User, expense_id: UUID) -> UpcomingExpense | None:
    expense = db.scalar(
        select(UpcomingExpense).where(
            UpcomingExpense.id == expense_id,
            UpcomingExpense.user_id == current_user.id,
        )
    )
    if expense is None:
        return None
    expense.active = False
    db.commit()
    db.refresh(expense)
    return expense


class UpcomingExpenseNotFoundError(ValueError):
    pass


class UpcomingExpenseStateError(ValueError):
    pass


def mark_paid(
    db: Session, *, current_user: User, expense_id: UUID, payload, idempotency_key: str, request_path: str,
):
    """VAU-11 : écrit la dépense au Vault, clôt l'échéance, crée la suivante si elle se répète."""
    expense = db.scalar(
        select(UpcomingExpense).where(UpcomingExpense.id == expense_id, UpcomingExpense.user_id == current_user.id)
        .with_for_update()
    )
    if expense is None:
        raise UpcomingExpenseNotFoundError("Upcoming expense not found.")
    if expense.paid_transaction_id is not None:
        transaction = db.get(ImperiumVaultTransaction, expense.paid_transaction_id)
        if transaction is not None and transaction.external_ref == f"upcoming:{expense.id}:{idempotency_key[:80]}":
            return _pay_result(db, expense, transaction)
        raise UpcomingExpenseStateError("Cette échéance est déjà payée.")
    if not expense.active:
        raise UpcomingExpenseStateError("Cette échéance n'est plus active.")
    paid_at = payload.paid_at or datetime.now(UTC)
    amount_cents = payload.amount_cents or int((Decimal(expense.amount) * 100).to_integral_value())
    transaction, _ = create_vault_transaction(
        db, current_user=current_user,
        payload=ImperiumVaultTransactionCreate(
            transaction_type="expense", amount_cents=amount_cents, wallet=payload.wallet or expense.wallet or "cash",
            occurred_at=paid_at, timezone="Europe/Paris", category=expense.category, source="upcoming_expense",
            note=expense.label_fr[:500], external_ref=f"upcoming:{expense.id}:{idempotency_key[:80]}",
        ),
        idempotency_key=idempotency_key, request_method="POST", request_path=request_path,
    )
    expense = db.get(UpcomingExpense, expense_id)
    expense.paid_at, expense.paid_transaction_id, expense.active = paid_at, transaction.id, False
    ensure_next_occurrence(db, expense=_still_active(expense))
    db.commit()
    db.refresh(expense)
    return _pay_result(db, expense, db.get(ImperiumVaultTransaction, transaction.id))


def _still_active(expense: UpcomingExpense) -> UpcomingExpense:
    """Modèle non enregistré : la prochaine échéance naît active, même si celle-ci vient d'être close."""
    return UpcomingExpense(
        user_id=expense.user_id, label_fr=expense.label_fr, amount=expense.amount, due_date=expense.due_date,
        recurrence=expense.recurrence, category=expense.category, wallet=expense.wallet, mandatory=expense.mandatory,
        active=True,
    )


def _pay_result(db: Session, expense: UpcomingExpense, transaction: ImperiumVaultTransaction) -> UpcomingExpensePayResult:
    following = None
    next_date = next_due_date(expense.due_date, expense.recurrence)
    if next_date is not None:
        following = db.scalar(
            select(UpcomingExpense).where(
                UpcomingExpense.user_id == expense.user_id, UpcomingExpense.label_fr == expense.label_fr,
                UpcomingExpense.due_date == next_date, UpcomingExpense.category == expense.category,
            )
        )
    return UpcomingExpensePayResult(
        expense=UpcomingExpenseRead.model_validate(expense), transaction=ImperiumVaultTransactionRead.model_validate(transaction),
        next_occurrence=UpcomingExpenseRead.model_validate(following) if following else None,
    )


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
            UpcomingExpense.user_id == expense.user_id,
            UpcomingExpense.amount == expense.amount,
            UpcomingExpense.category == expense.category,
            UpcomingExpense.wallet == expense.wallet,
            UpcomingExpense.due_date == next_date,
        )
    )
    if existing is not None:
        return existing
    generated = UpcomingExpense(
        user_id=expense.user_id,
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
    user = _job_user(ctx.db)
    if user is None:
        ctx.items_in = 0
        ctx.items_out = 0
        ctx.detail = {"skip": "no_user"}
        if window.to_ts is not None:
            ctx.cursor_ts = window.to_ts
        return
    today = (window.to_ts.date() if window.to_ts is not None else date.today())
    expenses = list(
        ctx.db.scalars(
            select(UpcomingExpense).where(
                UpcomingExpense.user_id == user.id,
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
    balances = _wallet_balances(ctx.db, current_user=user)
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


def _wallet_balances(db: Session, *, current_user: User) -> dict[str, Decimal]:
    balances: dict[str, Decimal] = {}
    transactions = list(
        db.scalars(select(ImperiumVaultTransaction).where(ImperiumVaultTransaction.user_id == current_user.id))
    )
    for transaction in transactions:
        amount = Decimal(transaction.amount_cents) / Decimal("100")
        if transaction.transaction_type == "expense":
            amount = -amount
        balances.setdefault(transaction.wallet, Decimal("0.00"))
        balances[transaction.wallet] += amount
    return balances


def _job_user(db: Session) -> User | None:
    from app.core.config import get_settings

    settings = get_settings()
    if settings.imperium_canonical_user_id is not None:
        user = db.get(User, settings.imperium_canonical_user_id)
        if user is not None:
            return user
    return db.scalar(select(User).order_by(User.created_at).limit(1))


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)
