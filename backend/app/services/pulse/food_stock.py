"""Stock alimentaire de Pulse (doc 40 §10.5, §11).

V1 : lecture du stock et entrée des articles alimentaires d'un ticket validé
(passage Vault → Pulse, doc 42 §15.2). Chaque achat est une ligne à part : deux
paquets de riz achetés à des dates différentes n'ont pas la même date limite.
Ajout manuel, scan du placard, décompte après repas : pas encore.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.imperium import FoodStockItem
from app.schemas.pulse import FoodStockItemRead, FoodStockLineIn, FoodStockListResponse
from app.services.events.emitter import build_event


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
