from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransactionType(StrEnum):
    income = "income"
    expense = "expense"
    correction = "correction"


class WalletType(StrEnum):
    cash = "cash"
    bank = "bank"


class CreateVaultTransactionRequest(BaseModel):
    occurred_at: datetime
    local_date: date
    timezone: str = Field(min_length=1)
    transaction_type: TransactionType
    wallet: WalletType
    category: str = Field(min_length=1, max_length=120)
    label: str | None = Field(default=None, max_length=200)
    amount: Decimal = Field(gt=Decimal("0"), max_digits=12, decimal_places=2)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    notes: str | None = None

    @field_validator("timezone", "category", "label", "currency", "notes")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        return stripped

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class VaultTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    occurred_at: datetime
    local_date: date
    timezone: str
    transaction_type: str
    wallet: str
    category: str
    label: str | None
    amount: Decimal
    currency: str
    notes: str | None
    created_at: datetime
    event_id: UUID | None = None
    idempotency_key: str | None = None


class VaultTransactionWriteResponse(BaseModel):
    transaction: VaultTransactionResponse
    event_id: str
    idempotency_key: str
    status: str


class VaultWeeklySummaryResponse(BaseModel):
    week_start: date
    week_end: date
    income_total: Decimal
    expense_total: Decimal
    correction_total: Decimal
    net_total: Decimal
    by_wallet: dict[str, dict[str, Decimal]]
    by_category: dict[str, dict[str, Decimal]]
