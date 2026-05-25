from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.vault import ImperiumVaultTransaction
from app.schemas.imperium import (
    ImperiumVaultCategorySummaryItem,
    ImperiumVaultCategorySummaryResponse,
    ImperiumVaultTransactionDetailResponse,
    ImperiumVaultMonthlySummaryItem,
    ImperiumVaultMonthlySummaryResponse,
    ImperiumVaultSummaryResponse,
)


def _load_filtered_vault_transactions(
    db: Session,
    *,
    current_user: User,
    currency: str,
    occurred_from: datetime | None,
    occurred_to: datetime | None,
    transaction_type: str | None = None,
) -> tuple[str, list[ImperiumVaultTransaction]]:
    normalized_currency = currency.strip().upper()
    query = select(ImperiumVaultTransaction).where(
        ImperiumVaultTransaction.user_id == current_user.id,
        ImperiumVaultTransaction.currency == normalized_currency,
    )
    if occurred_from is not None:
        query = query.where(ImperiumVaultTransaction.occurred_at >= occurred_from)
    if occurred_to is not None:
        query = query.where(ImperiumVaultTransaction.occurred_at <= occurred_to)
    if transaction_type is not None:
        query = query.where(ImperiumVaultTransaction.transaction_type == transaction_type)

    transactions = list(db.scalars(query))
    return normalized_currency, transactions


def get_vault_summary(
    db: Session,
    *,
    current_user: User,
    currency: str = "EUR",
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
) -> ImperiumVaultSummaryResponse:
    normalized_currency, transactions = _load_filtered_vault_transactions(
        db,
        current_user=current_user,
        currency=currency,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
    )

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


def get_vault_monthly_summary(
    db: Session,
    *,
    current_user: User,
    currency: str = "EUR",
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
) -> ImperiumVaultMonthlySummaryResponse:
    normalized_currency, transactions = _load_filtered_vault_transactions(
        db,
        current_user=current_user,
        currency=currency,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
    )

    grouped_transactions: dict[str, list[ImperiumVaultTransaction]] = {}
    for transaction in transactions:
        month = transaction.occurred_at.astimezone(UTC).strftime("%Y-%m")
        grouped_transactions.setdefault(month, []).append(transaction)

    items: list[ImperiumVaultMonthlySummaryItem] = []
    for month, month_transactions in grouped_transactions.items():
        income_count = sum(
            1 for transaction in month_transactions if transaction.transaction_type == "income"
        )
        expense_count = sum(
            1 for transaction in month_transactions if transaction.transaction_type == "expense"
        )
        total_income_cents = sum(
            transaction.amount_cents
            for transaction in month_transactions
            if transaction.transaction_type == "income"
        )
        total_expense_cents = sum(
            transaction.amount_cents
            for transaction in month_transactions
            if transaction.transaction_type == "expense"
        )

        items.append(
            ImperiumVaultMonthlySummaryItem(
                month=month,
                total_income_cents=total_income_cents,
                total_expense_cents=total_expense_cents,
                net_cents=total_income_cents - total_expense_cents,
                transaction_count=len(month_transactions),
                income_count=income_count,
                expense_count=expense_count,
            )
        )

    items = sorted(items, key=lambda item: item.month, reverse=True)

    return ImperiumVaultMonthlySummaryResponse(
        currency=normalized_currency,
        items=items,
        count=len(items),
    )


def get_vault_category_summary(
    db: Session,
    *,
    current_user: User,
    currency: str = "EUR",
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    transaction_type: str | None = None,
) -> ImperiumVaultCategorySummaryResponse:
    normalized_currency, transactions = _load_filtered_vault_transactions(
        db,
        current_user=current_user,
        currency=currency,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        transaction_type=transaction_type,
    )

    grouped_transactions: dict[str, list[ImperiumVaultTransaction]] = {}
    for transaction in transactions:
        category = _normalize_vault_category(transaction.category)
        grouped_transactions.setdefault(category, []).append(transaction)

    items: list[ImperiumVaultCategorySummaryItem] = []
    for category, category_transactions in grouped_transactions.items():
        income_count = sum(
            1 for transaction in category_transactions if transaction.transaction_type == "income"
        )
        expense_count = sum(
            1 for transaction in category_transactions if transaction.transaction_type == "expense"
        )
        total_income_cents = sum(
            transaction.amount_cents
            for transaction in category_transactions
            if transaction.transaction_type == "income"
        )
        total_expense_cents = sum(
            transaction.amount_cents
            for transaction in category_transactions
            if transaction.transaction_type == "expense"
        )

        items.append(
            ImperiumVaultCategorySummaryItem(
                category=category,
                total_income_cents=total_income_cents,
                total_expense_cents=total_expense_cents,
                net_cents=total_income_cents - total_expense_cents,
                transaction_count=len(category_transactions),
                income_count=income_count,
                expense_count=expense_count,
            )
        )
    items = sorted(
        items,
        key=lambda item: (-item.transaction_count, -abs(item.net_cents), item.category),
    )

    return ImperiumVaultCategorySummaryResponse(
        currency=normalized_currency,
        items=items,
        count=len(items),
    )


def _normalize_vault_category(category: str | None) -> str:
    if category is None:
        return "uncategorized"
    stripped = category.strip()
    if not stripped:
        return "uncategorized"
    return stripped


def get_vault_transaction_detail(
    db: Session,
    *,
    current_user: User,
    transaction_id: UUID,
) -> ImperiumVaultTransactionDetailResponse | None:
    transaction = db.scalar(
        select(ImperiumVaultTransaction).where(
            ImperiumVaultTransaction.id == transaction_id,
            ImperiumVaultTransaction.user_id == current_user.id,
        )
    )
    if transaction is None:
        return None
    return ImperiumVaultTransactionDetailResponse(transaction=transaction)
