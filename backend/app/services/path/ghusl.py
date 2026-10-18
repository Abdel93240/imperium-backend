"""Ghusl (doc 41 §10) : état requis posé et levé par l'utilisateur, mission Imperium, adresses.

Jamais déduit : seule l'action de l'utilisateur active ou termine (PAT-04). À l'activation,
l'état Path est enregistré d'abord, puis deux écritures du backend côté Imperium :
- la mission « Faire le ghusl avant {prière} » (backlog, domaine religieux, priorité 9) ;
- une demande de replanification `ghusl_required`, immédiate (hors délai, doc 43 §3.3).
Si l'une échoue (pas de journée ouverte, replanification déjà en cours), l'état reste
enregistré et la réponse le dit. « Ghusl fait » termine l'état et la mission, sans
nouvelle replanification.

Les événements ne portent que des identifiants (privacy very_high) ; les adresses
ne quittent pas Path, sauf pour la replanification qui les lit.
"""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.imperium import ImperiumMission
from app.models.path import PathGhuslAddress, PathGhuslState
from app.schemas.imperium import BacklogMissionCreateRequest
from app.schemas.path_ghusl import (
    GhuslAddressCreate,
    GhuslAddressListResponse,
    GhuslAddressRead,
    GhuslAddressUpdate,
    GhuslCompleteRequest,
    GhuslCurrentRead,
    GhuslStateRead,
)
from app.services.events.emitter import build_event
from app.services.imperium import missions, replan
from app.services.path.fasting import PARIS
from app.services.path.prayer import PRAYERS, prayer_times
from app.services.pulse import food_stock

logger = logging.getLogger(__name__)

PRAYER_LABELS = {"fajr": "Fajr", "dhuhr": "Dhuhr", "asr": "Asr", "maghrib": "Maghrib", "isha": "Isha"}
MISSION_PRIORITY = 9
OPEN_MISSION_STATUSES = ("backlog", "active", "standby")
MESSAGES = {
    "requested": "Ghusl requis : Imperium replanifie la journée.",
    "no_open_day": "Ghusl requis : mission créée. Aucune journée ouverte, pas de replanification.",
    "replan_in_progress": "Ghusl requis : mission créée. Une replanification est déjà en cours.",
    "failed": "Ghusl requis : enregistré. La mission ou la replanification n'a pas pu être créée.",
    "pending": "Ghusl requis.",
}


class GhuslStateError(ValueError):
    def __init__(self, message: str, current: GhuslStateRead | None = None) -> None:
        super().__init__(message)
        self.current = current


class GhuslNotFoundError(ValueError):
    pass


class GhuslIdempotencyConflictError(ValueError):
    pass


class GhuslAddressVersionConflictError(ValueError):
    def __init__(self, current: GhuslAddressRead) -> None:
        super().__init__("Cette adresse a changé depuis ta lecture.")
        self.current = current


# ---------- état ----------

def current(db: Session, *, current_user: User) -> GhuslCurrentRead:
    state = db.scalar(
        select(PathGhuslState).where(PathGhuslState.user_id == current_user.id).order_by(PathGhuslState.required_since.desc()).limit(1)
    )
    required = state is not None and state.status == "required"
    return GhuslCurrentRead(
        ghusl_required=required, state=GhuslStateRead.model_validate(state) if state else None,
        message=MESSAGES[state.replan_status] if required else None,
    )


def activate(
    db: Session, *, current_user: User, idempotency_key: str, now: datetime | None = None
) -> tuple[GhuslStateRead, bool]:
    fingerprint = food_stock.request_hash("path.ghusl.activate", {})
    existing = db.scalar(
        select(PathGhuslState).where(PathGhuslState.user_id == current_user.id, PathGhuslState.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return GhuslStateRead.model_validate(existing), True
    now = now or datetime.now(UTC)
    active = db.scalar(
        select(PathGhuslState).where(PathGhuslState.user_id == current_user.id, PathGhuslState.status == "required").with_for_update()
    )
    if active is not None:
        raise GhuslStateError("Le ghusl est déjà marqué comme requis.", GhuslStateRead.model_validate(active))
    prayer = next_prayer(db, now, current_user.id)
    state = PathGhuslState(
        user_id=current_user.id, status="required", required_since=now, next_prayer=prayer, replan_status="pending",
        idempotency_key=idempotency_key, request_hash=fingerprint,
    )
    db.add(state)
    db.flush()
    _event(db, current_user, "path.ghusl.required", {"ghusl_state_id": str(state.id), "required_since": now.isoformat()},
           state.id)
    db.commit()  # l'état Path est enregistré, quoi qu'il arrive côté Imperium
    state_id = state.id
    mission_id = _create_mission(db, current_user, state_id, prayer)
    replan_event_id, replan_status = _request_replan(db, current_user, now)
    state = db.get(PathGhuslState, state_id)
    state.mission_id = mission_id
    state.replan_event_id = replan_event_id
    state.replan_status = replan_status if mission_id is not None else "failed"
    db.commit()
    db.refresh(state)
    return GhuslStateRead.model_validate(state), False


def complete(
    db: Session, *, current_user: User, payload: GhuslCompleteRequest, idempotency_key: str, request_path: str,
    now: datetime | None = None,
) -> tuple[GhuslStateRead, bool]:
    fingerprint = food_stock.request_hash("path.ghusl.complete", payload.model_dump(mode="json"))
    previous = food_stock.replay(db, current_user, idempotency_key, fingerprint, request_path, GhuslStateRead)
    if previous is not None:
        return previous, True
    now = now or datetime.now(UTC)
    state = db.scalar(
        select(PathGhuslState).where(PathGhuslState.id == payload.state_id, PathGhuslState.user_id == current_user.id)
        .with_for_update()
    )
    if state is None:
        raise GhuslNotFoundError("Activation du ghusl introuvable.")
    if state.status != "required":
        raise GhuslStateError("Ce ghusl est déjà marqué comme fait.", GhuslStateRead.model_validate(state))
    state.status, state.completed_at = "completed", now
    mission_done = _finish_mission(db, current_user, state.mission_id, now)
    _event(db, current_user, "path.ghusl.completed",
           {"ghusl_state_id": str(state.id), "mission_id": str(state.mission_id) if state.mission_id else None,
            "mission_completed": mission_done}, state.id)
    db.flush()
    read = GhuslStateRead.model_validate(state)
    food_stock.remember(db, current_user, idempotency_key, "POST", request_path, fingerprint, 200, read)
    db.commit()
    return read, False


def next_prayer(db: Session, now: datetime, user_id: UUID | None = None) -> str:
    """Prochaine prière à partir de maintenant (fajr du lendemain après isha)."""
    today = now.astimezone(PARIS).date()
    adhans, _ = prayer_times(db, today, user_id=user_id)
    for name in PRAYERS:
        if adhans[name] > now:
            return name
    return "fajr"


def _create_mission(db: Session, user: User, state_id: UUID, prayer: str) -> UUID | None:
    try:
        response, _ = missions.create_backlog_mission(
            db, current_user=user,
            payload=BacklogMissionCreateRequest(
                title=f"Faire le ghusl avant {PRAYER_LABELS[prayer]}", category="ghusl", domain="religious",
                priority_level=MISSION_PRIORITY, estimated_minutes=30,
            ),
            idempotency_key=f"path.ghusl.mission.{state_id}", request_method="POST",
            request_path="/internal/path/ghusl/mission",
        )
    except Exception:  # noqa: BLE001 - l'état ghusl reste enregistré même sans mission
        db.rollback()
        logger.exception("Ghusl: création de la mission en échec.", extra={"ghusl_state_id": str(state_id)})
        return None
    return response.mission.id


def _request_replan(db: Session, user: User, now: datetime) -> tuple[UUID | None, str]:
    try:
        row = replan.request_hook_replan(db, current_user=user, hook_type="ghusl_required", now=now)
    except replan.ReplanStateConflictError as exc:
        db.rollback()
        return None, "no_open_day" if "No operational day" in str(exc) else "replan_in_progress"
    except Exception:  # noqa: BLE001 - même règle que la mission
        db.rollback()
        logger.exception("Ghusl: demande de replanification en échec.")
        return None, "failed"
    return row.id, "requested"


def _finish_mission(db: Session, user: User, mission_id: UUID | None, now: datetime) -> bool:
    """Imperium marque la mission « faite » (doc 41 §10.3) si elle est encore ouverte."""
    if mission_id is None:
        return False
    mission = db.scalar(
        select(ImperiumMission).where(ImperiumMission.id == mission_id, ImperiumMission.user_id == user.id).with_for_update()
    )
    if mission is None or mission.status not in OPEN_MISSION_STATUSES:
        return False
    event = build_event(
        db, user_id=user.id, event_type="mission.completed",
        payload={"mission_id": str(mission.id), "outcome": "completed", "reason": "Ghusl fait (Path)."},
        idempotency_key=f"path.ghusl.mission.completed.{mission.id}",
    )
    db.add(event)
    db.flush()
    mission.status, mission.ended_at, mission.completion_note = "completed", now, "Ghusl fait (Path)."
    mission.ended_by_event_id = event.id
    return True


def _event(db: Session, user: User, event_type: str, payload: dict, state_id: UUID) -> None:
    db.add(
        build_event(
            db, user_id=user.id, event_type=event_type, payload={**payload, "source": "user_action"},
            idempotency_key=f"{event_type}.{state_id}", source_app=SourceApp.path, privacy_level=PrivacyLevel.very_high,
        )
    )


# ---------- adresses ----------

def list_addresses(db: Session, *, current_user: User) -> GhuslAddressListResponse:
    rows = db.scalars(
        select(PathGhuslAddress).where(PathGhuslAddress.user_id == current_user.id)
        .order_by(PathGhuslAddress.is_default.desc(), PathGhuslAddress.created_at.asc())
    )
    return GhuslAddressListResponse(items=[GhuslAddressRead.model_validate(row) for row in rows])


def create_address(
    db: Session, *, current_user: User, payload: GhuslAddressCreate, idempotency_key: str
) -> tuple[GhuslAddressRead, bool]:
    fingerprint = food_stock.request_hash("path.ghusl.address", payload.model_dump(mode="json"))
    existing = db.scalar(
        select(PathGhuslAddress).where(PathGhuslAddress.user_id == current_user.id, PathGhuslAddress.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise GhuslIdempotencyConflictError("Idempotency key already used with a different address.")
        return GhuslAddressRead.model_validate(existing), True
    if payload.is_default:
        _clear_default(db, current_user)
    row = PathGhuslAddress(
        user_id=current_user.id, label=payload.label, address_type=payload.address_type,
        address_text=(payload.address_text or "").strip() or None, latitude=payload.latitude, longitude=payload.longitude,
        is_default=payload.is_default, version=1, idempotency_key=idempotency_key, request_hash=fingerprint,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    _address_event(db, current_user, row, "added")
    read = GhuslAddressRead.model_validate(row)
    db.commit()
    return read, False


def update_address(
    db: Session, *, current_user: User, address_id: UUID, payload: GhuslAddressUpdate, idempotency_key: str, request_path: str,
) -> GhuslAddressRead:
    fingerprint = food_stock.request_hash(
        "path.ghusl.address.update", {"address_id": str(address_id), **payload.model_dump(mode="json", exclude_unset=True)}
    )
    previous = food_stock.replay(db, current_user, idempotency_key, fingerprint, request_path, GhuslAddressRead)
    if previous is not None:
        return previous
    row = _get_address(db, current_user, address_id)
    if row.version != payload.version:
        raise GhuslAddressVersionConflictError(GhuslAddressRead.model_validate(row))
    changes = payload.model_dump(exclude_unset=True, exclude={"version"})
    if "label" in changes:
        if changes["label"] is None or not changes["label"].strip():
            raise GhuslStateError("Le libellé est obligatoire.")
        changes["label"] = changes["label"].strip()
    if "address_type" in changes and changes["address_type"] is None:
        raise GhuslStateError("Le type est obligatoire.")
    if "address_text" in changes:
        changes["address_text"] = (changes["address_text"] or "").strip() or None
    latitude = changes.get("latitude", row.latitude)
    longitude = changes.get("longitude", row.longitude)
    if (latitude is None) != (longitude is None):
        raise GhuslStateError("Latitude et longitude vont ensemble.")
    if changes.get("is_default"):
        _clear_default(db, current_user, keep=row.id)
    if changes.get("is_default") is None:
        changes.pop("is_default", None)
    for field, value in changes.items():
        setattr(row, field, value)
    row.version += 1
    db.flush()
    db.refresh(row)
    _address_event(db, current_user, row, "updated")
    read = GhuslAddressRead.model_validate(row)
    food_stock.remember(db, current_user, idempotency_key, "PATCH", request_path, fingerprint, 200, read)
    db.commit()
    return read


def delete_address(db: Session, *, current_user: User, address_id: UUID) -> None:
    row = _get_address(db, current_user, address_id)
    _address_event(db, current_user, row, "removed")
    db.delete(row)
    db.commit()


def _get_address(db: Session, user: User, address_id: UUID) -> PathGhuslAddress:
    row = db.scalar(
        select(PathGhuslAddress).where(PathGhuslAddress.id == address_id, PathGhuslAddress.user_id == user.id).with_for_update()
    )
    if row is None:
        raise GhuslNotFoundError("Adresse introuvable.")
    return row


def _clear_default(db: Session, user: User, keep: UUID | None = None) -> None:
    query = update(PathGhuslAddress).where(PathGhuslAddress.user_id == user.id, PathGhuslAddress.is_default.is_(True))
    if keep is not None:
        query = query.where(PathGhuslAddress.id != keep)
    db.execute(query.values(is_default=False, version=PathGhuslAddress.version + 1))
    db.flush()


def _address_event(db: Session, user: User, row: PathGhuslAddress, action: str) -> None:
    db.add(
        build_event(
            db, user_id=user.id, event_type="path.ghusl_address.updated",
            payload={"address_id": str(row.id), "action": action, "address_type": row.address_type},
            idempotency_key=f"path.ghusl_address.{action}.{row.id}.v{row.version}", source_app=SourceApp.path,
            privacy_level=PrivacyLevel.very_high,
        )
    )

