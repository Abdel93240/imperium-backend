"""Matériel possédé Pulse (doc 40 §13-EQUIP).

L'utilisateur ajoute ou retire son matériel (haltères, planche à pompes,
élastiques…). Un même nom, sans accents ni casse, n'est actif qu'une fois : le
rajouter renvoie la ligne existante. Retirer passe la ligne « removed » (jamais
supprimée). C'est une entrée du futur programme de séances (modes 1 et 3).
"""

import unicodedata
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.imperium import PulseOwnedEquipment
from app.schemas.pulse_workouts import EquipmentCreate, EquipmentListResponse, EquipmentRead, EquipmentUpdate
from app.services.events.emitter import build_event


class EquipmentNotFoundError(ValueError):
    pass


class EquipmentNameTakenError(ValueError):
    pass


def name_key(name: str) -> str:
    ligatures = name.replace("œ", "oe").replace("Œ", "Oe").replace("æ", "ae").replace("Æ", "Ae")
    folded = unicodedata.normalize("NFKD", ligatures).encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(folded.split())


def list_equipment(db: Session, *, current_user: User) -> EquipmentListResponse:
    rows = db.scalars(
        select(PulseOwnedEquipment)
        .where(PulseOwnedEquipment.user_id == current_user.id, PulseOwnedEquipment.status == "active")
        .order_by(PulseOwnedEquipment.name_key.asc())
    )
    return EquipmentListResponse(items=[EquipmentRead.model_validate(row) for row in rows])


def add_equipment(db: Session, *, current_user: User, payload: EquipmentCreate) -> tuple[EquipmentRead, bool]:
    key = name_key(payload.name)
    existing = _active(db, current_user, key)
    if existing is not None:
        return EquipmentRead.model_validate(existing), True
    item = PulseOwnedEquipment(
        user_id=current_user.id, name=payload.name, name_key=key, notes=(payload.notes or "").strip() or None, status="active"
    )
    db.add(item)
    try:
        db.flush()
    except IntegrityError:  # même nom ajouté au même moment par une autre requête
        db.rollback()
        return EquipmentRead.model_validate(_active(db, current_user, key)), True
    db.refresh(item)
    _emit(db, current_user, item, "added")
    read = EquipmentRead.model_validate(item)
    db.commit()
    return read, False


def remove_equipment(db: Session, *, current_user: User, equipment_id: UUID) -> EquipmentRead:
    item = db.get(PulseOwnedEquipment, equipment_id, with_for_update=True)
    if item is None or item.user_id != current_user.id:
        raise EquipmentNotFoundError("Equipment not found.")
    if item.status == "active":
        item.status = "removed"
        item.removed_at = datetime.now(UTC)
        _emit(db, current_user, item, "removed")
        db.flush()
    read = EquipmentRead.model_validate(item)
    db.commit()
    return read


def update_equipment(db: Session, *, current_user: User, equipment_id: UUID, payload: EquipmentUpdate) -> EquipmentRead:
    """Nom et note remplacés ; un nom déjà porté par un autre matériel actif est refusé."""
    item = db.get(PulseOwnedEquipment, equipment_id, with_for_update=True)
    if item is None or item.user_id != current_user.id or item.status != "active":
        raise EquipmentNotFoundError("Equipment not found.")
    key = name_key(payload.name)
    other = _active(db, current_user, key)
    if other is not None and other.id != item.id:
        raise EquipmentNameTakenError("Another equipment already has this name.")
    notes = (payload.notes or "").strip() or None
    if (item.name, item.notes) != (payload.name, notes):
        item.name, item.name_key, item.notes = payload.name, key, notes
        db.flush()
        db.add(
            build_event(
                db, user_id=current_user.id, event_type="pulse.equipment.updated",
                payload={"equipment_id": str(item.id), "action": "renamed", "name": item.name},
                idempotency_key=f"pulse.equipment.updated.{item.id}.renamed.{uuid4()}",
                source_app=SourceApp.pulse, privacy_level=PrivacyLevel.low,
            )
        )
    read = EquipmentRead.model_validate(item)
    db.commit()
    return read


def _active(db: Session, current_user: User, key: str) -> PulseOwnedEquipment | None:
    return db.scalar(
        select(PulseOwnedEquipment).where(
            PulseOwnedEquipment.user_id == current_user.id, PulseOwnedEquipment.name_key == key,
            PulseOwnedEquipment.status == "active",
        )
    )


def _emit(db: Session, current_user: User, item: PulseOwnedEquipment, action: str) -> None:
    db.add(
        build_event(
            db, user_id=current_user.id, event_type="pulse.equipment.updated",
            payload={"equipment_id": str(item.id), "action": action, "name": item.name},
            idempotency_key=f"pulse.equipment.updated.{item.id}.{action}", source_app=SourceApp.pulse,
            privacy_level=PrivacyLevel.low,
        )
    )
