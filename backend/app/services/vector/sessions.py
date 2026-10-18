"""Sessions VTC (Vector, doc 59 §14.1–§14.5, §14.10–§14.11 ; doc 13).

Une session encadre un temps de conduite : CA cible facultatif, direction stratégique,
mission Imperium liée. Les revenus et dépenses saisis pendant la session sont écrits au
Vault par le service Vault (doc 42 §15.3 : Vector n'écrit jamais une transaction lui-même),
catégories pro (revenu `vtc` ; carburant, entretien, plateformes, sinon `charges`), reliés
par `external_ref = rides:{session}:{clé}`. Une transaction annulée au Vault ne compte plus.

À la clôture, le CA et les dépenses sont figés dans la session. Vector ne lit ni fatigue ni
pression financière (doc 13 §5) : l'objectif atteint compare seulement le CA à la cible.
"""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumMission
from app.models.rides import RidesDropZone, RidesSession
from app.models.vault import ImperiumVaultTransaction
from app.schemas.rides import (
    CurrentSessionRead,
    DropZoneCreate,
    DropZoneRead,
    ManualExpenseCreate,
    ManualRevenueCreate,
    SessionComplete,
    SessionEntryResult,
    SessionKpis,
    SessionListResponse,
    SessionRead,
    SessionStart,
    SessionUpdate,
)
from app.schemas.vault import ImperiumVaultTransactionCreate
from app.services.events.emitter import build_event
from app.services.imperium import vault_transactions
from app.services.pulse import food_stock

PARIS = ZoneInfo("Europe/Paris")
CLOCK_SKEW = timedelta(minutes=5)
REVENUE_CATEGORY = "vtc"
# Catégories VEC-05 → catégories pro du Vault (vault.category_map, business_expenses).
EXPENSE_CATEGORIES = {
    "carburant": ("carburant", None),
    "peage": ("charges", "Péage"),
    "parking": ("charges", "Parking"),
    "entretien": ("entretien", None),
    "plateformes": ("plateformes", None),
    "autre": ("charges", None),
}


class RidesInputError(ValueError):
    pass


class RidesNotFoundError(ValueError):
    pass


class RidesIdempotencyConflictError(ValueError):
    pass


class RidesStateError(ValueError):
    def __init__(self, message: str, current: SessionRead | None = None) -> None:
        super().__init__(message)
        self.current = current


class RidesVersionConflictError(ValueError):
    def __init__(self, current: SessionRead) -> None:
        super().__init__("La session a changé depuis ta lecture.")
        self.current = current


# ---------- lecture ----------

def current_session(db: Session, *, current_user: User, now: datetime | None = None) -> CurrentSessionRead:
    session = db.scalar(select(RidesSession).where(RidesSession.user_id == current_user.id, RidesSession.status == "active"))
    return CurrentSessionRead(session=_read(db, session, now) if session else None)


def get_session(db: Session, *, current_user: User, session_id: UUID) -> SessionRead:
    return _read(db, _get(db, current_user, session_id))


def list_sessions(db: Session, *, current_user: User, from_day: date, to_day: date) -> SessionListResponse:
    if to_day < from_day or (to_day - from_day).days > 366:
        raise RidesInputError("Période invalide (366 jours maximum).")
    start = datetime.combine(from_day, time.min, tzinfo=PARIS)
    end = datetime.combine(to_day + timedelta(days=1), time.min, tzinfo=PARIS)
    rows = db.scalars(
        select(RidesSession)
        .where(RidesSession.user_id == current_user.id, RidesSession.started_at >= start, RidesSession.started_at < end)
        .order_by(RidesSession.started_at.desc())
    )
    return SessionListResponse(items=[_read(db, row) for row in rows])


# ---------- session ----------

def start_session(
    db: Session, *, current_user: User, payload: SessionStart, idempotency_key: str, now: datetime | None = None
) -> tuple[SessionRead, bool]:
    fingerprint = food_stock.request_hash("rides.session.start", payload.model_dump(mode="json"))
    existing = db.scalar(
        select(RidesSession).where(RidesSession.user_id == current_user.id, RidesSession.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise RidesIdempotencyConflictError("Idempotency key already used with a different session.")
        return _read(db, existing), True
    active = db.scalar(
        select(RidesSession).where(RidesSession.user_id == current_user.id, RidesSession.status == "active").with_for_update()
    )
    if active is not None:
        raise RidesStateError("Une session est déjà en cours.", _read(db, active))
    if payload.mission_id is not None and db.scalar(
        select(ImperiumMission.id).where(ImperiumMission.id == payload.mission_id, ImperiumMission.user_id == current_user.id)
    ) is None:
        raise RidesInputError("Mission introuvable.")
    session = RidesSession(
        user_id=current_user.id, status="active", started_at=now or datetime.now(UTC), target_ca_cents=payload.target_ca_cents,
        strategic_direction=(payload.strategic_direction or "").strip() or None, mission_id=payload.mission_id, version=1,
        idempotency_key=idempotency_key, request_hash=fingerprint,
    )
    db.add(session)
    db.flush()
    db.refresh(session)
    _event(db, current_user, "rides.session.started", session,
           {"target_ca_cents": session.target_ca_cents, "mission_id": str(session.mission_id) if session.mission_id else None})
    read = _read(db, session)
    db.commit()
    return read, False


def update_session(
    db: Session, *, current_user: User, session_id: UUID, payload: SessionUpdate, idempotency_key: str, request_path: str
) -> SessionRead:
    fingerprint = food_stock.request_hash(
        "rides.session.update", {"session_id": str(session_id), **payload.model_dump(mode="json", exclude_unset=True)}
    )
    previous = food_stock.replay(db, current_user, idempotency_key, fingerprint, request_path, SessionRead)
    if previous is not None:
        return previous
    session = _active(db, current_user, session_id)
    if session.version != payload.version:
        raise RidesVersionConflictError(_read(db, session))
    changes = payload.model_dump(exclude_unset=True, exclude={"version"})
    if "target_ca_cents" in changes:
        session.target_ca_cents = changes["target_ca_cents"]
    if "strategic_direction" in changes:
        session.strategic_direction = (changes["strategic_direction"] or "").strip() or None
    session.version += 1
    db.flush()
    db.refresh(session)
    read = _read(db, session)
    food_stock.remember(db, current_user, idempotency_key, "PATCH", request_path, fingerprint, 200, read)
    db.commit()
    return read


def complete_session(
    db: Session, *, current_user: User, session_id: UUID, payload: SessionComplete, idempotency_key: str,
    request_path: str, now: datetime | None = None,
) -> SessionRead:
    fingerprint = food_stock.request_hash("rides.session.complete", {"session_id": str(session_id), **payload.model_dump(mode="json")})
    previous = food_stock.replay(db, current_user, idempotency_key, fingerprint, request_path, SessionRead)
    if previous is not None:
        return previous
    now = now or datetime.now(UTC)
    session = _active(db, current_user, session_id)
    kpis = _kpis(db, session, now)
    session.status, session.ended_at = "completed", now
    session.final_revenue_cents, session.final_expense_cents = kpis.revenue_cents, kpis.expense_cents
    session.review_note = (payload.review_note or "").strip() or None
    session.version += 1
    db.flush()
    db.refresh(session)
    read = _read(db, session)
    _event(db, current_user, "rides.session.ended", session, {
        "revenue_cents": read.kpis.revenue_cents, "expense_cents": read.kpis.expense_cents,
        "objective_reached": read.kpis.objective_reached, "elapsed_minutes": read.kpis.elapsed_minutes,
    })
    food_stock.remember(db, current_user, idempotency_key, "POST", request_path, fingerprint, 200, read)
    db.commit()
    return read


# ---------- saisies ----------

def add_revenue(
    db: Session, *, current_user: User, session_id: UUID, payload: ManualRevenueCreate, idempotency_key: str,
    request_path: str, now: datetime | None = None,
) -> SessionEntryResult:
    zone = (payload.zone or "").strip()
    note = " · ".join(part for part in (f"Zone : {zone}" if zone else "", (payload.note or "").strip()) if part) or None
    return _vault_entry(db, current_user, session_id, "income", payload.amount_cents, REVENUE_CATEGORY, payload.wallet,
                        payload.occurred_at, note, idempotency_key, request_path, now)


def add_expense(
    db: Session, *, current_user: User, session_id: UUID, payload: ManualExpenseCreate, idempotency_key: str,
    request_path: str, now: datetime | None = None,
) -> SessionEntryResult:
    category, label = EXPENSE_CATEGORIES[payload.category]
    note = " · ".join(part for part in (label or "", (payload.note or "").strip()) if part) or None
    return _vault_entry(db, current_user, session_id, "expense", payload.amount_cents, category, payload.wallet,
                        payload.occurred_at, note, idempotency_key, request_path, now)


def add_drop_zone(
    db: Session, *, current_user: User, session_id: UUID, payload: DropZoneCreate, idempotency_key: str,
    now: datetime | None = None,
) -> tuple[DropZoneRead, bool]:
    fingerprint = food_stock.request_hash("rides.drop_zone", {"session_id": str(session_id), **payload.model_dump(mode="json")})
    existing = db.scalar(
        select(RidesDropZone).where(RidesDropZone.user_id == current_user.id, RidesDropZone.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise RidesIdempotencyConflictError("Idempotency key already used with a different drop zone.")
        return DropZoneRead.model_validate(existing), True
    session = _active(db, current_user, session_id)
    row = RidesDropZone(
        user_id=current_user.id, session_id=session.id, zone=payload.zone.strip(), latitude=payload.latitude,
        longitude=payload.longitude, gps_confidence=payload.gps_confidence, real_duration_minutes=payload.real_duration_minutes,
        recorded_at=now or datetime.now(UTC), idempotency_key=idempotency_key, request_hash=fingerprint,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    _event(db, current_user, "rides.drop_zone.recorded", session,
           {"drop_zone_id": str(row.id), "zone": row.zone, "real_duration_minutes": row.real_duration_minutes},
           ref=str(row.id))
    read = DropZoneRead.model_validate(row)
    db.commit()
    return read, False


def list_drop_zones(db: Session, *, current_user: User, session_id: UUID) -> list[DropZoneRead]:
    session = _get(db, current_user, session_id)
    rows = db.scalars(select(RidesDropZone).where(RidesDropZone.session_id == session.id).order_by(RidesDropZone.recorded_at))
    return [DropZoneRead.model_validate(row) for row in rows]


def _vault_entry(
    db: Session, user: User, session_id: UUID, kind: str, amount: int, category: str, wallet: str,
    occurred_at: datetime | None, note: str | None, idempotency_key: str, request_path: str, now: datetime | None,
) -> SessionEntryResult:
    now = now or datetime.now(UTC)
    session = _get(db, user, session_id)
    occurred_at = occurred_at or now
    if occurred_at.tzinfo is None:
        raise RidesInputError("L'heure doit préciser le fuseau.")
    if occurred_at > now + CLOCK_SKEW:
        raise RidesInputError("L'heure ne peut pas être dans le futur.")
    payload = ImperiumVaultTransactionCreate(
        transaction_type=kind, amount_cents=amount, wallet=wallet.strip(), occurred_at=occurred_at, timezone="Europe/Paris",
        category=category, source="vector_manual", note=note, external_ref=f"rides:{session.id}:{idempotency_key[:77]}",
    )
    if _key_used(db, user, idempotency_key):
        # Rejeu (l'heure par défaut a pu changer) : on rend la transaction déjà écrite pour cette session.
        transaction = db.scalar(
            select(ImperiumVaultTransaction).where(
                ImperiumVaultTransaction.user_id == user.id, ImperiumVaultTransaction.external_ref == payload.external_ref,
                ImperiumVaultTransaction.transaction_type == kind, ImperiumVaultTransaction.amount_cents == amount,
            )
        )
        if transaction is None:
            raise RidesIdempotencyConflictError("Idempotency key already used with a different request.")
        return SessionEntryResult(transaction_id=transaction.id, session=_read(db, session))
    if session.status != "active":
        raise RidesStateError("Cette session est close.", _read(db, session))
    transaction, _ = vault_transactions.create_vault_transaction(
        db, current_user=user, payload=payload, idempotency_key=idempotency_key, request_method="POST",
        request_path=request_path,
    )
    db.refresh(session)
    return SessionEntryResult(transaction_id=transaction.id, session=_read(db, session))


def _key_used(db: Session, user: User, idempotency_key: str) -> bool:
    return db.scalar(
        select(IdempotencyKey.id).where(IdempotencyKey.user_id == user.id, IdempotencyKey.idempotency_key == idempotency_key)
    ) is not None


# ---------- internes ----------

def _kpis(db: Session, session: RidesSession, now: datetime | None = None) -> SessionKpis:
    reversal = aliased(ImperiumVaultTransaction)
    rows = db.execute(
        select(ImperiumVaultTransaction.transaction_type, func.count(), func.coalesce(func.sum(ImperiumVaultTransaction.amount_cents), 0))
        .where(
            ImperiumVaultTransaction.user_id == session.user_id,
            ImperiumVaultTransaction.external_ref.like(f"rides:{session.id}:%"),
            ImperiumVaultTransaction.is_reversal.is_(False),
            ~select(reversal.id).where(reversal.reversal_of_transaction_id == ImperiumVaultTransaction.id).exists(),
        )
        .group_by(ImperiumVaultTransaction.transaction_type)
    ).all()
    figures = {kind: (count, int(total)) for kind, count, total in rows}
    revenue_entries, revenue = figures.get("income", (0, 0))
    expense_entries, expense = figures.get("expense", (0, 0))
    if session.status == "completed":
        revenue, expense = session.final_revenue_cents or 0, session.final_expense_cents or 0
    drops = db.scalar(select(func.count()).select_from(RidesDropZone).where(RidesDropZone.session_id == session.id)) or 0
    end = session.ended_at or now or datetime.now(UTC)
    target = session.target_ca_cents
    return SessionKpis(
        revenue_cents=revenue, expense_cents=expense, net_cents=revenue - expense, revenue_entries=revenue_entries,
        expense_entries=expense_entries, drop_zones=drops, elapsed_minutes=max(0, int((end - session.started_at).total_seconds() // 60)),
        target_progress=(Decimal(revenue) / Decimal(target)).quantize(Decimal("0.01")) if target else None,
        objective_reached=revenue >= target if target else None,
    )


def _read(db: Session, session: RidesSession, now: datetime | None = None) -> SessionRead:
    return SessionRead(
        id=session.id, status=session.status, started_at=session.started_at, ended_at=session.ended_at,
        target_ca_cents=session.target_ca_cents, strategic_direction=session.strategic_direction, mission_id=session.mission_id,
        review_note=session.review_note, version=session.version, kpis=_kpis(db, session, now),
    )


def _get(db: Session, user: User, session_id: UUID) -> RidesSession:
    session = db.scalar(
        select(RidesSession).where(RidesSession.id == session_id, RidesSession.user_id == user.id).with_for_update()
    )
    if session is None:
        raise RidesNotFoundError("Session introuvable.")
    return session


def _active(db: Session, user: User, session_id: UUID) -> RidesSession:
    session = _get(db, user, session_id)
    if session.status != "active":
        raise RidesStateError("Cette session est close.", _read(db, session))
    return session


def _event(db: Session, user: User, event_type: str, session: RidesSession, extra: dict, ref: str | None = None) -> None:
    db.add(
        build_event(
            db, user_id=user.id, event_type=event_type, payload={"session_id": str(session.id), **extra},
            idempotency_key=f"{event_type}.{ref or session.id}", source_app=SourceApp.vector, privacy_level=PrivacyLevel.high,
        )
    )
