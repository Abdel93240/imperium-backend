"""Sadaqa (doc 41 §9) : objectif de la semaine, report, dons, dépense au Vault.

Objectif d'une semaine (lundi → dimanche, Paris) :
    base   = max(bénéfice pro de la semaine, 0) × pourcentage × (1 + marge)
    cible  = base + montant reporté de la semaine précédente
    reste  = max(0, cible − dons de la semaine)          (jamais de « crédit » négatif)
Le bénéfice pro vient de `weekly_finance_summaries` (job Vault) ou, à défaut, du registre
Vault lu directement. La marge s'applique à la base seulement : le montant reporté la
contient déjà, elle ne se cumule pas d'une semaine à l'autre.

Une semaine close (job `path.sadaqa_week_close`) est figée dans `path_sadaqa_weeks` : son
report ne change plus, même si le registre Vault ou un don de cette semaine change ensuite.
Le suivi commence à la semaine du premier réglage ou du premier don (jamais de rattrapage
sur un historique Vault antérieur), et remonte au plus 104 semaines.

Un don est enregistré côté Path d'abord ; la dépense « sadaqa » est ensuite écrite au Vault
par le service Vault (doc 42 §15.1). Si cette écriture échoue, le don reste enregistré
avec `vault_status = pending` jusqu'à une nouvelle tentative. Les événements ne portent ni
le montant ni la destination.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.path import PathSadaqaDonation, PathSadaqaSetting, PathSadaqaWeek
from app.models.vault import ImperiumVaultTransaction, WeeklyFinanceSummary
from app.schemas.path_sadaqa import (
    SadaqaAllocationLine,
    SadaqaDonationCreate,
    SadaqaDonationDeleteResult,
    SadaqaDonationListResponse,
    SadaqaDonationRead,
    SadaqaDonationResult,
    SadaqaPendingChangeRead,
    SadaqaSettingsRead,
    SadaqaSettingsUpdate,
    SadaqaWeekRead,
)
from app.schemas.vault import ImperiumVaultTransactionCreate, ImperiumVaultTransactionReverseRequest
from app.services.events.emitter import build_event
from app.services.imperium import vault_transactions
from app.services.pulse import food_stock
from app.services.vault.weekly import _category_map, build_weekly_summary_detail

logger = logging.getLogger(__name__)

PARIS = ZoneInfo("Europe/Paris")
DEFAULT_PERCENTAGE = Decimal("0.0500")
DEFAULT_SAFETY_MARGIN = Decimal("0.1250")
MAX_WEEKS_BACK = 104
CLOCK_SKEW = timedelta(minutes=5)
WEEK = timedelta(days=7)
VAULT_PENDING = "Don enregistré. La dépense n'a pas pu être écrite au Vault : elle est en attente, réessaie plus tard."
SECOND_CHANGE = (
    "Deuxième changement cette semaine : la nouvelle valeur ne vaudra que pour les prochains objectifs. "
    "Confirme pour l'enregistrer."
)


class SadaqaInputError(ValueError):
    pass


class SadaqaNotFoundError(ValueError):
    pass


class SadaqaStateError(ValueError):
    pass


class SadaqaIdempotencyConflictError(ValueError):
    pass


class SadaqaVaultUnavailableError(RuntimeError):
    pass


class SadaqaSecondChangeError(ValueError):
    def __init__(self) -> None:
        super().__init__(SECOND_CHANGE)


class SadaqaSettingsConflictError(ValueError):
    def __init__(self, current: SadaqaSettingsRead) -> None:
        super().__init__("Les réglages sadaqa ont changé depuis ta lecture.")
        self.current = current


@dataclass
class WeekFigures:
    week_start: date
    profit_cents: int
    profit_source: str
    percentage: Decimal
    safety_margin: Decimal
    base_cents: int
    carried_in_cents: int
    target_cents: int
    donated_cents: int
    remaining_cents: int
    closed: bool


# ---------- semaines ----------

def week_start_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def current_week(now: datetime) -> date:
    return week_start_of(now.astimezone(PARIS).date())


# ---------- réglages ----------

def get_settings(db: Session, *, current_user: User, now: datetime | None = None) -> SadaqaSettingsRead:
    return _settings_read(_setting_rows(db, current_user), now or datetime.now(UTC))


def update_settings(
    db: Session, *, current_user: User, payload: SadaqaSettingsUpdate, idempotency_key: str, request_path: str,
    now: datetime | None = None,
) -> tuple[SadaqaSettingsRead, bool]:
    fingerprint = food_stock.request_hash("path.sadaqa.settings", payload.model_dump(mode="json"))
    previous = food_stock.replay(db, current_user, idempotency_key, fingerprint, request_path, SadaqaSettingsRead)
    if previous is not None:
        return previous, True
    now = now or datetime.now(UTC)
    rows = _setting_rows(db, current_user, lock=True)
    current = _settings_read(rows, now)
    if payload.base_version != current.version:
        raise SadaqaSettingsConflictError(current)
    second = current.changes_this_week >= 1
    if second and not payload.confirm_second_change:
        raise SadaqaSecondChangeError()
    if second and payload.apply_to_current_week:
        raise SadaqaInputError("Un deuxième changement dans la semaine ne vaut que pour les prochaines semaines.")
    week = current_week(now)
    latest = rows[-1] if rows else None
    row = PathSadaqaSetting(
        user_id=current_user.id,
        percentage=payload.percentage if payload.percentage is not None else (latest.percentage if latest else DEFAULT_PERCENTAGE),
        safety_margin=payload.safety_margin if payload.safety_margin is not None
        else (latest.safety_margin if latest else DEFAULT_SAFETY_MARGIN),
        effective_from=week if payload.apply_to_current_week else week + WEEK,
        created_at=now,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    db.add(
        build_event(
            db, user_id=current_user.id, event_type="path.sadaqa.settings_updated",
            payload={"percentage": str(row.percentage), "safety_margin": str(row.safety_margin),
                     "applies_from": row.effective_from.isoformat(), "source": "user_action"},
            idempotency_key=f"path.sadaqa.settings_updated.{row.id}", source_app=SourceApp.path,
            privacy_level=PrivacyLevel.high,
        )
    )
    read = _settings_read([*rows, row], now)
    food_stock.remember(db, current_user, idempotency_key, "PATCH", request_path, fingerprint, 200, read)
    db.commit()
    return read, False


def _setting_rows(db: Session, user: User, *, lock: bool = False) -> list[PathSadaqaSetting]:
    query = select(PathSadaqaSetting).where(PathSadaqaSetting.user_id == user.id).order_by(PathSadaqaSetting.created_at.asc())
    return list(db.scalars(query.with_for_update() if lock else query))


def _rate(rows: list[PathSadaqaSetting], week: date) -> PathSadaqaSetting | None:
    candidates = [row for row in rows if row.effective_from <= week]
    return max(candidates, key=lambda row: (row.effective_from, row.created_at)) if candidates else None


def _settings_read(rows: list[PathSadaqaSetting], now: datetime) -> SadaqaSettingsRead:
    week = current_week(now)
    applied = _rate(rows, week)
    future = [row for row in rows if row.effective_from > week]
    pending = max(future, key=lambda row: row.created_at) if future else None
    week_begin = datetime.combine(week, time.min, tzinfo=PARIS)
    return SadaqaSettingsRead(
        percentage=applied.percentage if applied else DEFAULT_PERCENTAGE,
        safety_margin=applied.safety_margin if applied else DEFAULT_SAFETY_MARGIN,
        applies_from=applied.effective_from if applied else None,
        pending=SadaqaPendingChangeRead(
            percentage=pending.percentage, safety_margin=pending.safety_margin, applies_from=pending.effective_from
        ) if pending else None,
        changes_this_week=sum(1 for row in rows if row.created_at >= week_begin),
        version=len(rows),
    )


# ---------- objectif de la semaine ----------

def week_summary(
    db: Session, *, current_user: User, week_start: date | None = None, now: datetime | None = None
) -> SadaqaWeekRead:
    now = now or datetime.now(UTC)
    this_week = current_week(now)
    week = week_start or this_week
    if week.weekday() != 0:
        raise SadaqaInputError("week_start doit être un lundi.")
    if week > this_week:
        raise SadaqaInputError("Cette semaine n'a pas encore commencé.")
    figures = _chain(db, current_user, week)[-1]
    pending = db.scalar(
        select(func.count()).select_from(PathSadaqaDonation).where(
            PathSadaqaDonation.user_id == current_user.id, PathSadaqaDonation.vault_status == "pending"
        )
    ) or 0
    return _week_read(figures, pending)


def _chain(db: Session, user: User, until: date) -> list[WeekFigures]:
    """Semaines du début du suivi jusqu'à `until` ; une semaine close est lue telle quelle."""
    start = _start_week(db, user)
    if start is None or start > until:
        start = until
    start = max(start, until - MAX_WEEKS_BACK * WEEK)
    snapshots = {
        row.week_start: row
        for row in db.scalars(
            select(PathSadaqaWeek).where(
                PathSadaqaWeek.user_id == user.id, PathSadaqaWeek.week_start >= start, PathSadaqaWeek.week_start <= until
            )
        )
    }
    donated = dict(
        db.execute(
            select(PathSadaqaDonation.related_week_start, func.sum(PathSadaqaDonation.amount_cents))
            .where(PathSadaqaDonation.user_id == user.id, PathSadaqaDonation.related_week_start >= start,
                   PathSadaqaDonation.related_week_start <= until)
            .group_by(PathSadaqaDonation.related_week_start)
        ).all()
    )
    summaries = {
        row.week_start: row
        for row in db.scalars(
            select(WeeklyFinanceSummary).where(
                WeeklyFinanceSummary.user_id == user.id, WeeklyFinanceSummary.week_start >= start,
                WeeklyFinanceSummary.week_start <= until,
            )
        )
    }
    rows = _setting_rows(db, user)
    chain: list[WeekFigures] = []
    carry = 0
    week = start
    while week <= until:
        snapshot = snapshots.get(week)
        if snapshot is not None:
            figures = WeekFigures(
                week_start=week, profit_cents=snapshot.business_profit_cents, profit_source="snapshot",
                percentage=snapshot.percentage, safety_margin=snapshot.safety_margin, base_cents=snapshot.base_target_cents,
                carried_in_cents=snapshot.carried_in_cents, target_cents=snapshot.target_cents,
                donated_cents=snapshot.donated_cents, remaining_cents=snapshot.remaining_cents, closed=True,
            )
        else:
            profit, source = _profit(db, user, week, summaries.get(week))
            rate = _rate(rows, week)
            percentage = rate.percentage if rate else DEFAULT_PERCENTAGE
            margin = rate.safety_margin if rate else DEFAULT_SAFETY_MARGIN
            base = int((Decimal(max(profit, 0)) * Decimal(percentage) * (1 + Decimal(margin))).quantize(Decimal("1"), ROUND_HALF_UP))
            given = int(donated.get(week) or 0)
            figures = WeekFigures(
                week_start=week, profit_cents=profit, profit_source=source, percentage=Decimal(percentage),
                safety_margin=Decimal(margin), base_cents=base, carried_in_cents=carry, target_cents=base + carry,
                donated_cents=given, remaining_cents=max(0, base + carry - given), closed=False,
            )
        chain.append(figures)
        carry = figures.remaining_cents
        week += WEEK
    return chain


def _start_week(db: Session, user: User) -> date | None:
    first_setting = db.scalar(select(func.min(PathSadaqaSetting.created_at)).where(PathSadaqaSetting.user_id == user.id))
    candidates = [
        db.scalar(select(func.min(PathSadaqaDonation.related_week_start)).where(PathSadaqaDonation.user_id == user.id)),
        db.scalar(select(func.min(PathSadaqaWeek.week_start)).where(PathSadaqaWeek.user_id == user.id)),
        current_week(first_setting) if first_setting else None,
    ]
    found = [candidate for candidate in candidates if candidate is not None]
    return min(found) if found else None


def _profit(db: Session, user: User, week: date, summary: WeeklyFinanceSummary | None) -> tuple[int, str]:
    if summary is not None:
        return _cents(summary.weekly_business_profit), "vault_summary"
    transactions = list(
        db.scalars(
            select(ImperiumVaultTransaction).where(
                ImperiumVaultTransaction.user_id == user.id, ImperiumVaultTransaction.local_date >= week,
                ImperiumVaultTransaction.local_date <= week + timedelta(days=6), ImperiumVaultTransaction.currency == "EUR",
            )
        )
    )
    data = build_weekly_summary_detail(transactions, category_map=_category_map(db))
    return _cents(data["weekly_business_profit"]), "live"


def _week_read(figures: WeekFigures, vault_pending: int) -> SadaqaWeekRead:
    carried = figures.carried_in_cents
    return SadaqaWeekRead(
        week_start=figures.week_start, week_end=figures.week_start + timedelta(days=6), closed=figures.closed,
        business_profit=_euros(figures.profit_cents), profit_source=figures.profit_source,
        percentage=figures.percentage, safety_margin=figures.safety_margin, base_target=_euros(figures.base_cents),
        carried_in=_euros(carried), target=_euros(figures.target_cents), donated=_euros(figures.donated_cents),
        remaining=_euros(figures.remaining_cents),
        carry_message=f"Montant reporté : {_label(carried)}." if carried > 0 else None,
        vault_pending=vault_pending,
    )


# ---------- dons ----------

def create_donation(
    db: Session, *, current_user: User, payload: SadaqaDonationCreate, idempotency_key: str, now: datetime | None = None,
) -> tuple[SadaqaDonationResult, bool]:
    now = now or datetime.now(UTC)
    fingerprint = food_stock.request_hash("path.sadaqa.donation", payload.model_dump(mode="json"))
    existing = db.scalar(
        select(PathSadaqaDonation).where(
            PathSadaqaDonation.user_id == current_user.id, PathSadaqaDonation.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise SadaqaIdempotencyConflictError("Idempotency key already used with a different donation.")
        return _result(db, current_user, existing, [], now), True
    donated_at = payload.donated_at or now
    if donated_at > now + CLOCK_SKEW:
        raise SadaqaInputError("La date du don ne peut pas être dans le futur.")
    week = week_start_of(donated_at.astimezone(PARIS).date())
    closed = db.get(PathSadaqaWeek, (current_user.id, week)) is not None
    if closed:  # semaine figée : le don déclaré après coup compte pour la semaine en cours
        week = current_week(now)
    figures = _chain(db, current_user, week)[-1]
    donation = PathSadaqaDonation(
        user_id=current_user.id, amount_cents=payload.amount_cents,
        destination=(payload.destination or "").strip() or None, note=(payload.note or "").strip() or None,
        donated_at=donated_at, related_week_start=week,
        allocation=[line.model_dump() for line in _allocate(figures, payload.amount_cents)],
        record_in_vault=payload.record_in_vault, wallet=payload.wallet.strip(),
        vault_status="pending" if payload.record_in_vault else "not_requested",
        idempotency_key=idempotency_key, request_hash=fingerprint,
    )
    db.add(donation)
    db.flush()
    db.add(
        build_event(
            db, user_id=current_user.id, event_type="path.sadaqa.recorded",
            payload={"donation_id": str(donation.id), "related_week_start": week.isoformat(),
                     "record_in_vault": donation.record_in_vault, "source": "user_action"},
            idempotency_key=f"path.sadaqa.recorded.{donation.id}", source_app=SourceApp.path,
            privacy_level=PrivacyLevel.very_high,
        )
    )
    db.commit()  # le don Path est enregistré, quoi qu'il arrive au Vault ensuite
    warnings = []
    if donation.record_in_vault and not _record_in_vault(db, current_user, donation.id):
        warnings.append(VAULT_PENDING)
    if closed:
        warnings.append("Cette semaine est close : le don compte pour la semaine en cours.")
    return _result(db, current_user, db.get(PathSadaqaDonation, donation.id), warnings, now), False


def retry_vault(db: Session, *, current_user: User, donation_id: UUID) -> SadaqaDonationRead:
    donation = _get(db, current_user, donation_id)
    if donation.vault_status == "not_requested":
        raise SadaqaStateError("Ce don n'est pas destiné au Vault.")
    if donation.vault_status == "pending" and not _record_in_vault(db, current_user, donation.id):
        raise SadaqaVaultUnavailableError(VAULT_PENDING)
    return SadaqaDonationRead.model_validate(db.get(PathSadaqaDonation, donation_id))


def list_donations(db: Session, *, current_user: User, from_day: date, to_day: date) -> SadaqaDonationListResponse:
    if to_day < from_day or (to_day - from_day).days > 366:
        raise SadaqaInputError("Période invalide (366 jours maximum).")
    start = datetime.combine(from_day, time.min, tzinfo=PARIS)
    end = datetime.combine(to_day + timedelta(days=1), time.min, tzinfo=PARIS)
    donations = db.scalars(
        select(PathSadaqaDonation)
        .where(PathSadaqaDonation.user_id == current_user.id, PathSadaqaDonation.donated_at >= start,
               PathSadaqaDonation.donated_at < end)
        .order_by(PathSadaqaDonation.donated_at.desc())
    )
    return SadaqaDonationListResponse(items=[SadaqaDonationRead.model_validate(donation) for donation in donations])


def delete_donation(db: Session, *, current_user: User, donation_id: UUID) -> SadaqaDonationDeleteResult:
    """Suppression réelle côté Path ; la dépense Vault est annulée par une écriture inverse (registre en ajout seul)."""
    donation = _get(db, current_user, donation_id, lock=True)
    transaction_id = donation.vault_transaction_id
    db.add(
        build_event(
            db, user_id=current_user.id, event_type="path.sadaqa.deleted",
            payload={"donation_id": str(donation.id), "related_week_start": donation.related_week_start.isoformat(),
                     "vault_transaction_id": str(transaction_id) if transaction_id else None},
            idempotency_key=f"path.sadaqa.deleted.{donation.id}", source_app=SourceApp.path,
            privacy_level=PrivacyLevel.very_high,
        )
    )
    db.delete(donation)
    db.flush()
    if transaction_id is None:
        db.commit()
        return SadaqaDonationDeleteResult(deleted=True, vault_reversed=False)
    try:
        vault_transactions.reverse_vault_transaction(  # écrit l'inverse et valide la suppression avec
            db, current_user=current_user, transaction_id=transaction_id,
            payload=ImperiumVaultTransactionReverseRequest(reason="Don de sadaqa supprimé dans Path."),
            idempotency_key=f"path.sadaqa.vault.reverse.{donation_id}", request_method="DELETE",
            request_path="/internal/path/sadaqa/vault",
        )
    except vault_transactions.VaultTransactionReversalConflictError:
        db.commit()  # déjà annulée côté Vault
        return SadaqaDonationDeleteResult(deleted=True, vault_reversed=False)
    return SadaqaDonationDeleteResult(deleted=True, vault_reversed=True)


def _allocate(figures: WeekFigures, amount: int) -> list[SadaqaAllocationLine]:
    """Le don couvre d'abord le montant reporté, puis l'objectif de la semaine, le reste va au-delà."""
    given = figures.donated_cents
    carry_left = max(0, figures.carried_in_cents - given)
    target_left = max(0, figures.base_cents - max(0, given - figures.carried_in_cents))
    to_carry = min(amount, carry_left)
    to_target = min(amount - to_carry, target_left)
    parts = (("carry", to_carry), ("week_target", to_target), ("beyond_target", amount - to_carry - to_target))
    return [SadaqaAllocationLine(part=part, amount_cents=value) for part, value in parts if value > 0]


def _record_in_vault(db: Session, user: User, donation_id: UUID) -> bool:
    """Deuxième écriture, par le service Vault (doc 42 §15.1) ; même clé à chaque tentative."""
    donation = db.get(PathSadaqaDonation, donation_id)
    try:
        transaction, _ = vault_transactions.create_vault_transaction(
            db, current_user=user,
            payload=ImperiumVaultTransactionCreate(
                transaction_type="expense", amount_cents=donation.amount_cents, wallet=donation.wallet,
                occurred_at=donation.donated_at, timezone="Europe/Paris", category="sadaqa", source="path_sadaqa",
                note="Sadaqa", external_ref=f"sadaqa:{donation.id}",
            ),
            idempotency_key=f"path.sadaqa.vault.{donation.id}", request_method="POST",
            request_path="/internal/path/sadaqa/vault",
        )
    except Exception:  # noqa: BLE001 - le don Path reste enregistré, la dépense Vault passe en attente
        db.rollback()
        logger.exception("Sadaqa: écriture Vault en échec.", extra={"donation_id": str(donation_id)})
        return False
    donation = db.get(PathSadaqaDonation, donation_id)
    donation.vault_status, donation.vault_transaction_id = "recorded", transaction.id
    db.commit()
    return True


def _result(db: Session, user: User, donation: PathSadaqaDonation, warnings: list[str], now: datetime) -> SadaqaDonationResult:
    return SadaqaDonationResult(
        donation=SadaqaDonationRead.model_validate(donation),
        week=week_summary(db, current_user=user, week_start=donation.related_week_start, now=now),
        warnings=warnings,
    )


def _get(db: Session, user: User, donation_id: UUID, *, lock: bool = False) -> PathSadaqaDonation:
    query = select(PathSadaqaDonation).where(PathSadaqaDonation.id == donation_id, PathSadaqaDonation.user_id == user.id)
    donation = db.scalar(query.with_for_update() if lock else query)
    if donation is None:
        raise SadaqaNotFoundError("Don introuvable.")
    return donation


# ---------- job de clôture ----------

def close_weeks(db: Session, user: User, now: datetime) -> int:
    """Fige les semaines terminées pas encore closes (au plus 104 en arrière)."""
    last = current_week(now) - WEEK
    start = _start_week(db, user)
    if start is None or start > last:
        return 0
    closed = 0
    for figures in _chain(db, user, last):
        if figures.closed:
            continue
        db.add(
            PathSadaqaWeek(
                user_id=user.id, week_start=figures.week_start, business_profit_cents=figures.profit_cents,
                profit_source=figures.profit_source, percentage=figures.percentage, safety_margin=figures.safety_margin,
                base_target_cents=figures.base_cents, carried_in_cents=figures.carried_in_cents,
                target_cents=figures.target_cents, donated_cents=figures.donated_cents,
                remaining_cents=figures.remaining_cents, closed_at=now,
            )
        )
        closed += 1
    db.flush()
    return closed


def sadaqa_week_close_job(ctx, window) -> None:  # noqa: ANN001 - contrat Handler du runner
    """path.sadaqa_week_close : le lundi, après le bénéfice hebdomadaire du Vault."""
    now = window.to_ts or datetime.now(UTC)
    user_ids = set(ctx.db.scalars(select(PathSadaqaSetting.user_id).distinct()))
    user_ids |= set(ctx.db.scalars(select(PathSadaqaDonation.user_id).distinct()))
    closed = sum(close_weeks(ctx.db, _Owner(user_id), now) for user_id in sorted(user_ids, key=str))
    ctx.items_in = len(user_ids)
    ctx.items_out = closed
    ctx.detail = {"users": len(user_ids), "weeks_closed": closed}


class _Owner:
    """Propriétaire des lignes, pour le job (pas de session utilisateur)."""

    def __init__(self, user_id: UUID) -> None:
        self.id = user_id


def _cents(value: Decimal) -> int:
    return int((Decimal(value) * 100).quantize(Decimal("1"), ROUND_HALF_UP))


def _euros(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(Decimal("0.01"))


def _label(cents: int) -> str:
    return f"{_euros(cents):.2f} €".replace(".", ",")
