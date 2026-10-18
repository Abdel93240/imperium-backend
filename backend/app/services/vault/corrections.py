"""Corrections manuelles de la pression (doc 11 « Manual Correction »).

L'utilisateur marque une échéance reportée (elle compte à sa nouvelle date) ou déjà réglée
(elle sort du calcul), ou une semaine exceptionnelle (ses jours sortent de la capacité
réaliste). Chaque correction : un événement finance.pressure.corrected, un nouvel instantané
de pression, visible dans l'explication (factors.manual_corrections). Journal en ajout seul :
une correction se révoque, l'échéance d'origine n'est jamais modifiée.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.vault import UpcomingExpense, VaultPressureCorrection
from app.schemas.vault import (
    PressureCorrectionCreate,
    PressureCorrectionRead,
    PressureCorrectionResult,
    VaultPressureResponse,
)
from app.services.events.emitter import build_event
from app.services.pulse import food_stock
from app.services.vault.pressure import compute_pressure_from_db


class CorrectionNotFoundError(ValueError):
    pass


class CorrectionStateError(ValueError):
    pass


class CorrectionIdempotencyConflictError(ValueError):
    pass


def list_corrections(db: Session, *, current_user: User, include_revoked: bool = False) -> list[PressureCorrectionRead]:
    query = select(VaultPressureCorrection).where(VaultPressureCorrection.user_id == current_user.id)
    if not include_revoked:
        query = query.where(VaultPressureCorrection.revoked_at.is_(None))
    rows = db.scalars(query.order_by(VaultPressureCorrection.created_at.desc(), VaultPressureCorrection.id))
    return [PressureCorrectionRead.model_validate(row) for row in rows]


def create_correction(
    db: Session, *, current_user: User, payload: PressureCorrectionCreate, idempotency_key: str
) -> tuple[PressureCorrectionResult, bool]:
    fingerprint = food_stock.request_hash("vault.pressure.correction", payload.model_dump(mode="json"))
    existing = db.scalar(
        select(VaultPressureCorrection).where(
            VaultPressureCorrection.user_id == current_user.id, VaultPressureCorrection.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise CorrectionIdempotencyConflictError("Idempotency key already used with a different correction.")
        return _result(db, current_user, existing, recompute=False), True
    if payload.upcoming_expense_id is not None:
        expense = db.scalar(
            select(UpcomingExpense).where(
                UpcomingExpense.id == payload.upcoming_expense_id, UpcomingExpense.user_id == current_user.id
            )
        )
        if expense is None:
            raise CorrectionNotFoundError("Échéance introuvable.")
        if not expense.active:
            raise CorrectionStateError("Cette échéance n'est plus active.")
        if payload.kind == "postponed" and payload.postponed_until <= expense.due_date:
            raise CorrectionStateError("La nouvelle date doit être après l'échéance.")
        active = db.scalar(
            select(VaultPressureCorrection.id).where(
                VaultPressureCorrection.upcoming_expense_id == expense.id, VaultPressureCorrection.revoked_at.is_(None)
            )
        )
        if active is not None:
            raise CorrectionStateError("Cette échéance a déjà une correction active : révoque-la d'abord.")
    else:
        active = db.scalar(
            select(VaultPressureCorrection.id).where(
                VaultPressureCorrection.user_id == current_user.id, VaultPressureCorrection.week_start == payload.week_start,
                VaultPressureCorrection.revoked_at.is_(None),
            )
        )
        if active is not None:
            raise CorrectionStateError("Cette semaine est déjà marquée exceptionnelle.")
    row = VaultPressureCorrection(user_id=current_user.id, **payload.model_dump(), idempotency_key=idempotency_key,
                                  request_hash=fingerprint)
    db.add(row)
    db.flush()
    db.refresh(row)
    return _result(db, current_user, row, recompute=True, action="created"), False


def revoke_correction(db: Session, *, current_user: User, correction_id: UUID) -> PressureCorrectionResult:
    row = db.scalar(
        select(VaultPressureCorrection).where(
            VaultPressureCorrection.id == correction_id, VaultPressureCorrection.user_id == current_user.id
        ).with_for_update()
    )
    if row is None:
        raise CorrectionNotFoundError("Correction introuvable.")
    if row.revoked_at is not None:
        return _result(db, current_user, row, recompute=False)
    row.revoked_at = datetime.now(UTC)
    db.flush()
    return _result(db, current_user, row, recompute=True, action="revoked")


def _result(
    db: Session, user: User, row: VaultPressureCorrection, *, recompute: bool, action: str | None = None
) -> PressureCorrectionResult:
    from app.services.vault.pressure import latest_pressure_snapshot

    read = PressureCorrectionRead.model_validate(row)
    if recompute:
        event = build_event(
            db, user_id=user.id, event_type="finance.pressure.corrected",
            payload={"correction_id": str(row.id), "kind": row.kind, "action": action,
                     "upcoming_expense_id": str(row.upcoming_expense_id) if row.upcoming_expense_id else None,
                     "week_start": row.week_start.isoformat() if row.week_start else None},
            idempotency_key=f"vault.pressure.correction.{action}.{row.id}", source_app=SourceApp.vault,
            privacy_level=PrivacyLevel.high,
        )
        db.add(event)
        db.flush()
        snapshot = compute_pressure_from_db(db, current_user=user, causation_event_id=event.event_id)  # commit
    else:
        snapshot = latest_pressure_snapshot(db, current_user=user) or compute_pressure_from_db(db, current_user=user)
    return PressureCorrectionResult(
        correction=read,
        pressure=VaultPressureResponse(score=snapshot.score, label=snapshot.label, daily_targets=snapshot.daily_targets,
                                       computed_at=snapshot.computed_at),
    )
