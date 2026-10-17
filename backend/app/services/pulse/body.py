"""Relevé corporel Pulse (PUL-08, doc 40 §14) sous consentement « body ».

Mesures seulement (aucune photo côté serveur), progression montrée telle quelle,
sans interprétation ni conclusion médicale. Les événements ne portent que des
identifiants : supprimer un relevé ne laisse aucune mesure ailleurs. Suppression
réelle, ligne par ligne ou tout d'un coup (confirmation demandée).

Note : rejouer une Idempotency-Key après suppression recrée le relevé (aucune trace
gardée d'un relevé supprimé).
"""

from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.imperium import PulseBodySnapshot
from app.schemas.pulse_health import BodySnapshotCreate, BodySnapshotListResponse, BodySnapshotRead
from app.services.events.emitter import build_event
from app.services.pulse import food_stock, health_consent

MAX_ITEMS = 500


class BodySnapshotNotFoundError(ValueError):
    pass


class BodyIdempotencyConflictError(ValueError):
    pass


def create_snapshot(
    db: Session, *, current_user: User, payload: BodySnapshotCreate, idempotency_key: str
) -> tuple[BodySnapshotRead, bool]:
    fingerprint = food_stock.request_hash("pulse.body_snapshot.create", payload.model_dump(mode="json"))
    existing = db.scalar(
        select(PulseBodySnapshot).where(
            PulseBodySnapshot.user_id == current_user.id, PulseBodySnapshot.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise BodyIdempotencyConflictError("Idempotency key already used with a different snapshot.")
        return BodySnapshotRead.model_validate(existing), True
    health_consent.require(db, current_user, "body")
    snapshot = PulseBodySnapshot(
        user_id=current_user.id, **payload.model_dump(exclude={"notes"}), notes=(payload.notes or "").strip() or None,
        idempotency_key=idempotency_key, request_hash=fingerprint,
    )
    db.add(snapshot)
    db.flush()
    db.refresh(snapshot)
    _emit(db, current_user, "pulse.body_snapshot.created", {"snapshot_id": str(snapshot.id)}, str(snapshot.id))
    read = BodySnapshotRead.model_validate(snapshot)
    db.commit()
    return read, False


def list_snapshots(db: Session, *, current_user: User) -> BodySnapshotListResponse:
    rows = list(
        db.scalars(
            select(PulseBodySnapshot)
            .where(PulseBodySnapshot.user_id == current_user.id)
            .order_by(PulseBodySnapshot.measured_at.desc())
            .limit(MAX_ITEMS)
        )
    )
    weights = [row.weight_kg for row in rows if row.weight_kg is not None]
    return BodySnapshotListResponse(
        items=[BodySnapshotRead.model_validate(row) for row in rows],
        weight_change_kg=weights[0] - weights[-1] if len(weights) > 1 else None,
    )


def delete_snapshot(db: Session, *, current_user: User, snapshot_id: UUID) -> None:
    snapshot = db.get(PulseBodySnapshot, snapshot_id)
    if snapshot is None or snapshot.user_id != current_user.id:
        raise BodySnapshotNotFoundError("Snapshot not found.")
    db.delete(snapshot)
    _emit(db, current_user, "pulse.body_snapshot.deleted", {"deleted": 1, "scope": "one"}, str(snapshot_id))
    db.commit()


def delete_all(db: Session, *, current_user: User) -> int:
    deleted = db.execute(delete(PulseBodySnapshot).where(PulseBodySnapshot.user_id == current_user.id)).rowcount or 0
    if deleted:
        db.flush()
        _emit(db, current_user, "pulse.body_snapshot.deleted", {"deleted": deleted, "scope": "all"}, None)
    db.commit()
    return deleted


def _emit(db: Session, current_user: User, event_type: str, payload: dict, ref: str | None) -> None:
    db.add(
        build_event(
            db, user_id=current_user.id, event_type=event_type, payload=payload,
            idempotency_key=f"{event_type}.{ref or uuid4()}", source_app=SourceApp.pulse,
            privacy_level=PrivacyLevel.high,
        )
    )
