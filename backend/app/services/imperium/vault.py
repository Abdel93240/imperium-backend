from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.vault import ImperiumVaultTransaction
from app.schemas.imperium import ImperiumVaultSummaryResponse


def get_vault_summary(
    db: Session,
    *,
    current_user: User,
    currency: str = "EUR",
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
) -> ImperiumVaultSummaryResponse:
    normalized_currency = currency.strip().upper()
    query = select(ImperiumVaultTransaction).where(
        ImperiumVaultTransaction.user_id == current_user.id,
        ImperiumVaultTransaction.currency == normalized_currency,
    )
    if occurred_from is not None:
        query = query.where(ImperiumVaultTransaction.occurred_at >= occurred_from)
    if occurred_to is not None:
        query = query.where(ImperiumVaultTransaction.occurred_at <= occurred_to)

    transactions = [
        transaction
        for transaction in db.scalars(query)
        if transaction.user_id == current_user.id
        and transaction.currency == normalized_currency
        and (occurred_from is None or transaction.occurred_at >= occurred_from)
        and (occurred_to is None or transaction.occurred_at <= occurred_to)
    ]

    income_count = sum(1 for transaction in transactions if transaction.transaction_type == "income")
    expense_count = sum(1 for transaction in transactions if transaction.transaction_type == "expense")
    total_income_cents = sum(
        transaction.amount_cents for transaction in transactions if transaction.transaction_type == "income"
    )
    total_expense_cents = sum(
        transaction.amount_cents for transaction in transactions if transaction.transaction_type == "expense"
    )

    return ImperiumVaultSummaryResponse(
        currency=normalized_currency,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        total_income_cents=total_income_cents,
        total_expense_cents=total_expense_cents,
        net_cents=total_income_cents - total_expense_cents,
        transaction_count=len(transactions),
        income_count=income_count,
        expense_count=expense_count,
    )
