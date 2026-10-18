from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.pulse import FoodStockItemRead, FoodStockLineIn


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
    paid_at: datetime | None = None
    paid_transaction_id: UUID | None = None
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


# ---------- Catégorie suggérée (doc 42 §7.0–§7.2) ----------

class VaultCategoryRead(BaseModel):
    category: str
    book: Literal["business", "personal"]
    kind: Literal["income", "expense"]


class VaultCategoryListResponse(BaseModel):
    categories: list[VaultCategoryRead]


class VaultCategorySuggestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=200)
    amount_cents: int | None = Field(default=None, gt=0)
    transaction_type: Literal["income", "expense"] | None = None


class VaultCategorySuggestionRead(BaseModel):
    label_key: str
    category: str | None
    book: Literal["business", "personal"] | None
    source: Literal["user_memory", "table", "ai", "none"]
    confidence: Literal["high", "medium", "low"] | None
    confirmations: int = 0


class VaultCategoryConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=80)


class VaultCategoryConfirmResponse(BaseModel):
    label_key: str
    category: str
    book: Literal["business", "personal"]
    confirmations: int


class VaultReceiptLineRead(BaseModel):
    index: int
    description: str
    quantity: float
    unit: str
    total_cents: int
    category_hint: str
    to_stock: bool  # coché par défaut sur VAU-05 : les lignes alimentaires


class VaultReceiptDraftRead(BaseModel):
    merchant: str | None = None
    purchase_date: date | None = None
    purchase_time: str | None = None
    total_cents: int | None = None
    payment_method: str = "unknown"
    wallet: str | None = None
    category: str | None = None
    book: str | None = None
    category_source: str | None = None
    line_items: list[VaultReceiptLineRead] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class VaultReceiptExtractionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entry_app: str
    status: str
    original_filename: str
    mime_type: str
    size_bytes: int
    ocr_confidence: float | None
    draft: VaultReceiptDraftRead | None
    error_message: str | None
    transaction_id: UUID | None
    created_at: datetime
    validated_at: datetime | None


class VaultReceiptValidateRequest(BaseModel):
    """Ce que l'utilisateur a vérifié ou corrigé sur l'écran VAU-05."""

    model_config = ConfigDict(extra="forbid")

    amount_cents: int = Field(gt=0)
    occurred_at: datetime
    timezone: str | None = Field(default=None, min_length=1, max_length=80)
    category: str | None = Field(default=None, max_length=80)
    wallet: str = Field(default="cash", min_length=1, max_length=80)
    note: str | None = Field(default=None, max_length=500)
    # Lignes qui entrent au stock Pulse. Absent : les lignes alimentaires du brouillon ;
    # liste vide : rien au stock.
    stock_lines: list[FoodStockLineIn] | None = Field(default=None, max_length=100)

    @field_validator("occurred_at")
    @classmethod
    def require_timezone_aware_occurred_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include timezone information.")
        return value


class VaultReceiptValidateResponse(BaseModel):
    extraction: VaultReceiptExtractionRead
    transaction: ImperiumVaultTransactionRead
    stock_items: list[FoodStockItemRead] = Field(default_factory=list)


class WalletSnapshotCreate(BaseModel):
    """Soldes réels (doc 42 §8.1) : EUR seul, crypto en contre-valeur ; la banque peut être à découvert."""

    model_config = ConfigDict(extra="forbid")

    cash_cents: int = Field(ge=0, le=100_000_000, strict=True)
    bank_cents: int = Field(ge=-100_000_000, le=1_000_000_000, strict=True)
    crypto_cents: int = Field(default=0, ge=0, le=1_000_000_000, strict=True)
    recorded_at: datetime | None = None
    note: str | None = Field(default=None, max_length=300)


class WalletSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cash_cents: int
    bank_cents: int
    crypto_cents: int
    total_cents: int
    recorded_at: datetime
    source: str
    note: str | None


class WalletStateRead(BaseModel):
    """Dernier relevé (réel) et solde prévu = relevé + transactions passées depuis (doc 42 §8.2)."""

    snapshot: WalletSnapshotRead | None
    predicted_cash_cents: int | None
    predicted_bank_cents: int | None
    predicted_crypto_cents: int | None
    predicted_total_cents: int | None
    transactions_since: int
    other_wallets_cents: dict[str, int]  # transactions sur un autre portefeuille (ex. plateforme), hors total
    check_suggested: bool  # écart prévu / réel > 5 % : « Vérifier ton solde réel ? »
    message: str | None


class UpcomingExpensePay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_cents: int | None = Field(default=None, gt=0, le=100_000_000, strict=True)  # absent : le montant prévu
    paid_at: datetime | None = None
    wallet: str | None = Field(default=None, min_length=1, max_length=80)  # absent : celui de la dépense, sinon cash


class UpcomingExpensePayResult(BaseModel):
    expense: UpcomingExpenseRead
    transaction: ImperiumVaultTransactionRead
    next_occurrence: UpcomingExpenseRead | None
