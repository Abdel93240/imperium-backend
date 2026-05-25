from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
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


class ImperiumVaultTransactionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_type: Literal["income", "expense"]
    amount_cents: int = Field(gt=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    occurred_at: datetime
    category: str | None = Field(default=None, max_length=80)
    source: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=500)
    external_ref: str | None = Field(default=None, max_length=120)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> str:
        if value is None:
            return "EUR"
        if not isinstance(value, str):
            raise ValueError("currency must be a string.")
        return value.strip().upper()

    @field_validator("occurred_at")
    @classmethod
    def require_timezone_aware_occurred_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include timezone information.")
        return value

    @field_validator("category", "source", "note", "external_ref")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        return stripped


class ImperiumVaultTransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    transaction_type: Literal["income", "expense"]
    amount_cents: int
    currency: str
    occurred_at: datetime
    category: str | None
    source: str | None
    note: str | None
    external_ref: str | None
    is_reversal: bool = False
    reversal_of_transaction_id: UUID | None = None
    reversal_reason: str | None = None
    created_at: datetime

    @field_validator("is_reversal", mode="before")
    @classmethod
    def default_is_reversal(cls, value: bool | None) -> bool:
        return False if value is None else value


class ImperiumVaultTransactionListResponse(BaseModel):
    items: list[ImperiumVaultTransactionRead]
    count: int
    limit: int
    offset: int
    safe_explanation: str = "Vault transactions for current user."


class ImperiumVaultTransactionReverseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("reason cannot be empty.")
        return stripped


class ImperiumVaultTransactionReversalSummary(BaseModel):
    status: Literal["reversed"]
    original_transaction_id: UUID
    guardrails_checked: list[str]
    safe_explanation: str = "Transaction reversed by appending an opposite ledger transaction."


class ImperiumVaultTransactionReverseResponse(BaseModel):
    transaction: ImperiumVaultTransactionRead
    reversal_summary: ImperiumVaultTransactionReversalSummary
