"""Hydratation Pulse (PUL-04, doc 40 §12, §8).

Un appui enregistre l'eau bue et la décompte du stock en même temps : lignes actives
dont le nom contient « eau », comptées en ml/cl/l, date limite la plus proche
d'abord. Une ligne vidée passe « consumed ». Pas assez d'eau en stock : l'eau bue
est quand même enregistrée, avec un avertissement (jamais de blocage).

Même Idempotency-Key + même contenu → même réponse ; contenu différent → conflit ;
clés distinctes → les quantités s'additionnent (fusion hors ligne, doc 40 §8).
Jeûne (Path) : un appui daté dans la fenêtre suhoor → iftar est refusé, sauf si l'eau
est permise de jour pour ce jeûne. Cible personnalisée (programme santé) : pas encore.
"""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.imperium import FoodStockItem, PulseHydrationLog
from app.schemas.pulse import FoodStockItemRead
from app.schemas.pulse_hydration import HydrationDayRead, HydrationLogCreate, HydrationLogRead, HydrationLogResult
from app.services.events.emitter import build_event
from app.services.path import fasting
from app.services.pulse import food_stock
from app.services.pulse.expiry import PARIS
from app.services.pulse.meals import convert
from app.services.pulse.pantry_scan import normalize_name

VOLUME_UNITS = ("ml", "cl", "l")
NO_TARGET = "Objectif personnalisé pas encore calculé."


class HydrationIdempotencyConflictError(ValueError):
    pass


class HydrationFastingError(ValueError):
    pass


def log_hydration(
    db: Session, *, current_user: User, payload: HydrationLogCreate, idempotency_key: str
) -> tuple[HydrationLogResult, bool]:
    fingerprint = food_stock.request_hash("pulse.hydration.log", payload.model_dump(mode="json"))
    existing = db.scalar(
        select(PulseHydrationLog).where(
            PulseHydrationLog.user_id == current_user.id, PulseHydrationLog.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise HydrationIdempotencyConflictError("Idempotency key already used with a different hydration log.")
        return HydrationLogResult.model_validate(existing.result), True
    logged_at = payload.logged_at or datetime.now(UTC)
    if blocked := fasting.hydration_blocked(db, current_user, logged_at):
        raise HydrationFastingError(blocked)
    log = PulseHydrationLog(
        user_id=current_user.id, amount_ml=payload.amount_ml, logged_at=logged_at,
        source=payload.source, idempotency_key=idempotency_key, request_hash=fingerprint,
    )
    touched, warnings = _decrement_water(db, current_user, payload.amount_ml) if payload.decrement_stock else ([], [])
    log.stock_decrement_applied = bool(touched)
    db.add(log)
    db.flush()
    for item in touched:
        db.refresh(item)
    db.refresh(log)
    result = HydrationLogResult(
        log=HydrationLogRead.model_validate(log), stock_items=[FoodStockItemRead.model_validate(i) for i in touched],
        warnings=warnings,
    )
    log.result = result.model_dump(mode="json")
    db.add(
        build_event(
            db, user_id=current_user.id, event_type="pulse.hydration.logged",
            payload={"hydration_log_id": str(log.id), "amount_ml": log.amount_ml, "logged_at": log.logged_at.isoformat(),
                     "source": log.source, "stock_decrement_applied": log.stock_decrement_applied},
            idempotency_key=f"pulse.hydration.logged.{log.id}", source_app=SourceApp.pulse, privacy_level=PrivacyLevel.medium,
        )
    )
    if touched:
        db.add(
            build_event(
                db, user_id=current_user.id, event_type="pulse.food_stock.updated",
                payload={"source": "hydration", "hydration_log_id": str(log.id),
                         "items_finished": sum(1 for item in touched if item.status == "consumed"),
                         "stock_item_ids": [str(item.id) for item in touched]},
                idempotency_key=f"pulse.food_stock.updated.hydration:{log.id}", source_app=SourceApp.pulse,
                privacy_level=PrivacyLevel.medium,
            )
        )
    db.commit()
    return result, False


def day_view(db: Session, *, current_user: User, day: date) -> HydrationDayRead:
    start = datetime.combine(day, time.min, tzinfo=PARIS)
    logs = list(
        db.scalars(
            select(PulseHydrationLog)
            .where(PulseHydrationLog.user_id == current_user.id, PulseHydrationLog.logged_at >= start,
                   PulseHydrationLog.logged_at < start + timedelta(days=1))
            .order_by(PulseHydrationLog.logged_at.asc())
        )
    )
    return HydrationDayRead(
        day=day, total_ml=sum(log.amount_ml for log in logs), logs=[HydrationLogRead.model_validate(log) for log in logs],
        target=None, target_message=NO_TARGET,
    )


def _decrement_water(db: Session, current_user: User, amount_ml: int) -> tuple[list[FoodStockItem], list[str]]:
    lines = [
        item for item in db.scalars(
            select(FoodStockItem)
            .where(FoodStockItem.user_id == current_user.id, FoodStockItem.status == "active")
            .order_by(FoodStockItem.expiry_date.asc().nulls_last(), FoodStockItem.created_at.asc())
            .with_for_update()
        )
        if "eau" in normalize_name(item.name)
    ]
    if not lines:
        return [], ["Pas d'eau en stock : rien n'est décompté."]
    volume = [item for item in lines if item.unit in VOLUME_UNITS]
    if not volume:
        return [], ["Eau comptée en pièces : décompte le stock à la main."]
    left = Decimal(amount_ml)
    touched = []
    for item in volume:
        available = convert(item.quantity, item.unit, "ml")
        if available > left:
            item.quantity = item.quantity - convert(left, "ml", item.unit)
            left = Decimal(0)
        else:
            item.status = "consumed"
            left -= available
        item.version += 1
        touched.append(item)
        if left == 0:
            break
    warnings = [f"Stock d'eau épuisé : {int(left)} ml non décomptés."] if left > 0 else []
    return touched, warnings
