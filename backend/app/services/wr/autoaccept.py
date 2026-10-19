"""Classes d'auto-acceptation du docket (spec WR §9 P4, §13.8).

La table naît vide : seul l'utilisateur active une classe (item_type, domaine éventuel, slot IA,
confiance minimale, raison). Au dépôt, un item non rouge qui remplit une classe active — confiance
>= min_confidence ET agreement du slot >= cible sur les dernières semaines closes (audit_loop) — est
validé d'office ; `wr.spotcheck_pct` % de ces items (tirage déterministe sur l'id) sont re-présentés
en `autoaccept_spotcheck`. Un refus de contrôle est un label, il ne désactive rien tout seul.
"""

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import IdempotencyStatus, PrivacyLevel, SourceApp
from app.models.idempotency import IdempotencyKey
from app.models.wr import WrAutoacceptClass, WrDocketItem
from app.schemas.wr import AutoacceptClassCreateRequest, AutoacceptClassRead
from app.services.ai import audit_loop
from app.services.events.emitter import build_event
from app.services.params import get_parameter


class AutoacceptClassNotFoundError(LookupError):
    pass


class AutoacceptStateError(RuntimeError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def matching_class(db: Session, item: WrDocketItem, *, now: datetime) -> WrAutoacceptClass | None:
    if item.severity == "red" or item.confidence is None:
        return None
    candidates = db.scalars(
        select(WrAutoacceptClass)
        .where(WrAutoacceptClass.user_id == item.user_id, WrAutoacceptClass.enabled.is_(True),
               WrAutoacceptClass.item_type == item.item_type,
               or_(WrAutoacceptClass.domain.is_(None), WrAutoacceptClass.domain == item.domain),
               WrAutoacceptClass.min_confidence <= item.confidence)
        .order_by(WrAutoacceptClass.domain.is_(None), WrAutoacceptClass.created_at)  # le domaine précis d'abord
    )
    for candidate in candidates:
        if audit_loop.agreement_holds(db, slot_code=candidate.slot_code, now=now):
            return candidate
    return None


def in_spotcheck(db: Session, item_id: UUID) -> bool:
    pct = float(get_parameter(db, "wr.spotcheck_pct", default=10))
    return int(hashlib.sha256(f"wr.spotcheck:{item_id}".encode()).hexdigest()[:8], 16) % 100 < pct


def list_classes(db: Session, *, current_user: User, now: datetime | None = None) -> list[AutoacceptClassRead]:
    now = now or datetime.now(UTC)
    rows = db.scalars(
        select(WrAutoacceptClass).where(WrAutoacceptClass.user_id == current_user.id)
        .order_by(WrAutoacceptClass.enabled.desc(), WrAutoacceptClass.created_at.desc())
    ).all()
    counts: dict[tuple[UUID, str, str], int] = {
        (class_id, item_type, status): count
        for class_id, item_type, status, count in db.execute(
            select(WrDocketItem.autoaccept_class_id, WrDocketItem.item_type, WrDocketItem.status, func.count())
            .where(WrDocketItem.user_id == current_user.id, WrDocketItem.autoaccept_class_id.is_not(None))
            .group_by(WrDocketItem.autoaccept_class_id, WrDocketItem.item_type, WrDocketItem.status)
        )
    }
    reads = []
    for row in rows:
        read = AutoacceptClassRead.model_validate(row)
        read.agreement_holds = audit_loop.agreement_holds(db, slot_code=row.slot_code, now=now)
        read.auto_accepted = sum(count for (cid, item_type, _), count in counts.items()
                                 if cid == row.id and item_type != "autoaccept_spotcheck")
        read.spotchecks_validated = counts.get((row.id, "autoaccept_spotcheck", "validated"), 0)
        read.spotchecks_refused = counts.get((row.id, "autoaccept_spotcheck", "refused"), 0)
        reads.append(read)
    return reads


def create_class(
    db: Session,
    *,
    current_user: User,
    request: AutoacceptClassCreateRequest,
    idempotency_key: str,
    request_path: str,
    now: datetime | None = None,
) -> AutoacceptClassRead:
    fingerprint = hashlib.sha256(
        json.dumps({"ns": "wr.autoaccept.create", **request.model_dump(mode="json")}, sort_keys=True).encode()
    ).hexdigest()
    previous = db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == current_user.id, IdempotencyKey.idempotency_key == idempotency_key
        )
    )
    if previous is not None:
        if previous.request_path != request_path or previous.request_hash != fingerprint or previous.response_body is None:
            raise AutoacceptStateError("Idempotency key already used with a different request.", "IDEMPOTENCY_CONFLICT")
        return AutoacceptClassRead.model_validate(previous.response_body)

    now = now or datetime.now(UTC)
    audit_loop.agreement_holds(db, slot_code=request.slot_code, now=now)  # UnknownSlotError si le slot n'existe pas
    row = WrAutoacceptClass(user_id=current_user.id, created_at=now, enabled=True, **request.model_dump())
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError as exc:
        raise AutoacceptStateError("An enabled class already covers this item type and domain.",
                                   "AUTOACCEPT_CLASS_EXISTS") from exc
    _emit(db, current_user, "planning.docket.autoaccept_class_enabled", row, now)
    read = list_classes(db, current_user=current_user, now=now)
    read = next(entry for entry in read if entry.id == row.id)
    db.add(IdempotencyKey(
        user_id=current_user.id, idempotency_key=idempotency_key, request_method="POST", request_path=request_path,
        request_hash=fingerprint, status=IdempotencyStatus.completed, response_status_code=201,
        response_body=read.model_dump(mode="json"),
    ))
    db.commit()
    return read


def disable_class(
    db: Session, *, current_user: User, class_id: UUID, now: datetime | None = None
) -> AutoacceptClassRead:
    """Désactive une classe ; déjà désactivée, la rend telle quelle (rien n'est émis)."""
    now = now or datetime.now(UTC)
    row = db.get(WrAutoacceptClass, class_id, with_for_update=True)
    if row is None or row.user_id != current_user.id:
        raise AutoacceptClassNotFoundError("Auto-accept class not found.")
    if row.enabled:
        row.enabled = False
        row.disabled_at = now
        db.flush()
        _emit(db, current_user, "planning.docket.autoaccept_class_disabled", row, now)
    db.commit()
    return next(entry for entry in list_classes(db, current_user=current_user, now=now) if entry.id == row.id)


def _emit(db: Session, current_user: User, event_type: str, row: WrAutoacceptClass, now: datetime) -> None:
    db.add(build_event(
        db, user_id=current_user.id, event_type=event_type,
        payload={"class_id": str(row.id), "item_type": row.item_type, "domain": row.domain,
                 "slot_code": row.slot_code, "min_confidence": row.min_confidence},
        idempotency_key=f"{event_type}.{row.id}", source_app=SourceApp.imperium,
        privacy_level=PrivacyLevel.low, occurred_at=now,
    ))
    db.flush()
