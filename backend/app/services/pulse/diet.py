"""Diète Pulse (doc 40 §10.4–§10.9, kit Pulse P02/P05/P06/P08). Code pur, aucun modèle ici.

Le cerveau propose la semaine (`diet_planner`) ; l'utilisateur la valide, le plan devient `active` (un seul par
semaine, le précédent passe `superseded`). Tout passe par l'inventaire :

- besoins = ingrédients des préparations à faire, à l'échelle des portions prévues (portions / `servings`) ;
- stock = lignes `raw` actives, prises par date limite la plus proche (FEFO), rapprochées par nom normalisé
  (même nom, ou l'un contient l'autre) dans la même famille d'unités (masse, volume, pièce) ;
- courses = besoins non couverts, créées à la validation ; relues à chaque lecture : une ligne couverte par le
  stock passe `bought` (la liste se vide quand le stock arrive), `removed` seulement à la demande ; cocher ne
  crédite jamais le stock ;
- démarrer une préparation vérifie le stock : il manque quelque chose → 409, la préparation garde la liste des
  manques (attention requise dans Imperium), les manques entrent dans les courses ; aucune substitution ;
- terminer consomme les ingrédients et crée UNE ligne `prepared` (une pièce = une portion, même poids pour toutes),
  en une transaction. Apports d'une portion = apports de la recette pour les portions prévues ÷ portions réelles :
  la perte de masse à la cuisson ne multiplie pas les nutriments.
"""

import logging
import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.imperium import FoodStockItem
from app.models.pulse import PulseDietPlan, PulseDietPlanMeal, PulsePreparation, PulseRecipe, PulseShoppingItem
from app.schemas.operations import IntrinsicMissionCreate
from app.schemas.pulse_diet import (
    MissingLine,
    NeedLine,
    PlanMealRead,
    PlanRead,
    PlanRequest,
    PreparationComplete,
    PreparationDetailRead,
    PreparationRead,
    PulseAttentionRead,
    RecipeCreate,
    RecipeListRead,
    RecipeRead,
    ShoppingItemRead,
    ShoppingListRead,
    WeekRead,
)
from app.services.events.emitter import build_event
from app.services.params import get_parameter
from app.services.pulse import food_stock
from app.services.pulse.expiry import PARIS
from app.services.pulse.pantry_scan import normalize_name

logger = logging.getLogger(__name__)

MACROS = ("calories", "protein_g", "carbs_g", "fat_g")
OPEN_PREPARATIONS = ("planned", "started")
PLAN_REQUESTED = "pulse.diet.plan_requested"
_FAMILY = {"g": ("mass", Decimal(1)), "kg": ("mass", Decimal(1000)), "ml": ("volume", Decimal(1)),
           "cl": ("volume", Decimal(10)), "l": ("volume", Decimal(1000)), "piece": ("piece", Decimal(1))}
_EPSILON = Decimal("0.0005")
_SLOT_ORDER = {"breakfast": 0, "lunch": 1, "snack": 2, "dinner": 3}


class DietDisabledError(RuntimeError):
    pass


class DietNotFoundError(ValueError):
    pass


class DietStateError(ValueError):
    pass


class DietIdempotencyConflictError(ValueError):
    pass


class IngredientsMissingError(ValueError):
    def __init__(self, missing: list[MissingLine]) -> None:
        super().__init__("Ingredients missing from the stock.")
        self.missing = missing


def enabled(db: Session) -> bool:
    return bool(get_parameter(db, "pulse.diet_enabled", default=False))


def missions_enabled(db: Session) -> bool:
    return bool(get_parameter(db, "pulse.diet_missions_enabled", default=False))


def week_start_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def today() -> date:
    return datetime.now(PARIS).date()


# --- Quantités et rapprochement ---------------------------------------------------------------------------------

@dataclass
class Need:
    """Besoin d'un ingrédient, en unité de base de sa famille (g, ml, pièce)."""

    name: str
    family: str
    base: Decimal
    key: tuple = field(init=False)

    def __post_init__(self) -> None:
        self.key = (normalize_name(self.name), self.family)


@dataclass
class Allocation:
    need: Need
    taken: list[tuple[FoodStockItem, Decimal]]  # (ligne, quantité de base prise)
    available: Decimal
    shortfall: Decimal


def to_base(quantity: Decimal, unit: str) -> tuple[str, Decimal]:
    family, factor = _FAMILY[unit]
    return family, Decimal(quantity) * factor


def from_base(family: str, base: Decimal, *, round_pieces: bool = False) -> tuple[Decimal, str]:
    """Unité lisible : kg / l au-delà de 1000 g / ml ; pièces arrondies au-dessus pour les courses."""
    if family == "mass":
        quantity, unit = (base / 1000, "kg") if base >= 1000 else (base, "g")
    elif family == "volume":
        quantity, unit = (base / 1000, "l") if base >= 1000 else (base, "ml")
    else:
        quantity, unit = (Decimal(math.ceil(base - _EPSILON)) if round_pieces else base), "piece"
    return plain(quantity), unit


def plain(quantity: Decimal) -> Decimal:
    """Au millième, sans zéros inutiles ni notation exponentielle (« 1.500 » → 1.5, « 10.000 » → 10)."""
    rounded = Decimal(quantity).quantize(Decimal("0.001"))
    return rounded.quantize(Decimal(1)) if rounded == rounded.to_integral_value() else rounded.normalize()


def _in_unit(base: Decimal, unit: str) -> Decimal:
    return plain(base / _FAMILY[unit][1])


def _matches(wanted: frozenset, other: frozenset) -> bool:
    return bool(wanted) and bool(other) and (wanted == other or wanted <= other or other <= wanted)


def recipe_needs(recipe: PulseRecipe, portions: int) -> list[Need]:
    factor = Decimal(portions) / Decimal(recipe.servings)
    needs = []
    for line in recipe.ingredients or []:
        family, base = to_base(Decimal(str(line["quantity"])), line["unit"])
        needs.append(Need(name=line["name"], family=family, base=base * factor))
    return needs


def merge(needs: Iterable[Need]) -> list[Need]:
    merged: dict[tuple, Need] = {}
    for need in needs:
        if need.key in merged:
            merged[need.key].base += need.base
        else:
            merged[need.key] = Need(name=need.name, family=need.family, base=need.base)
    return list(merged.values())


def raw_stock(db: Session, user: User, *, lock: bool = False) -> list[FoodStockItem]:
    query = (select(FoodStockItem)
             .where(FoodStockItem.user_id == user.id, FoodStockItem.status == "active", FoodStockItem.kind == "raw")
             .order_by(FoodStockItem.expiry_date.asc().nulls_last(), FoodStockItem.created_at.asc()))
    return list(db.scalars(query.with_for_update() if lock else query))


def allocate(needs: list[Need], stock: list[FoodStockItem], pool: dict | None = None) -> list[Allocation]:
    """Prend le stock pour chaque besoin (même nom d'abord, puis noms proches ; FEFO). `pool` = reste par ligne,
    partagé entre plusieurs appels pour ne pas compter deux fois la même ligne."""
    pool = pool if pool is not None else {}
    out = []
    for need in needs:
        wanted = need.key[0]
        lines = [item for item in stock if _FAMILY[item.unit][0] == need.family]
        exact = [item for item in lines if normalize_name(item.name) == wanted]
        close = [item for item in lines if item not in exact and _matches(wanted, normalize_name(item.name))]
        left, taken, available = need.base, [], Decimal(0)
        for item in exact + close:
            remaining = pool.setdefault(item.id, to_base(item.quantity, item.unit)[1])
            available += remaining
            if left <= _EPSILON or remaining <= 0:
                continue
            take = min(left, remaining)
            pool[item.id] = remaining - take
            left -= take
            taken.append((item, take))
        out.append(Allocation(need=need, taken=taken, available=available,
                              shortfall=left if left > _EPSILON else Decimal(0)))
    return out


def _missing(allocations: list[Allocation]) -> list[MissingLine]:
    lines = []
    for allocation in allocations:
        if allocation.shortfall <= 0:
            continue
        quantity, unit = from_base(allocation.need.family, allocation.shortfall, round_pieces=True)
        lines.append(MissingLine(name=allocation.need.name, quantity=quantity, unit=unit,
                                 available=_in_unit(min(allocation.available, allocation.need.base), unit)))
    return lines


# --- Recettes -------------------------------------------------------------------------------------------------

def create_recipe(db: Session, *, current_user: User, payload: RecipeCreate, idempotency_key: str,
                  source: str = "manual") -> tuple[RecipeRead, bool]:
    fingerprint = food_stock.request_hash("pulse.recipe", payload.model_dump(mode="json"))
    existing = db.scalar(select(PulseRecipe).where(PulseRecipe.user_id == current_user.id,
                                                   PulseRecipe.idempotency_key == idempotency_key))
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise DietIdempotencyConflictError("Idempotency key already used with a different recipe.")
        return recipe_read(existing), True
    recipe = new_recipe(current_user.id, payload, source=source, status="active")
    recipe.idempotency_key, recipe.request_hash = idempotency_key, fingerprint
    db.add(recipe)
    db.flush()
    db.add(build_event(db, user_id=current_user.id, event_type="pulse.recipe.added",
                       payload={"recipe_id": str(recipe.id), "source": source},
                       idempotency_key=f"pulse.recipe.added.{recipe.id}", source_app=SourceApp.pulse,
                       privacy_level=PrivacyLevel.low))
    db.flush()
    db.refresh(recipe)
    read = recipe_read(recipe)
    db.commit()
    return read, False


def new_recipe(user_id: UUID, payload: RecipeCreate, *, source: str, status: str,
               plan_id: UUID | None = None) -> PulseRecipe:
    return PulseRecipe(
        user_id=user_id, title=payload.title, servings=payload.servings, portion_weight_g=payload.portion_weight_g,
        ingredients=[line.model_dump(mode="json") for line in payload.ingredients], steps=payload.steps,
        packaging=payload.packaging, shelf_life_days=payload.shelf_life_days,
        **{macro: getattr(payload, macro) for macro in MACROS}, source=source, status=status, plan_id=plan_id)


def list_recipes(db: Session, *, current_user: User) -> RecipeListRead:
    rows = db.scalars(select(PulseRecipe).where(PulseRecipe.user_id == current_user.id, PulseRecipe.status == "active")
                      .order_by(PulseRecipe.title))
    return RecipeListRead(items=[recipe_read(row) for row in rows])


def get_recipe(db: Session, *, current_user: User, recipe_id: UUID) -> RecipeRead:
    return recipe_read(_recipe(db, current_user, recipe_id))


def archive_recipe(db: Session, *, current_user: User, recipe_id: UUID) -> None:
    recipe = _recipe(db, current_user, recipe_id)
    if recipe.status != "archived":
        recipe.status = "archived"
        db.commit()


# --- Plans ----------------------------------------------------------------------------------------------------

def request_plan(db: Session, *, current_user: User, payload: PlanRequest, idempotency_key: str
                 ) -> tuple[PlanRead, bool]:
    """Demande au cerveau la semaine ; le job `pulse.diet_planner` dépose la proposition."""
    week = week_start_of(payload.week_start or today())
    fingerprint = food_stock.request_hash("pulse.diet.plan", {"week_start": week.isoformat(), "note": payload.note})
    existing = db.scalar(select(PulseDietPlan).where(PulseDietPlan.user_id == current_user.id,
                                                     PulseDietPlan.idempotency_key == idempotency_key))
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise DietIdempotencyConflictError("Idempotency key already used with a different request.")
        return plan_read(db, existing), True
    if week + timedelta(days=6) < today():
        raise DietStateError("This week is over.")
    running = db.scalar(select(PulseDietPlan).where(PulseDietPlan.user_id == current_user.id,
                                                    PulseDietPlan.week_start == week,
                                                    PulseDietPlan.status == "generating"))
    if running is not None:
        raise DietStateError("A plan is already being prepared for this week.")
    plan = PulseDietPlan(user_id=current_user.id, week_start=week, status="generating",
                         note=(payload.note or "").strip() or None, idempotency_key=idempotency_key,
                         request_hash=fingerprint)
    db.add(plan)
    db.flush()
    db.add(build_event(db, user_id=current_user.id, event_type=PLAN_REQUESTED,
                       payload={"plan_id": str(plan.id), "week_start": week.isoformat()},
                       idempotency_key=f"{PLAN_REQUESTED}.{plan.id}", source_app=SourceApp.pulse,
                       privacy_level=PrivacyLevel.medium))
    db.flush()
    db.refresh(plan)
    read = plan_read(db, plan)
    db.commit()
    return read, False


def week(db: Session, *, current_user: User, day: date) -> WeekRead:
    start = week_start_of(day)
    plans = list(db.scalars(select(PulseDietPlan).where(
        PulseDietPlan.user_id == current_user.id, PulseDietPlan.week_start == start,
        PulseDietPlan.status.in_(("active", "generating", "proposed", "failed"))).order_by(PulseDietPlan.created_at)))
    active = next((plan for plan in plans if plan.status == "active"), None)
    pending = [plan for plan in plans if plan.status != "active"
               and (active is None or plan.created_at > (active.activated_at or active.created_at))]
    shopping = shopping_list(db, current_user=current_user)
    return WeekRead(week_start=start, active=plan_read(db, active) if active else None,
                    pending=plan_read(db, pending[-1]) if pending else None, shopping_open=len(shopping.items))


def get_plan(db: Session, *, current_user: User, plan_id: UUID) -> PlanRead:
    return plan_read(db, _plan(db, current_user, plan_id))


def activate_plan(db: Session, *, current_user: User, plan_id: UUID) -> PlanRead:
    """Validation de l'utilisateur : le plan proposé devient la semaine ; courses calculées, missions si permises."""
    plan = _plan(db, current_user, plan_id, lock=True)
    if plan.status == "active":
        return plan_read(db, plan)
    if plan.status != "proposed":
        raise DietStateError("Only a proposed plan can be validated.")
    now = datetime.now(UTC)
    previous = db.scalar(select(PulseDietPlan).where(PulseDietPlan.user_id == current_user.id,
                                                     PulseDietPlan.week_start == plan.week_start,
                                                     PulseDietPlan.status == "active").with_for_update())
    if previous is not None:
        _retire(db, previous)
        db.flush()
    plan.status, plan.activated_at = "active", now
    for recipe in db.scalars(select(PulseRecipe).where(PulseRecipe.plan_id == plan.id, PulseRecipe.status == "proposed")):
        recipe.status = "active"
    db.flush()
    created = _create_shopping(db, current_user, plan)
    db.add(build_event(db, user_id=current_user.id, event_type="pulse.diet.plan_activated",
                       payload={"plan_id": str(plan.id), "week_start": plan.week_start.isoformat(),
                                "shopping_items": created,
                                "superseded_plan_id": str(previous.id) if previous else None},
                       idempotency_key=f"pulse.diet.plan_activated.{plan.id}", source_app=SourceApp.pulse,
                       privacy_level=PrivacyLevel.medium))
    db.flush()
    db.refresh(plan)
    db.commit()
    if missions_enabled(db):
        _create_missions(db, current_user, plan, shopping=created > 0)
    return plan_read(db, plan)


def reject_plan(db: Session, *, current_user: User, plan_id: UUID) -> PlanRead:
    plan = _plan(db, current_user, plan_id, lock=True)
    if plan.status == "rejected":
        return plan_read(db, plan)
    if plan.status not in ("proposed", "failed"):
        raise DietStateError("Only a proposed or failed plan can be dismissed.")
    plan.status = "rejected"
    for recipe in db.scalars(select(PulseRecipe).where(PulseRecipe.plan_id == plan.id, PulseRecipe.status == "proposed")):
        recipe.status = "archived"
    db.commit()
    return plan_read(db, plan)


def _retire(db: Session, plan: PulseDietPlan) -> None:
    plan.status = "superseded"
    for preparation in db.scalars(select(PulsePreparation).where(PulsePreparation.plan_id == plan.id,
                                                                 PulsePreparation.status.in_(OPEN_PREPARATIONS))):
        preparation.status = "cancelled"
    now = datetime.now(UTC)
    for item in db.scalars(select(PulseShoppingItem).where(PulseShoppingItem.plan_id == plan.id,
                                                           PulseShoppingItem.status == "open")):
        item.status, item.closed_at = "superseded", now


def _create_missions(db: Session, user: User, plan: PulseDietPlan, *, shopping: bool) -> None:
    """Missions hors projet « Faire les courses » (avant la première préparation) et « Cuisiner » (par jour)."""
    from app.services.imperium import operations  # import tardif : Imperium dépend déjà de Pulse ailleurs

    preparations = _preparations(db, plan.id)
    by_day: dict[date, list[str]] = {}
    for preparation, recipe in preparations:
        if preparation.status in OPEN_PREPARATIONS:
            by_day.setdefault(preparation.planned_day, []).append(recipe.title)
    if not by_day:
        return
    now = datetime.now(UTC)
    first = min(by_day)
    payloads = []
    if shopping:
        deadline = datetime.combine(first, time(12), tzinfo=PARIS)
        payloads.append((f"pulse.diet.{plan.id}.shopping", IntrinsicMissionCreate(
            title="Faire les courses", domain="health", source="pulse",
            description="Liste des courses dans Pulse : ce qui manque pour les préparations de la semaine.",
            deadline_at=deadline if deadline > now else None)))
    for day, titles in sorted(by_day.items()):
        deadline = datetime.combine(day, time(21), tzinfo=PARIS)
        payloads.append((f"pulse.diet.{plan.id}.cook.{day.isoformat()}", IntrinsicMissionCreate(
            title=f"Cuisiner : {', '.join(titles)}"[:200], domain="health", source="pulse",
            description="Préparation dans Pulse (Repas) : étapes, conditionnement et conservation.",
            planned_start_at=datetime.combine(day, time(8), tzinfo=PARIS),
            deadline_at=deadline if deadline > now else None)))
    for key, payload in payloads:
        try:
            operations.create_intrinsic_mission(db, current_user=user, payload=payload, idempotency_key=key)
        except Exception:  # noqa: BLE001 - une mission manquée ne défait pas la validation du plan
            db.rollback()
            logger.exception("pulse diet mission %s not created", key)


# --- Courses --------------------------------------------------------------------------------------------------

def _active_plans(db: Session, user: User) -> list[PulseDietPlan]:
    """Plans validés dont la semaine n'est pas finie, la plus ancienne d'abord (elle se sert la première)."""
    return list(db.scalars(select(PulseDietPlan).where(
        PulseDietPlan.user_id == user.id, PulseDietPlan.status == "active",
        PulseDietPlan.week_start >= week_start_of(today())).order_by(PulseDietPlan.week_start)))


def _plan_needs(db: Session, plan_id: UUID) -> list[Need]:
    needs = []
    for preparation, recipe in _preparations(db, plan_id):
        if preparation.status in OPEN_PREPARATIONS:
            needs.extend(recipe_needs(recipe, preparation.portions_planned))
    return merge(needs)


def _shortfalls(db: Session, user: User, plans: list[PulseDietPlan]) -> dict[UUID, list[Allocation]]:
    stock, pool = raw_stock(db, user), {}
    return {plan.id: allocate(_plan_needs(db, plan.id), stock, pool) for plan in plans}


def _create_shopping(db: Session, user: User, plan: PulseDietPlan) -> int:
    plans = sorted({*[p for p in _active_plans(db, user) if p.week_start <= plan.week_start], plan},
                   key=lambda p: (p.week_start, p.id != plan.id))
    created = 0
    for line in _missing(_shortfalls(db, user, plans)[plan.id]):
        db.add(PulseShoppingItem(user_id=user.id, plan_id=plan.id, name=line.name, quantity=line.quantity,
                                 unit=line.unit, status="open"))
        created += 1
    db.flush()
    return created


def shopping_list(db: Session, *, current_user: User) -> ShoppingListRead:
    """Lignes ouvertes des plans en cours, relues contre le stock : une ligne couverte passe `bought`."""
    plans = _active_plans(db, current_user)
    if not plans:
        return ShoppingListRead(items=[])
    shortfalls = _shortfalls(db, current_user, plans)
    now, changed, items = datetime.now(UTC), False, []
    for plan in plans:
        left = {allocation.need.key: allocation for allocation in shortfalls[plan.id]}
        for item in db.scalars(select(PulseShoppingItem).where(PulseShoppingItem.plan_id == plan.id,
                                                               PulseShoppingItem.status == "open")
                               .order_by(PulseShoppingItem.created_at)):
            family = _FAMILY[item.unit][0]
            allocation = left.get((normalize_name(item.name), family))
            if allocation is None or allocation.shortfall <= 0:
                item.status, item.closed_at, changed = "bought", now, True
                continue
            quantity, unit = from_base(family, allocation.shortfall, round_pieces=True)
            if (quantity, unit) != (item.quantity, item.unit):
                item.quantity, item.unit, changed = quantity, unit, True
            items.append(item)
    if changed:
        db.flush()
        db.commit()
    return ShoppingListRead(items=[_shopping_read(item) for item in items])


def check_item(db: Session, *, current_user: User, item_id: UUID, checked: bool) -> ShoppingItemRead:
    item = _shopping(db, current_user, item_id)
    if item.status != "open":
        raise DietStateError("This line is no longer on the list.")
    item.checked = checked
    db.commit()
    return _shopping_read(item)


def remove_item(db: Session, *, current_user: User, item_id: UUID) -> None:
    """Retrait à la demande : donnée gardée (les non-achats nourrissent la Weekly Review)."""
    item = _shopping(db, current_user, item_id)
    if item.status == "open":
        item.status, item.closed_at = "removed", datetime.now(UTC)
        db.add(build_event(db, user_id=current_user.id, event_type="pulse.shopping.item_removed",
                           payload={"shopping_item_id": str(item.id), "plan_id": str(item.plan_id)},
                           idempotency_key=f"pulse.shopping.item_removed.{item.id}", source_app=SourceApp.pulse,
                           privacy_level=PrivacyLevel.low))
        db.commit()


# --- Préparations ---------------------------------------------------------------------------------------------

def get_preparation(db: Session, *, current_user: User, preparation_id: UUID) -> PreparationDetailRead:
    preparation, recipe = _preparation(db, current_user, preparation_id)
    needs = recipe_needs(recipe, preparation.portions_planned)
    allocations = allocate(needs, raw_stock(db, current_user))
    lines = []
    for allocation in allocations:
        quantity, unit = from_base(allocation.need.family, allocation.need.base)
        lines.append(NeedLine(name=allocation.need.name, quantity=quantity, unit=unit,
                              available=_in_unit(allocation.available, unit), enough=allocation.shortfall <= 0))
    return PreparationDetailRead(**preparation_read(preparation, recipe).model_dump(), recipe=recipe_read(recipe),
                                 needs=lines)


def start_preparation(db: Session, *, current_user: User, preparation_id: UUID) -> PreparationRead:
    """« Démarrer la préparation » : vérifie le stock ; un manque → 409, attention requise et courses."""
    preparation, recipe = _preparation(db, current_user, preparation_id, lock=True)
    if preparation.status == "started":
        return preparation_read(preparation, recipe)
    if preparation.status != "planned":
        raise DietStateError("This preparation is not waiting to start.")
    missing = _missing(allocate(recipe_needs(recipe, preparation.portions_planned), raw_stock(db, current_user)))
    if missing:
        _record_missing(db, current_user, preparation, recipe, missing)
        db.commit()
        raise IngredientsMissingError(missing)
    preparation.status, preparation.started_at = "started", datetime.now(UTC)
    preparation.missing, preparation.missing_at = [], None
    db.commit()
    return preparation_read(preparation, recipe)


def complete_preparation(db: Session, *, current_user: User, preparation_id: UUID, payload: PreparationComplete,
                         idempotency_key: str) -> PreparationRead:
    """Une mutation : ingrédients décomptés (FEFO) + une ligne de portions ; rejouer la même clé ne refait rien."""
    fingerprint = food_stock.request_hash("pulse.preparation.complete",
                                          {"id": str(preparation_id), **payload.model_dump(mode="json")})
    preparation, recipe = _preparation(db, current_user, preparation_id, lock=True)
    if preparation.status == "done":
        if preparation.complete_idempotency_key != idempotency_key:
            raise DietStateError("Preparation already finished.")
        if preparation.complete_request_hash != fingerprint:
            raise DietIdempotencyConflictError("Idempotency key already used with a different completion.")
        return preparation_read(preparation, recipe)
    if preparation.status not in OPEN_PREPARATIONS:
        raise DietStateError("This preparation was cancelled.")
    allocations = allocate(recipe_needs(recipe, preparation.portions_planned), raw_stock(db, current_user, lock=True))
    missing = _missing(allocations)
    if missing:
        db.rollback()
        preparation, recipe = _preparation(db, current_user, preparation_id, lock=True)
        _record_missing(db, current_user, preparation, recipe, missing)
        db.commit()
        raise IngredientsMissingError(missing)
    consumed, touched = [], []
    for allocation in allocations:
        for item, base in allocation.taken:
            used = _in_unit(base, item.unit)
            finished = used >= item.quantity - _EPSILON
            if finished:
                item.status = "consumed"
            else:
                item.quantity = item.quantity - used
            item.version += 1
            touched.append(item)
            consumed.append({"stock_item_id": str(item.id), "name": item.name, "quantity": str(used),
                             "unit": item.unit, "finished": finished})
    now = datetime.now(UTC)
    day = now.astimezone(PARIS).date()
    portions = Decimal(payload.portions)
    per_portion = {macro: (value * preparation.portions_planned / portions).quantize(Decimal("0.1"), ROUND_HALF_UP)
                   if (value := getattr(recipe, macro)) is not None else None for macro in MACROS}
    produced = FoodStockItem(
        user_id=current_user.id, name=recipe.title, quantity=portions, unit="piece",
        expiry_type="DLC" if recipe.shelf_life_days is not None else "unknown",
        expiry_date=day + timedelta(days=recipe.shelf_life_days) if recipe.shelf_life_days is not None else None,
        category="Préparation", source="preparation", source_ref=f"preparation:{preparation.id}", status="active",
        kind="prepared", recipe_id=recipe.id, portion_weight_g=payload.portion_weight_g, **per_portion)
    db.add(produced)
    db.flush()
    preparation.status, preparation.done_at = "done", now
    preparation.started_at = preparation.started_at or now
    preparation.portions_made, preparation.portion_weight_g = payload.portions, payload.portion_weight_g
    preparation.stock_item_id, preparation.consumed = produced.id, consumed
    preparation.missing, preparation.missing_at = [], None
    preparation.complete_idempotency_key, preparation.complete_request_hash = idempotency_key, fingerprint
    db.add(build_event(db, user_id=current_user.id, event_type="pulse.preparation.done",
                       payload={"preparation_id": str(preparation.id), "recipe_id": str(recipe.id),
                                "portions": payload.portions, "stock_item_id": str(produced.id)},
                       idempotency_key=f"pulse.preparation.done.{preparation.id}", source_app=SourceApp.pulse,
                       privacy_level=PrivacyLevel.medium))
    db.add(build_event(db, user_id=current_user.id, event_type="pulse.food_stock.updated",
                       payload={"source": "preparation", "preparation_id": str(preparation.id),
                                "items_consumed": len(touched), "stock_item_ids": [str(item.id) for item in touched],
                                "created_item_id": str(produced.id)},
                       idempotency_key=f"pulse.food_stock.updated.preparation:{preparation.id}",
                       source_app=SourceApp.pulse, privacy_level=PrivacyLevel.medium))
    db.flush()
    db.refresh(preparation)
    read = preparation_read(preparation, recipe)
    db.commit()
    return read


def cancel_preparation(db: Session, *, current_user: User, preparation_id: UUID) -> PreparationRead:
    preparation, recipe = _preparation(db, current_user, preparation_id, lock=True)
    if preparation.status == "done":
        raise DietStateError("A finished preparation is not cancelled.")
    if preparation.status != "cancelled":
        preparation.status, preparation.missing, preparation.missing_at = "cancelled", [], None
        db.commit()
    return preparation_read(preparation, recipe)


def _record_missing(db: Session, user: User, preparation: PulsePreparation, recipe: PulseRecipe,
                    missing: list[MissingLine]) -> None:
    """Garde les manques (attention requise dans Imperium) et les ajoute aux courses s'ils n'y sont pas."""
    preparation.missing = [line.model_dump(mode="json") for line in missing]
    preparation.missing_at = datetime.now(UTC)
    listed = {(normalize_name(item.name), _FAMILY[item.unit][0]) for item in db.scalars(
        select(PulseShoppingItem).where(PulseShoppingItem.plan_id == preparation.plan_id,
                                        PulseShoppingItem.status == "open"))}
    for line in missing:
        if (normalize_name(line.name), _FAMILY[line.unit][0]) not in listed:
            db.add(PulseShoppingItem(user_id=user.id, plan_id=preparation.plan_id, name=line.name,
                                     quantity=line.quantity, unit=line.unit, status="open"))
    db.add(build_event(db, user_id=user.id, event_type="pulse.preparation.blocked",
                       payload={"preparation_id": str(preparation.id), "recipe_id": str(recipe.id),
                                "missing": [line.name for line in missing]},
                       idempotency_key=f"pulse.preparation.blocked.{preparation.id}.{preparation.missing_at.isoformat()}",
                       source_app=SourceApp.pulse, privacy_level=PrivacyLevel.low))


def attention(db: Session, *, current_user: User) -> list[PulseAttentionRead]:
    """Préparations bloquées par un manque, relues contre le stock (un manque comblé disparaît)."""
    rows = db.execute(select(PulsePreparation, PulseRecipe)
                      .join(PulseRecipe, PulseRecipe.id == PulsePreparation.recipe_id)
                      .join(PulseDietPlan, PulseDietPlan.id == PulsePreparation.plan_id)
                      .where(PulsePreparation.user_id == current_user.id, PulsePreparation.status == "planned",
                             PulsePreparation.missing_at.is_not(None), PulseDietPlan.status == "active")
                      .order_by(PulsePreparation.planned_day)).all()
    if not rows:
        return []
    stock, out = raw_stock(db, current_user), []
    for preparation, recipe in rows:
        missing = _missing(allocate(recipe_needs(recipe, preparation.portions_planned), stock))
        if not missing:
            continue
        names = ", ".join(line.name for line in missing[:4]) + ("…" if len(missing) > 4 else "")
        out.append(PulseAttentionRead(
            preparation_id=preparation.id, recipe_title=recipe.title, planned_day=preparation.planned_day,
            missing=missing, message_fr=f"Préparation « {recipe.title} » bloquée : il manque {names}."))
    return out


# --- Repas prévus ---------------------------------------------------------------------------------------------

def check_plan_meal(db: Session, user: User, plan_meal_id: UUID) -> PulseDietPlanMeal:
    meal = db.get(PulseDietPlanMeal, plan_meal_id)
    if meal is None or meal.user_id != user.id:
        raise DietNotFoundError("Planned meal not found.")
    return meal


def mark_eaten(db: Session, user: User, plan_meal_id: UUID, meal_id: UUID) -> None:
    planned = db.get(PulseDietPlanMeal, plan_meal_id, with_for_update=True)
    if planned is not None and planned.user_id == user.id and planned.status == "planned":
        planned.status, planned.meal_id = "eaten", meal_id


# --- Lectures -------------------------------------------------------------------------------------------------

def recipe_read(recipe: PulseRecipe) -> RecipeRead:
    return RecipeRead(
        id=recipe.id, title=recipe.title, servings=recipe.servings, portion_weight_g=recipe.portion_weight_g,
        ingredients=recipe.ingredients or [], steps=recipe.steps or [], packaging=recipe.packaging or [],
        shelf_life_days=recipe.shelf_life_days, **{macro: getattr(recipe, macro) for macro in MACROS},
        source=recipe.source, status=recipe.status, created_at=recipe.created_at)


def preparation_read(preparation: PulsePreparation, recipe: PulseRecipe) -> PreparationRead:
    return PreparationRead(
        id=preparation.id, plan_id=preparation.plan_id, recipe_id=recipe.id, recipe_title=recipe.title,
        planned_day=preparation.planned_day, portions_planned=preparation.portions_planned,
        portion_weight_g_planned=recipe.portion_weight_g, status=preparation.status,
        missing=[MissingLine(**line) for line in preparation.missing or []], started_at=preparation.started_at,
        done_at=preparation.done_at, portions_made=preparation.portions_made,
        portion_weight_g=preparation.portion_weight_g, stock_item_id=preparation.stock_item_id)


def plan_read(db: Session, plan: PulseDietPlan) -> PlanRead:
    meals = db.execute(select(PulseDietPlanMeal, PulseRecipe)
                       .join(PulseRecipe, PulseRecipe.id == PulseDietPlanMeal.recipe_id)
                       .where(PulseDietPlanMeal.plan_id == plan.id)).all()
    meals.sort(key=lambda row: (row[0].day, _SLOT_ORDER.get(row[0].slot, 9)))
    return PlanRead(
        id=plan.id, week_start=plan.week_start, status=plan.status, source=plan.source, note=plan.note,
        rationale_fr=plan.rationale_fr, error=plan.error, created_at=plan.created_at, activated_at=plan.activated_at,
        meals=[PlanMealRead(
            id=meal.id, day=meal.day, slot=meal.slot, recipe_id=recipe.id, recipe_title=recipe.title,
            portions=meal.portions, status=meal.status, meal_id=meal.meal_id,
            **{macro: (value * meal.portions).quantize(Decimal("0.1")) if (value := getattr(recipe, macro)) is not None
               else None for macro in MACROS}) for meal, recipe in meals],
        preparations=[preparation_read(p, r) for p, r in _preparations(db, plan.id)])


def _shopping_read(item: PulseShoppingItem) -> ShoppingItemRead:
    return ShoppingItemRead(id=item.id, plan_id=item.plan_id, name=item.name, quantity=item.quantity, unit=item.unit,
                            status=item.status, checked=item.checked)


def _preparations(db: Session, plan_id: UUID) -> list[tuple[PulsePreparation, PulseRecipe]]:
    return [tuple(row) for row in db.execute(
        select(PulsePreparation, PulseRecipe).join(PulseRecipe, PulseRecipe.id == PulsePreparation.recipe_id)
        .where(PulsePreparation.plan_id == plan_id)
        .order_by(PulsePreparation.planned_day, PulsePreparation.created_at)).all()]


def _plan(db: Session, user: User, plan_id: UUID, *, lock: bool = False) -> PulseDietPlan:
    plan = db.get(PulseDietPlan, plan_id, with_for_update=lock)
    if plan is None or plan.user_id != user.id:
        raise DietNotFoundError("Plan not found.")
    return plan


def _recipe(db: Session, user: User, recipe_id: UUID) -> PulseRecipe:
    recipe = db.get(PulseRecipe, recipe_id)
    if recipe is None or recipe.user_id != user.id:
        raise DietNotFoundError("Recipe not found.")
    return recipe


def _preparation(db: Session, user: User, preparation_id: UUID, *, lock: bool = False
                 ) -> tuple[PulsePreparation, PulseRecipe]:
    preparation = db.get(PulsePreparation, preparation_id, with_for_update=lock)
    if preparation is None or preparation.user_id != user.id:
        raise DietNotFoundError("Preparation not found.")
    return preparation, db.get(PulseRecipe, preparation.recipe_id)


def _shopping(db: Session, user: User, item_id: UUID) -> PulseShoppingItem:
    item = db.get(PulseShoppingItem, item_id)
    if item is None or item.user_id != user.id:
        raise DietNotFoundError("Shopping item not found.")
    return item
