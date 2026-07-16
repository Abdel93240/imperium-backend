from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.event import Event
from app.models.toolbox import SignalValue
from app.models.vault import ImperiumVaultTransaction, PressureSnapshot, UpcomingExpense
from app.services.events.emitter import build_event
from app.services.params import get_parameter

MONEY = Decimal("0.01")
ZERO = Decimal("0.00")
LABELS = ("safe", "stable", "attention", "pressure", "critical")
FUEL_CATEGORIES = {"fuel", "carburant", "diesel", "essence"}
FIXED_WEEKLY_CHARGE_CATEGORIES = {"fixed_weekly_charges", "charges", "charge fixe", "charges fixes"}
CONDITIONAL_REQUIRED_CATEGORIES = {
    "family_exceptional_expense",
    "school_payment_due",
    "rent_proximity",
    "leasing_payment_proximity",
    "loyer",
    "rent",
    "leasing",
    "school",
    "ecole",
    "école",
}
EXCEPTIONAL_REQUIRED_CATEGORIES = {
    "exceptional_required_expenses",
    "urgent_maintenance_cost",
    "maintenance",
    "entretien",
    "reparation",
    "réparation",
}


@dataclass(frozen=True)
class PressureInputs:
    current_week_income: Decimal = ZERO
    expected_week_income: Decimal = ZERO
    fixed_weekly_charges: Decimal = ZERO
    upcoming_required_expenses: Decimal = ZERO
    overdue_expenses: Decimal = ZERO
    available_liquidity: Decimal = ZERO
    fuel_required_next_days: Decimal = ZERO
    conditional_required_expenses: Decimal = ZERO
    exceptional_required_expenses: Decimal = ZERO
    urgent_fixed_charges_due_within_3_days: Decimal = ZERO
    minimum_survival_threshold: Decimal = Decimal("150.00")
    number_of_remaining_work_days: int = 1
    realistic_daily_capacity: Decimal = Decimal("220.00")


@dataclass(frozen=True)
class PressureResult:
    score: int
    label: str
    factors: dict
    daily_targets: dict[str, Decimal]
    inputs_snapshot: dict


def compute_pressure(inputs: PressureInputs) -> PressureResult:
    required_money = _money(
        inputs.fixed_weekly_charges
        + inputs.upcoming_required_expenses
        + inputs.overdue_expenses
        + inputs.fuel_required_next_days
        + inputs.conditional_required_expenses
    )
    remaining_required = max(ZERO, _money(required_money - inputs.available_liquidity))
    remaining_capacity = _money(
        Decimal(max(0, inputs.number_of_remaining_work_days)) * inputs.realistic_daily_capacity
    )
    denominator = max(Decimal("1.00"), remaining_capacity)
    base_ratio = remaining_required / denominator
    base_score = min(100, max(0, _score(base_ratio * Decimal("100"))))

    overdue_modifier = _overdue_modifier(inputs.overdue_expenses, remaining_capacity)
    low_cash_modifier = _low_cash_modifier(inputs.available_liquidity, inputs.minimum_survival_threshold)
    urgent_fixed_charge_modifier = 10 if inputs.urgent_fixed_charges_due_within_3_days > inputs.available_liquidity else 0
    exceptional_modifier = _exceptional_modifier(inputs.exceptional_required_expenses, remaining_capacity)

    final_score = min(100, max(0, base_score + overdue_modifier + low_cash_modifier + urgent_fixed_charge_modifier + exceptional_modifier))
    label = label_for_score(final_score)
    daily_targets = _daily_targets(
        remaining_required=remaining_required,
        work_days=inputs.number_of_remaining_work_days,
        realistic_daily_capacity=inputs.realistic_daily_capacity,
        label=label,
    )
    factors = {
        "required_money_this_week": required_money,
        "remaining_required_money": remaining_required,
        "remaining_realistic_earning_capacity": remaining_capacity,
        "base_pressure_ratio": _ratio(base_ratio),
        "base_score": base_score,
        "modifiers": {
            "overdue": overdue_modifier,
            "low_cash": low_cash_modifier,
            "urgent_fixed_charge": urgent_fixed_charge_modifier,
            "exceptional": exceptional_modifier,
        },
    }
    return PressureResult(
        score=final_score,
        label=label,
        factors=factors,
        daily_targets=daily_targets,
        inputs_snapshot=_inputs_snapshot(inputs),
    )


def explain(result: PressureResult) -> dict:
    return {
        "score": result.score,
        "label": result.label,
        "factors": result.factors,
        "daily_targets": result.daily_targets,
        "inputs_snapshot": result.inputs_snapshot,
    }


def label_for_score(score: int) -> str:
    if score <= 20:
        return "safe"
    if score <= 40:
        return "stable"
    if score <= 60:
        return "attention"
    if score <= 80:
        return "pressure"
    return "critical"


def compute_pressure_from_db(
    db: Session,
    *,
    current_user: User,
    today: date | None = None,
    now: datetime | None = None,
    causation_event_id: str | None = None,
) -> PressureSnapshot:
    now = now or datetime.now(UTC)
    today = today or now.date()
    inputs = load_pressure_inputs(db, current_user=current_user, today=today, now=now)
    return publish_pressure_result(
        db,
        current_user=current_user,
        result=compute_pressure(inputs),
        computed_at=now,
        causation_event_id=causation_event_id,
    )


def load_pressure_inputs(
    db: Session, *, current_user: User, today: date, now: datetime
) -> PressureInputs:
    minimum_survival = Decimal(str(get_parameter(db, "vault.minimum_survival_threshold", default=150)))
    realistic_daily_capacity = _recent_daily_capacity(db, current_user=current_user, today=today)
    work_days = _remaining_work_days(today)
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    transactions = list(
        db.scalars(
            select(ImperiumVaultTransaction).where(
                ImperiumVaultTransaction.user_id == current_user.id,
                ImperiumVaultTransaction.currency == "EUR",
            )
        )
    )
    liquidity = ZERO
    current_week_income = ZERO
    for transaction in transactions:
        amount = Decimal(transaction.amount_cents) / Decimal("100")
        signed = amount if transaction.transaction_type == "income" else -amount
        if transaction.wallet in {"cash", "bank"} and transaction.occurred_at <= now:
            liquidity += signed
        if (
            transaction.transaction_type == "income"
            and week_start <= transaction.local_date <= today
        ):
            current_week_income += amount

    active_expenses = list(
        db.scalars(
            select(UpcomingExpense).where(
                UpcomingExpense.user_id == current_user.id,
                UpcomingExpense.active.is_(True),
                UpcomingExpense.due_date <= week_end,
            )
        )
    )
    fixed_weekly = ZERO
    overdue = ZERO
    upcoming = ZERO
    fuel = ZERO
    conditional = ZERO
    exceptional = ZERO
    urgent = ZERO
    for expense in active_expenses:
        if not expense.mandatory:
            continue
        if expense.due_date > week_end:
            continue
        amount = _money(Decimal(expense.amount))
        if expense.due_date < today:
            overdue += amount
            continue
        if expense.due_date <= today + timedelta(days=3):
            urgent += amount

        category = _normalize_category(expense.category)
        if category in FUEL_CATEGORIES:
            fuel += amount
        elif category in EXCEPTIONAL_REQUIRED_CATEGORIES:
            exceptional += amount
        elif expense.recurrence in {"monthly", "quarterly", "yearly"} or category in CONDITIONAL_REQUIRED_CATEGORIES:
            conditional += amount
        elif expense.recurrence == "weekly" or category in FIXED_WEEKLY_CHARGE_CATEGORIES:
            fixed_weekly += amount
        else:
            upcoming += amount

    return PressureInputs(
        current_week_income=_money(current_week_income),
        expected_week_income=_money(current_week_income),
        fixed_weekly_charges=_money(fixed_weekly),
        upcoming_required_expenses=_money(upcoming),
        overdue_expenses=_money(overdue),
        available_liquidity=_money(liquidity),
        fuel_required_next_days=_money(fuel),
        conditional_required_expenses=_money(conditional),
        exceptional_required_expenses=_money(exceptional),
        urgent_fixed_charges_due_within_3_days=_money(urgent),
        minimum_survival_threshold=_money(minimum_survival),
        number_of_remaining_work_days=work_days,
        realistic_daily_capacity=realistic_daily_capacity,
    )


def publish_pressure_result(
    db: Session,
    *,
    current_user: User,
    result: PressureResult,
    computed_at: datetime | None = None,
    causation_event_id: str | None = None,
) -> PressureSnapshot:
    computed_at = computed_at or datetime.now(UTC)
    snapshot = PressureSnapshot(
        id=uuid4(),
        user_id=current_user.id,
        computed_at=computed_at,
        score=result.score,
        label=result.label,
        factors=_jsonify(result.factors),
        daily_targets=_jsonify(result.daily_targets),
        inputs_snapshot=_jsonify(result.inputs_snapshot),
    )
    db.add(snapshot)
    db.flush()

    db.add(
        SignalValue(
            id=uuid4(),
            signal_code="vault.pressure",
            measured_at=computed_at,
            value=result.score,
            band=result.label,
            flags={},
            stale=False,
            detail={
                "snapshot_id": str(snapshot.id),
                "daily_targets": _jsonify(result.daily_targets),
                "factors": _jsonify(result.factors),
            },
        )
    )
    event = build_event(
        db,
        user_id=current_user.id,
        event_type="finance.pressure.updated",
        payload={"snapshot_id": str(snapshot.id), "score": result.score, "label": result.label},
        idempotency_key=f"vault.pressure.{snapshot.id}",
        source_app=SourceApp.vault,
        privacy_level=PrivacyLevel.high,
        causation_id=causation_event_id,
    )
    db.add(event)
    db.commit()
    return snapshot


def latest_pressure_snapshot(db: Session, *, current_user: User) -> PressureSnapshot | None:
    return db.scalar(
        select(PressureSnapshot)
        .where(PressureSnapshot.user_id == current_user.id)
        .order_by(PressureSnapshot.computed_at.desc())
        .limit(1)
    )


def pressure_history(db: Session, *, current_user: User, limit: int = 30) -> list[PressureSnapshot]:
    return list(
        db.scalars(
            select(PressureSnapshot)
            .where(PressureSnapshot.user_id == current_user.id)
            .order_by(PressureSnapshot.computed_at.desc())
            .limit(limit)
        )
    )


def pressure_refresh_job(ctx, window) -> None:

    user = _job_user(ctx.db)
    if user is None:
        ctx.items_in = 0
        ctx.items_out = 0
        ctx.detail = {"skip": "no_user"}
        if window.to_ts is not None:
            ctx.cursor_ts = window.to_ts
        return
    causation_event_id = None
    if ctx.trigger_ref is not None:
        event = ctx.db.get(Event, ctx.trigger_ref)
        if event is not None:
            causation_event_id = event.event_id
    compute_pressure_from_db(
        ctx.db, current_user=user, now=window.to_ts or datetime.now(UTC), causation_event_id=causation_event_id
    )
    ctx.items_in = 1
    ctx.items_out = 1
    ctx.detail = {"refreshed": True}
    if window.to_ts is not None:
        ctx.cursor_ts = window.to_ts
        ctx.cursor_event_id = ctx.trigger_ref


def _job_user(db: Session) -> User | None:
    from app.core.config import get_settings
    from app.models.auth import User

    settings = get_settings()
    if settings.imperium_canonical_user_id is not None:
        user = db.get(User, settings.imperium_canonical_user_id)
        if user is not None:
            return user
    return db.scalar(select(User).order_by(User.created_at).limit(1))


def _recent_daily_capacity(db: Session, *, current_user: User, today: date) -> Decimal:
    since = today - timedelta(days=14)
    transactions = list(
        db.scalars(
            select(ImperiumVaultTransaction).where(
                ImperiumVaultTransaction.user_id == current_user.id,
                ImperiumVaultTransaction.transaction_type == "income",
                ImperiumVaultTransaction.local_date >= since,
                ImperiumVaultTransaction.local_date <= today,
                ImperiumVaultTransaction.currency == "EUR",
            )
        )
    )
    if not transactions:
        return Decimal("220.00")
    totals: dict[date, Decimal] = {}
    for transaction in transactions:
        totals.setdefault(transaction.local_date, ZERO)
        totals[transaction.local_date] += Decimal(transaction.amount_cents) / Decimal("100")
    return _money(sum(totals.values(), ZERO) / Decimal(len(totals)))


def _normalize_category(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip().lower()


def _remaining_work_days(today: date) -> int:
    return max(1, 7 - today.weekday())


def _daily_targets(
    *, remaining_required: Decimal, work_days: int, realistic_daily_capacity: Decimal, label: str
) -> dict[str, Decimal]:
    minimum = _money(remaining_required / Decimal(max(1, work_days)))
    if label == "critical":
        comfortable_cap = realistic_daily_capacity * Decimal("1.15")
    else:
        comfortable_cap = realistic_daily_capacity
    comfortable = _money(min(comfortable_cap, minimum * Decimal("1.35")))
    optimal = _money(min(realistic_daily_capacity * Decimal("1.25"), minimum * Decimal("1.75")))
    return {"minimum": minimum, "comfortable": comfortable, "optimal": optimal}


def _overdue_modifier(overdue: Decimal, capacity: Decimal) -> int:
    if overdue <= 0:
        return 0
    if overdue > Decimal("0.5") * capacity:
        return 15
    return 10


def _low_cash_modifier(liquidity: Decimal, threshold: Decimal) -> int:
    if liquidity <= 0:
        return 15
    if liquidity < threshold:
        return 10
    return 0


def _exceptional_modifier(exceptional: Decimal, capacity: Decimal) -> int:
    if exceptional <= 0:
        return 0
    if exceptional > capacity:
        return 10
    return 5


def _score(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _ratio(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def _inputs_snapshot(inputs: PressureInputs) -> dict:
    return _jsonify(asdict(inputs))


def _jsonify(value):
    if isinstance(value, Decimal):
        return str(_money(value))
    if isinstance(value, dict):
        return {key: _jsonify(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_jsonify(item) for item in value]
    return value
