"""Repas Pulse (PUL-02/PUL-03, doc 40 §10.1–§10.3, §8).

Saisie (texte tapé ou dicté) → brouillon : macros saisies ou vides, proposition de
décompte du stock lue sans IA dans la description (« 200 g de riz et 2 œufs »).
Rien n'est écrit au stock avant la validation, qui ne décompte que les lignes
cochées, une seule fois (`stock_decrement_applied`, même clé → même réponse).

Décompte : la quantité est convertie dans l'unité de la ligne de stock (g/kg,
ml/cl/l ; la pièce ne se convertit pas). Tout utiliser, ou plus que le reste, exige
`finish` : la ligne passe alors « consumed » ; sinon conflit, rien n'est écrit.
Photo du repas : meal_photo (macros estimées, toujours à valider). Estimation depuis le
texte : pas encore.
"""

import re
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.imperium import FoodStockItem, PulseMeal
from app.schemas.pulse import FoodStockItemRead
from app.schemas.pulse_meals import (
    MealConfirmRequest,
    MealDayRead,
    MealDraftCreate,
    MealRead,
    MealStockLineRead,
    MealTotalsRead,
)
from app.services.events.emitter import build_event
from app.services.pulse import food_stock
from app.services.pulse.expiry import PARIS
from app.services.pulse.pantry_scan import match_stock, normalize_name
from app.services.pulse.stock_declaration import DeclaredLine, parse_declaration

MACROS = ("calories", "protein_g", "carbs_g", "fat_g")
NO_MACROS = "Macros non estimées automatiquement : saisis-les pour le suivi."
_UNITS = {"g": ("mass", 1), "kg": ("mass", 1000), "ml": ("volume", 1), "cl": ("volume", 10), "l": ("volume", 1000),
          "piece": ("piece", 1)}
_MEAL_PREFIX = re.compile(
    r"^(?:j'ai\s+(?:mangé|mange|bu|pris)|mangé|bu|repas|petit[-\s]déjeuner|déjeuner|dîner|diner|goûter|gouter|"
    r"collation)\s*:?\s*",
    re.IGNORECASE,
)
_WITH = re.compile(r"\s+(?:avec|accompagnée?s?\s+de|sur)\s+", re.IGNORECASE)


class MealNotFoundError(ValueError):
    pass


class MealStateError(ValueError):
    pass


class MealIdempotencyConflictError(ValueError):
    pass


class MealUnitError(ValueError):
    pass


class MealStockInsufficientError(ValueError):
    def __init__(self, current: FoodStockItemRead) -> None:
        super().__init__("Not enough stock left: confirm with finish to mark the line consumed.")
        self.current = current


def convert(quantity: Decimal, unit: str, target: str) -> Decimal | None:
    """Quantité exprimée dans l'unité cible, ou None si les unités ne se convertissent pas."""
    (family, factor), (target_family, target_factor) = _UNITS[unit], _UNITS[target]
    if family != target_family:
        return None
    return (quantity * factor / target_factor).quantize(Decimal("0.001")) if factor != target_factor else quantity


def create_draft(
    db: Session, *, current_user: User, payload: MealDraftCreate, idempotency_key: str
) -> tuple[MealRead, bool]:
    fingerprint = food_stock.request_hash("pulse.meal.draft", payload.model_dump(mode="json"))
    previous = find_draft(db, current_user, idempotency_key, fingerprint)
    if previous is not None:
        return previous, True
    macros = {macro: getattr(payload, macro) for macro in MACROS}
    lines, warnings = propose(db, current_user, [(line, False) for line in _declared(payload.description)])
    if all(value is None for value in macros.values()):
        warnings.insert(0, NO_MACROS)
    meal = PulseMeal(
        user_id=current_user.id, status="draft", label=payload.label or payload.description[:120],
        description=payload.description, source=payload.source, eaten_at=payload.eaten_at or datetime.now(UTC),
        **macros, proposal=[line.model_dump(mode="json") for line in lines], warnings=warnings[:20],
        idempotency_key=idempotency_key, request_hash=fingerprint,
    )
    return save_draft(db, meal), False


def find_draft(db: Session, current_user: User, idempotency_key: str, fingerprint: str) -> MealRead | None:
    """Brouillon déjà créé avec cette clé ; même clé + contenu différent → conflit."""
    existing = db.scalar(select(PulseMeal).where(PulseMeal.user_id == current_user.id, PulseMeal.idempotency_key == idempotency_key))
    if existing is None:
        return None
    if existing.request_hash != fingerprint:
        raise MealIdempotencyConflictError("Idempotency key already used with a different meal.")
    return _read(existing)


def save_draft(db: Session, meal: PulseMeal) -> MealRead:
    db.add(meal)
    db.flush()
    db.refresh(meal)
    read = _read(meal)
    db.commit()
    return read


def get_meal(db: Session, *, current_user: User, meal_id: UUID) -> MealRead:
    return _read(_get(db, current_user, meal_id))


def confirm_meal(
    db: Session, *, current_user: User, meal_id: UUID, payload: MealConfirmRequest, idempotency_key: str
) -> MealRead:
    fingerprint = food_stock.request_hash("pulse.meal.confirm", {"meal_id": str(meal_id), **payload.model_dump(mode="json")})
    meal = _get(db, current_user, meal_id, lock=True)
    if meal.status == "confirmed":
        if meal.confirm_idempotency_key != idempotency_key:
            raise MealStateError("Meal already confirmed.")
        if meal.confirm_request_hash != fingerprint:
            raise MealIdempotencyConflictError("Idempotency key already used with a different confirmation.")
        return _read(meal)
    if meal.status != "draft":
        raise MealStateError("Only a draft meal can be confirmed.")
    touched: list[FoodStockItem] = []
    finished = 0
    for line in payload.stock_lines:
        item = db.get(FoodStockItem, line.stock_item_id, with_for_update=True)
        if item is None or item.user_id != current_user.id or item.status != "active":
            db.rollback()
            raise MealNotFoundError("Stock item not found.")
        used = convert(line.quantity, line.unit, item.unit)
        if used is None:
            db.rollback()
            raise MealUnitError(f"« {item.name} » est compté en {item.unit} : impossible de décompter en {line.unit}.")
        if line.finish:
            item.status = "consumed"
            finished += 1
        elif used >= item.quantity:
            current = FoodStockItemRead.model_validate(item)
            db.rollback()
            raise MealStockInsufficientError(current)
        else:
            item.quantity = item.quantity - used
        item.version += 1
        touched.append(item)
    for field in ("label", "eaten_at", *MACROS):
        if field in payload.model_fields_set:
            setattr(meal, field, getattr(payload, field))
    db.flush()
    for item in touched:
        db.refresh(item)
    meal.status = "confirmed"
    meal.confirmed_at = datetime.now(UTC)
    meal.stock_decrement_applied = bool(touched)
    meal.result = {"stock_items": [FoodStockItemRead.model_validate(item).model_dump(mode="json") for item in touched]}
    meal.confirm_idempotency_key, meal.confirm_request_hash = idempotency_key, fingerprint
    meal.warnings = [warning for warning in meal.warnings if warning != NO_MACROS or _no_macros(meal)]
    db.add(
        build_event(
            db, user_id=current_user.id, event_type="pulse.meal.logged",
            payload={"meal_id": str(meal.id), "eaten_at": meal.eaten_at.isoformat(), "has_macros": not _no_macros(meal),
                     "stock_decrement_applied": meal.stock_decrement_applied},
            idempotency_key=f"pulse.meal.logged.{meal.id}", source_app=SourceApp.pulse, privacy_level=PrivacyLevel.high,
        )
    )
    if touched:
        db.add(
            build_event(
                db, user_id=current_user.id, event_type="pulse.food_stock.updated",
                payload={"source": "meal", "meal_id": str(meal.id), "items_decremented": len(touched) - finished,
                         "items_finished": finished, "stock_item_ids": [str(item.id) for item in touched]},
                idempotency_key=f"pulse.food_stock.updated.meal:{meal.id}", source_app=SourceApp.pulse,
                privacy_level=PrivacyLevel.medium,
            )
        )
    db.flush()
    db.refresh(meal)
    read = _read(meal)
    db.commit()
    return read


def cancel_meal(db: Session, *, current_user: User, meal_id: UUID) -> MealRead:
    meal = _get(db, current_user, meal_id)
    if meal.status == "confirmed":
        raise MealStateError("A confirmed meal is not cancelled.")
    if meal.status != "cancelled":
        meal.status = "cancelled"
        db.commit()
    return _read(meal)


def list_day(db: Session, *, current_user: User, day: date) -> MealDayRead:
    start = datetime.combine(day, time.min, tzinfo=PARIS)
    meals = list(
        db.scalars(
            select(PulseMeal)
            .where(PulseMeal.user_id == current_user.id, PulseMeal.status == "confirmed",
                   PulseMeal.eaten_at >= start, PulseMeal.eaten_at < start + timedelta(days=1))
            .order_by(PulseMeal.eaten_at.asc())
        )
    )
    totals = {macro: sum((getattr(meal, macro) or Decimal("0") for meal in meals), Decimal("0.0")) for macro in MACROS}
    return MealDayRead(
        day=day, meals=[_read(meal) for meal in meals],
        totals=MealTotalsRead(**{macro: value.quantize(Decimal("0.1")) for macro, value in totals.items()}),
        meals_without_macros=sum(1 for meal in meals if _no_macros(meal)),
    )


# ---------- internes ----------

def _declared(description: str) -> list[DeclaredLine]:
    text = _WITH.sub(", ", _MEAL_PREFIX.sub("", description.replace("’", "'").strip(), count=1))
    return parse_declaration(text, today=datetime.now(PARIS).date()).lines


def propose(
    db: Session, current_user: User, foods: list[tuple[DeclaredLine, bool]]
) -> tuple[list[MealStockLineRead], list[str]]:
    """Lignes de décompte comparées au stock actif ; (ligne, incertaine) — une ligne incertaine reste décochée."""
    stock = list(db.scalars(select(FoodStockItem).where(FoodStockItem.user_id == current_user.id, FoodStockItem.status == "active")))
    lines, warnings = [], []
    for index, (declared, uncertain) in enumerate(foods):
        match = match_stock(declared.name, stock)
        if match is None:
            lines.append(MealStockLineRead(index=index, name=declared.name, quantity=declared.quantity, unit=declared.unit,
                                           confidence="low", checked=False))
            warnings.append(f"« {declared.name} » n'est pas dans le stock.")
            continue
        used = convert(declared.quantity, declared.unit, match.unit)
        exact = normalize_name(match.name) == normalize_name(declared.name)
        high = exact and used is not None and not declared.quantity_assumed and not uncertain
        insufficient = used is not None and used >= match.quantity
        if insufficient:
            warnings.append(f"Stock insuffisant pour « {match.name} » (reste {match.quantity} {match.unit}).")
        lines.append(
            MealStockLineRead(
                index=index, name=declared.name, quantity=declared.quantity, unit=declared.unit, stock_item_id=match.id,
                stock_name=match.name, stock_quantity=match.quantity, stock_unit=match.unit, used_in_stock_unit=used,
                confidence="high" if high else "low", checked=high, insufficient=insufficient,
            )
        )
    return lines, warnings


def _no_macros(meal: PulseMeal) -> bool:
    return all(getattr(meal, macro) is None for macro in MACROS)


def _get(db: Session, current_user: User, meal_id: UUID, *, lock: bool = False) -> PulseMeal:
    meal = db.get(PulseMeal, meal_id, with_for_update=lock)
    if meal is None or meal.user_id != current_user.id:
        raise MealNotFoundError("Meal not found.")
    return meal


def _read(meal: PulseMeal) -> MealRead:
    return MealRead(
        id=meal.id, status=meal.status, label=meal.label, description=meal.description, source=meal.source,
        eaten_at=meal.eaten_at, **{macro: getattr(meal, macro) for macro in MACROS},
        stock_lines=[MealStockLineRead(**line) for line in meal.proposal or []], warnings=list(meal.warnings or []),
        stock_decrement_applied=meal.stock_decrement_applied, macros_estimated=meal.macros_estimated,
        confidence=float(meal.confidence) if meal.confidence is not None else None,
        stock_items=[FoodStockItemRead.model_validate(item) for item in (meal.result or {}).get("stock_items", [])],
        confirmed_at=meal.confirmed_at, created_at=meal.created_at,
    )
