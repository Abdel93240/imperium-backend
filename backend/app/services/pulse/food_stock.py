"""Stock alimentaire de Pulse (doc 40 §10.5, §11).

V1 : lecture du stock, ajout et modification manuels (PUL-12), et entrée des
articles alimentaires d'un ticket validé (passage Vault → Pulse, doc 42 §15.2).
Chaque achat est une ligne à part : deux paquets de riz achetés à des dates
différentes n'ont pas la même date limite. Scan du placard, chatbot, décompte après
repas : pas encore.

Mutations (doc 40 §7–§8) : Idempotency-Key obligatoire (même clé + même contenu →
même réponse ; contenu différent → conflit) ; une modification porte la version lue,
une version dépassée renvoie un conflit avec la ligne actuelle, jamais d'écrasement.
La quantité reste > 0 : une ligne finie passe « consumed », une erreur « removed ».
"""

import hashlib
import json
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import IdempotencyStatus, PrivacyLevel, SourceApp
from app.models.idempotency import IdempotencyKey
from app.models.imperium import FoodStockItem
from app.schemas.pulse import (
    FoodStockItemCreate,
    FoodStockItemRead,
    FoodStockItemUpdate,
    FoodStockLineIn,
    FoodStockListResponse,
)
from app.services.events.emitter import build_event


class FoodStockNotFoundError(ValueError):
    pass


class FoodStockIdempotencyConflictError(ValueError):
    pass


class FoodStockVersionConflictError(ValueError):
    def __init__(self, current: FoodStockItemRead) -> None:
        super().__init__("Stock item was changed since it was read.")
        self.current = current


def list_stock(db: Session, *, current_user: User, include_inactive: bool = False) -> FoodStockListResponse:
    query = select(FoodStockItem).where(FoodStockItem.user_id == current_user.id)
    if not include_inactive:
        query = query.where(FoodStockItem.status == "active")
    rows = db.scalars(
        query.order_by(FoodStockItem.expiry_date.asc().nulls_last(), FoodStockItem.created_at.desc())
    )
    return FoodStockListResponse(items=[FoodStockItemRead.model_validate(row) for row in rows])


def add_from_receipt(
    db: Session,
    *,
    current_user: User,
    receipt_ref: str,
    lines: list[FoodStockLineIn],
    confidence: Decimal | None,
) -> list[FoodStockItem]:
    """Écrit les lignes validées ; même ticket rejoué → rien en double (source_ref unique)."""
    if not lines:
        return []
    existing = set(
        db.scalars(
            select(FoodStockItem.source_ref).where(
                FoodStockItem.user_id == current_user.id, FoodStockItem.source_ref.like(f"{receipt_ref}:%")
            )
        )
    )
    created = []
    for index, line in enumerate(lines):
        source_ref = f"{receipt_ref}:{index}"
        if source_ref in existing:
            continue
        item = FoodStockItem(
            user_id=current_user.id,
            name=line.name,
            quantity=line.quantity,
            unit=line.unit,
            expiry_type=line.expiry_type,
            expiry_date=line.expiry_date,
            category="food",
            confidence=confidence,
            source="vault_receipt",
            source_ref=source_ref,
            status="active",
        )
        db.add(item)
        created.append(item)
    if created:
        db.flush()
        db.add(
            build_event(
                db,
                user_id=current_user.id,
                event_type="pulse.food_stock.updated",
                payload={"source": "vault_receipt", "source_ref": receipt_ref, "items_added": len(created),
                         "stock_item_ids": [str(item.id) for item in created]},
                idempotency_key=f"pulse.food_stock.updated.{receipt_ref}",
                source_app=SourceApp.pulse,
                privacy_level=PrivacyLevel.medium,
            )
        )
    return created


def create_item(
    db: Session, *, current_user: User, payload: FoodStockItemCreate, idempotency_key: str, request_path: str
) -> tuple[FoodStockItemRead, bool]:
    request_hash = _hash("pulse.food_stock.create", payload.model_dump(mode="json"))
    replay = _replay(db, current_user, idempotency_key, request_hash, request_path)
    if replay is not None:
        return replay, True
    item = FoodStockItem(
        user_id=current_user.id,
        name=payload.name,
        quantity=payload.quantity,
        unit=payload.unit,
        expiry_type=payload.expiry_type,
        expiry_date=payload.expiry_date,
        category=payload.category,
        source="manual",
        status="active",
        version=1,
    )
    db.add(item)
    db.flush()
    db.refresh(item)  # quantité relue telle que stockée (2.000), comme dans la liste
    read = FoodStockItemRead.model_validate(item)
    _emit_manual(db, current_user, item, "created")
    _remember(db, current_user, idempotency_key, "POST", request_path, request_hash, 201, read)
    db.commit()
    return read, False


def update_item(
    db: Session,
    *,
    current_user: User,
    item_id: UUID,
    payload: FoodStockItemUpdate,
    idempotency_key: str,
    request_path: str,
) -> FoodStockItemRead:
    request_hash = _hash("pulse.food_stock.update", {"item_id": str(item_id), **payload.model_dump(mode="json", exclude_unset=True)})
    replay = _replay(db, current_user, idempotency_key, request_hash, request_path)
    if replay is not None:
        return replay
    item = db.get(FoodStockItem, item_id, with_for_update=True)
    if item is None or item.user_id != current_user.id:
        raise FoodStockNotFoundError("Stock item not found.")
    if item.version != payload.version:
        raise FoodStockVersionConflictError(FoodStockItemRead.model_validate(item))
    changes = payload.model_dump(exclude_unset=True, exclude={"version"})
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    for field, value in changes.items():
        setattr(item, field, value)
    item.version += 1
    db.flush()
    db.refresh(item)
    read = FoodStockItemRead.model_validate(item)
    action = changes.get("status") if changes.get("status") in ("consumed", "removed") else "updated"
    _emit_manual(db, current_user, item, action, fields=sorted(changes))
    _remember(db, current_user, idempotency_key, "PATCH", request_path, request_hash, 200, read)
    db.commit()
    return read


def _emit_manual(db: Session, current_user: User, item: FoodStockItem, action: str, fields: list[str] | None = None) -> None:
    db.add(
        build_event(
            db,
            user_id=current_user.id,
            event_type="pulse.food_stock.updated",
            payload={"source": "manual", "action": action, "stock_item_id": str(item.id), "version": item.version,
                     **({"fields": fields} if fields else {})},
            idempotency_key=f"pulse.food_stock.updated.{item.id}.v{item.version}",
            source_app=SourceApp.pulse,
            privacy_level=PrivacyLevel.medium,
        )
    )


def _hash(namespace: str, payload: dict) -> str:
    return hashlib.sha256(json.dumps({"ns": namespace, "payload": payload}, sort_keys=True).encode()).hexdigest()


def _replay(
    db: Session, current_user: User, idempotency_key: str, request_hash: str, request_path: str
) -> FoodStockItemRead | None:
    existing = db.scalar(
        select(IdempotencyKey).where(IdempotencyKey.user_id == current_user.id, IdempotencyKey.idempotency_key == idempotency_key)
    )
    if existing is None:
        return None
    if existing.request_path != request_path or existing.request_hash != request_hash:
        raise FoodStockIdempotencyConflictError("Idempotency key already used with a different request.")
    if existing.response_body is None:
        raise FoodStockIdempotencyConflictError("Idempotency key is already processing.")
    return FoodStockItemRead.model_validate(existing.response_body)


def _remember(
    db: Session, current_user: User, idempotency_key: str, method: str, path: str, request_hash: str, code: int,
    read: FoodStockItemRead,
) -> None:
    db.add(
        IdempotencyKey(
            user_id=current_user.id,
            idempotency_key=idempotency_key,
            request_method=method,
            request_path=path,
            request_hash=request_hash,
            status=IdempotencyStatus.completed,
            response_status_code=code,
            response_body=read.model_dump(mode="json"),
        )
    )
