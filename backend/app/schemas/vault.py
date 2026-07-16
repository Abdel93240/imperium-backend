from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ImperiumVaultTransactionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_type: Literal["income", "expense"]
    amount_cents: int = Field(gt=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    wallet: str = Field(default="cash", min_length=1, max_length=80)
    occurred_at: datetime
    timezone: str | None = Field(default=None, min_length=1, max_length=80)
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

    @field_validator("wallet", "timezone", "category", "source", "note", "external_ref")
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
    wallet: str = "cash"
    occurred_at: datetime
    local_date: date
    timezone: str
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

    @field_validator("wallet", mode="before")
    @classmethod
    def default_wallet(cls, value: str | None) -> str:
        return "cash" if value is None else value


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


class VaultDailyTargets(BaseModel):
    minimum: Decimal
    comfortable: Decimal
    optimal: Decimal


class VaultPressureResponse(BaseModel):
    score: int = Field(ge=0, le=100)
    label: Literal["safe", "stable", "attention", "pressure", "critical"]
    daily_targets: VaultDailyTargets
    computed_at: datetime


class VaultPressureExplainResponse(BaseModel):
    score: int = Field(ge=0, le=100)
    label: Literal["safe", "stable", "attention", "pressure", "critical"]
    factors: dict
    daily_targets: dict
    inputs_snapshot: dict
    computed_at: datetime


class VaultPressureHistoryItem(BaseModel):
    id: UUID
    computed_at: datetime
    score: int
    label: str
    daily_targets: dict


class UpcomingExpenseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label_fr: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(gt=Decimal("0"), max_digits=12, decimal_places=2)
    due_date: date
    recurrence: Literal["monthly", "quarterly", "yearly"] | None = None
    category: str = Field(min_length=1, max_length=120)
    wallet: str | None = Field(default=None, max_length=80)
    mandatory: bool = True
    active: bool = True

    @field_validator("label_fr", "category", "wallet")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        return stripped


class UpcomingExpenseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label_fr: str | None = Field(default=None, min_length=1, max_length=200)
    amount: Decimal | None = Field(default=None, gt=Decimal("0"), max_digits=12, decimal_places=2)
    due_date: date | None = None
    recurrence: Literal["monthly", "quarterly", "yearly"] | None = None
    category: str | None = Field(default=None, min_length=1, max_length=120)
    wallet: str | None = Field(default=None, max_length=80)
    mandatory: bool | None = None
    active: bool | None = None

    @field_validator("label_fr", "category", "wallet")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        return stripped


class UpcomingExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    label_fr: str
    amount: Decimal
    due_date: date
    recurrence: str | None
    category: str
    wallet: str | None
    mandatory: bool
    active: bool
    created_at: datetime
    updated_at: datetime


class WeeklyFinanceSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    week_start: date
    business_revenue: Decimal
    business_expenses: Decimal
    weekly_business_profit: Decimal
    personal_expenses: Decimal
    computed_at: datetime
    detail: dict
