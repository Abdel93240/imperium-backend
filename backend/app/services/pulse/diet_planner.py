"""Job `pulse.diet_planner` : le cerveau propose la semaine de diète (doc 40 §10.6, §18).

Réveillé par `pulse.diet.plan_requested`. Rôle santé d'abord (slot cloud `pulse.diet_weekly_program`), sinon modèle
local (slot `pulse.diet_weekly_program_local`) ; tous deux semés éteints : aucun branché → le plan passe `failed`
avec la raison, rien n'est inventé.

Contexte en LISTE BLANCHE : jours à planifier, consigne de la demande, catalogue de recettes actives (repères R1…),
stock brut (nom, quantité, date limite), portions déjà prêtes, matériel. Sortie contrainte par schéma puis relue
par le code : recettes citées existantes, jours de la semaine (pas de jour passé), portions mangées couvertes par
les préparations (ou les portions déjà prêtes), conservation respectée, un repas par créneau. Invalide → un nouvel
essai avec les erreurs, puis échec. Le plan proposé attend la validation de l'utilisateur (`diet.activate_plan`).
Les courses ne viennent PAS du modèle : le code les calcule à la validation.
"""

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.imperium import FoodStockItem, PulseOwnedEquipment
from app.models.pulse import PulseDietPlan, PulseDietPlanMeal, PulsePreparation, PulseRecipe
from app.schemas.pulse_diet import RecipeCreate
from app.services.ai import cloud, local_executor
from app.services.pulse import diet

logger = logging.getLogger(__name__)

SLOT = "pulse.diet_weekly_program"
LOCAL_SLOT = "pulse.diet_weekly_program_local"
MAX_CATALOGUE = 40
MAX_STOCK_LINES = 80
MAX_NEW_RECIPES = 8
LOCAL_MAX_TOKENS = 12000
WEEKDAYS_FR = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
SLOTS = ("breakfast", "lunch", "dinner", "snack")
UNITS = ("g", "kg", "ml", "cl", "l", "piece")
NO_BRAIN = ("Aucun cerveau n'est branché pour la diète : allume le rôle santé (ou le modèle local) dans les "
            "paramètres avancés d'Imperium, puis redemande la semaine.")

SYSTEM = (
    "Tu es le spécialiste santé et nutrition d'un assistant personnel. Tu prépares la semaine de repas d'un chauffeur "
    "VTC qui cuisine en une ou deux fois (batch cooking) : les plats sont mis en bocaux de verre stérilisés et "
    "mangés pendant la semaine. Tu choisis d'abord dans son catalogue et dans son stock ; tu peux ajouter quelques "
    "recettes nouvelles, complètes : ingrédients avec quantités pour le nombre de portions indiqué, étapes simples, "
    "et une section conditionnement et conservation précise (stérilisation, refroidissement, durée). Les apports par "
    "portion sont tes estimations honnêtes, ou null si tu ne sais pas. Les noms d'ingrédients sont ceux du magasin "
    "(« riz basmati », « oignon »), unités g, kg, ml, cl, l ou piece seulement. Une préparation produit des portions ; "
    "un repas en mange ; on ne mange jamais un plat avant de l'avoir préparé ni après sa durée de conservation. "
    "Respecte la consigne de l'utilisateur. Pas de conseil médical, pas de promesse de santé. Réponds en français, "
    "en tutoyant, uniquement selon le schéma JSON."
)


class PlannerUnavailableError(RuntimeError):
    pass


Caller = Callable[[str, str, dict], tuple[dict, str, dict]]  # (system, prompt, schema) → (sortie, source, trace)


def diet_planner_job(ctx, window) -> None:  # noqa: ARG001 - signature du runner
    done = process_requested(ctx.db)
    ctx.items_in = ctx.items_out = done


def process_requested(db: Session, *, call: Caller | None = None, now: datetime | None = None) -> int:
    ids = list(db.scalars(select(PulseDietPlan.id).where(PulseDietPlan.status == "generating")
                          .order_by(PulseDietPlan.created_at).limit(10)))
    for plan_id in ids:
        generate(db, plan_id, call=call, now=now)
    return len(ids)


def generate(db: Session, plan_id: UUID, *, call: Caller | None = None, now: datetime | None = None) -> None:
    plan = db.get(PulseDietPlan, plan_id, with_for_update=True)
    if plan is None or plan.status != "generating":
        db.rollback()
        return
    user = db.get(User, plan.user_id)
    now = now or datetime.now(UTC)
    first = max(plan.week_start, now.astimezone(diet.PARIS).date())
    days = [first + timedelta(days=i) for i in range((plan.week_start + timedelta(days=7) - first).days)]
    if not days:
        _fail(db, plan, "Cette semaine est finie.")
        return
    catalogue = list(db.scalars(select(PulseRecipe).where(PulseRecipe.user_id == user.id, PulseRecipe.status == "active")
                                .order_by(PulseRecipe.updated_at.desc()).limit(MAX_CATALOGUE)))
    aliases = {f"R{i}": recipe for i, recipe in enumerate(catalogue, start=1)}
    ready = _ready_portions(db, user, catalogue)
    prompt = build_prompt(db, user, plan, days, aliases, ready)
    schema = output_schema(days)
    caller = call or _default_caller(db, plan)
    trace: dict = {"attempts": 0, "errors": []}
    output, source = None, None
    current = prompt
    for _ in range(2):
        trace["attempts"] += 1
        try:
            output, source, info = caller(SYSTEM, current, schema)
        except PlannerUnavailableError as exc:
            _fail(db, plan, str(exc), trace)
            return
        trace.update(info)
        errors = validate(output, days, aliases, ready)
        if not errors:
            break
        trace["errors"].extend(errors[:20])
        output = None
        current = (f"{prompt}\n\n## rappel\nTa proposition précédente était invalide : {' ; '.join(errors[:12])}. "
                   "Corrige-la en respectant le schéma et les règles.")
    if output is None:
        _fail(db, plan, "Le cerveau n'a pas proposé de semaine valable ; redemande-la ou précise ta consigne.", trace)
        return
    _write(db, plan, output, days, aliases, source, trace)


# --- Contexte et schéma ---------------------------------------------------------------------------------------

def _ready_portions(db: Session, user: User, catalogue: list[PulseRecipe]) -> dict[UUID, Decimal]:
    ids = {recipe.id for recipe in catalogue}
    ready: dict[UUID, Decimal] = {}
    for item in db.scalars(select(FoodStockItem).where(FoodStockItem.user_id == user.id, FoodStockItem.status == "active",
                                                       FoodStockItem.kind == "prepared")):
        if item.recipe_id in ids:
            ready[item.recipe_id] = ready.get(item.recipe_id, Decimal(0)) + item.quantity
    return ready


def _day_label(day: date) -> str:
    return f"{WEEKDAYS_FR[day.weekday()]} {day.isoformat()}"


def build_prompt(db: Session, user: User, plan: PulseDietPlan, days: list[date], aliases: dict[str, PulseRecipe],
                 ready: dict[UUID, Decimal]) -> str:
    def macros(recipe: PulseRecipe) -> str:
        known = [f"{getattr(recipe, m)} {label}" for m, label in
                 (("calories", "kcal"), ("protein_g", "g prot."), ("carbs_g", "g gluc."), ("fat_g", "g lip."))
                 if getattr(recipe, m) is not None]
        return ", ".join(known) or "apports inconnus"

    catalogue = "\n".join(
        f"- {alias} | {r.title} | {r.servings} portions | se garde "
        f"{f'{r.shelf_life_days} j' if r.shelf_life_days is not None else 'durée inconnue'} | {macros(r)} par portion"
        f"{f' | {ready[r.id]} portions déjà prêtes' if r.id in ready else ''} | ingrédients : "
        + ", ".join(f"{line['name']} {line['quantity']} {line['unit']}" for line in r.ingredients or [])
        for alias, r in aliases.items()) or "catalogue vide : propose des recettes nouvelles"
    stock_rows = diet.raw_stock(db, user)[:MAX_STOCK_LINES]
    stock = "\n".join(
        f"- {item.name} : {diet.plain(item.quantity)} {item.unit}"
        + (f" ({item.expiry_type} {item.expiry_date.isoformat()})" if item.expiry_date else "")
        for item in stock_rows) or "stock vide"
    equipment = ", ".join(db.scalars(select(PulseOwnedEquipment.name).where(
        PulseOwnedEquipment.user_id == user.id, PulseOwnedEquipment.status == "active"))) or "non renseigné"
    return (
        f"Semaine du {plan.week_start.isoformat()}. Jours à planifier : {', '.join(_day_label(d) for d in days)}.\n"
        f"Consigne de l'utilisateur : {plan.note or 'aucune'}.\n"
        "Par défaut : le déjeuner et le dîner de chaque jour, une ou deux préparations dans la semaine.\n\n"
        f"## Catalogue (repères R…)\n{catalogue}\n\n## Stock (matières premières)\n{stock}\n\n"
        f"## Matériel\n{equipment}\n\n"
        "Nouvelles recettes : repère N1, N2… dans new_recipes, puis cite-les par ce repère. Chaque recette citée par "
        "un repas doit être préparée avant (ou avoir des portions déjà prêtes)."
    )


def output_schema(days: list[date]) -> dict:
    day = {"enum": [d.isoformat() for d in days]}
    number = {"type": ["number", "null"]}
    recipe = {
        "type": "object", "additionalProperties": False,
        "required": ["key", "title", "servings", "portion_weight_g", "ingredients", "steps", "packaging",
                     "shelf_life_days", "calories", "protein_g", "carbs_g", "fat_g"],
        "properties": {
            "key": {"type": "string", "pattern": r"^N\d{1,2}$"}, "title": {"type": "string", "maxLength": 160},
            "servings": {"type": "integer"}, "portion_weight_g": number,
            "ingredients": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["name", "quantity", "unit"],
                "properties": {"name": {"type": "string", "maxLength": 120}, "quantity": {"type": "number"},
                               "unit": {"enum": list(UNITS)}}}},
            "steps": {"type": "array", "items": {"type": "string", "maxLength": 1000}},
            "packaging": {"type": "array", "items": {"type": "string", "maxLength": 1000}},
            "shelf_life_days": {"type": ["integer", "null"]},
            "calories": number, "protein_g": number, "carbs_g": number, "fat_g": number}}
    return {
        "type": "object", "additionalProperties": False,
        "required": ["rationale_fr", "new_recipes", "preparations", "meals"],
        "properties": {
            "rationale_fr": {"type": "string", "maxLength": 600},
            "new_recipes": {"type": "array", "maxItems": MAX_NEW_RECIPES, "items": recipe},
            "preparations": {"type": "array", "maxItems": 14, "items": {
                "type": "object", "additionalProperties": False, "required": ["recipe", "day", "portions"],
                "properties": {"recipe": {"type": "string"}, "day": day, "portions": {"type": "integer"}}}},
            "meals": {"type": "array", "maxItems": 28, "items": {
                "type": "object", "additionalProperties": False, "required": ["day", "slot", "recipe", "portions"],
                "properties": {"day": day, "slot": {"enum": list(SLOTS)}, "recipe": {"type": "string"},
                               "portions": {"type": "number"}}}}}}


# --- Relecture par le code ------------------------------------------------------------------------------------

def _new_recipe(raw: dict) -> RecipeCreate:
    return RecipeCreate(**{k: v for k, v in raw.items() if k != "key"})


def validate(output: dict | None, days: list[date], aliases: dict[str, PulseRecipe],
             ready: dict[UUID, Decimal]) -> list[str]:
    if not isinstance(output, dict):
        return ["sortie illisible"]
    errors: list[str] = []
    allowed = {d.isoformat() for d in days}
    shelf: dict[str, int | None] = {alias: r.shelf_life_days for alias, r in aliases.items()}
    on_hand = {alias: ready.get(r.id, Decimal(0)) for alias, r in aliases.items()}  # portions déjà prêtes
    supply: dict[str, Decimal] = dict(on_hand)
    for raw in output.get("new_recipes") or []:
        key = raw.get("key")
        if key in shelf:
            errors.append(f"repère {key} en double")
            continue
        try:
            recipe = _new_recipe(raw)
        except ValidationError as exc:
            errors.append(f"recette {key} incomplète ({exc.errors()[0].get('loc')})")
            continue
        shelf[key], supply[key] = recipe.shelf_life_days, Decimal(0)
    prepared: dict[str, list[date]] = {}
    for prep in output.get("preparations") or []:
        ref, day, portions = prep.get("recipe"), prep.get("day"), prep.get("portions")
        if ref not in shelf:
            errors.append(f"préparation d'une recette inconnue ({ref})")
            continue
        if day not in allowed:
            errors.append(f"préparation de {ref} hors des jours à planifier ({day})")
            continue
        if not isinstance(portions, int) or not 1 <= portions <= 40:
            errors.append(f"portions de la préparation {ref} hors de 1 à 40")
            continue
        supply[ref] += portions
        prepared.setdefault(ref, []).append(date.fromisoformat(day))
    used = {key for key in shelf if key.startswith("N")} - set(prepared)
    errors.extend(f"recette nouvelle {key} jamais préparée" for key in sorted(used))
    eaten: dict[str, Decimal] = {}
    slots: set[tuple[str, str]] = set()
    for meal in output.get("meals") or []:
        ref, day, slot, portions = meal.get("recipe"), meal.get("day"), meal.get("slot"), meal.get("portions")
        if ref not in shelf:
            errors.append(f"repas avec une recette inconnue ({ref})")
            continue
        if day not in allowed or slot not in SLOTS:
            errors.append(f"repas hors des jours ou des créneaux ({day} {slot})")
            continue
        if (day, slot) in slots:
            errors.append(f"deux repas le même créneau ({day} {slot})")
            continue
        slots.add((day, slot))
        if not isinstance(portions, (int, float)) or not 0 < portions <= 4:
            errors.append(f"portions du repas {day} {slot} hors de 0 à 4")
            continue
        eaten[ref] = eaten.get(ref, Decimal(0)) + Decimal(str(portions))
        when = date.fromisoformat(day)
        before = [d for d in prepared.get(ref, []) if d <= when]
        if not before and on_hand.get(ref, Decimal(0)) <= 0:
            errors.append(f"{ref} mangé le {day} sans préparation avant ni portions prêtes")
        elif before and shelf[ref] is not None and (when - max(before)).days > shelf[ref]:
            errors.append(f"{ref} mangé le {day} après sa durée de conservation")
    for ref, total in eaten.items():
        if total > supply.get(ref, Decimal(0)):
            errors.append(f"{ref} : {total} portions mangées pour {supply.get(ref, 0)} préparées ou prêtes")
    if not output.get("meals"):
        errors.append("aucun repas")
    return errors


# --- Écriture -------------------------------------------------------------------------------------------------

def _write(db: Session, plan: PulseDietPlan, output: dict, days: list[date], aliases: dict[str, PulseRecipe],
           source: str, trace: dict) -> None:
    refs: dict[str, UUID] = {alias: recipe.id for alias, recipe in aliases.items()}
    for raw in output.get("new_recipes") or []:
        recipe = diet.new_recipe(plan.user_id, _new_recipe(raw), source="planner", status="proposed", plan_id=plan.id)
        db.add(recipe)
        db.flush()
        refs[raw["key"]] = recipe.id
    for prep in output["preparations"]:
        db.add(PulsePreparation(user_id=plan.user_id, plan_id=plan.id, recipe_id=refs[prep["recipe"]],
                                planned_day=date.fromisoformat(prep["day"]), portions_planned=prep["portions"],
                                status="planned", missing=[], consumed=[]))
    for meal in output["meals"]:
        db.add(PulseDietPlanMeal(user_id=plan.user_id, plan_id=plan.id, day=date.fromisoformat(meal["day"]),
                                 slot=meal["slot"], recipe_id=refs[meal["recipe"]],
                                 portions=Decimal(str(meal["portions"])).quantize(Decimal("0.01")), status="planned"))
    plan.status, plan.source = "proposed", source
    plan.rationale_fr = (output.get("rationale_fr") or "").strip()[:600] or None
    plan.trace, plan.error = trace, None
    db.commit()


def _fail(db: Session, plan: PulseDietPlan, message: str, trace: dict | None = None) -> None:
    plan.status, plan.error, plan.trace = "failed", message, trace
    db.commit()


def _default_caller(db: Session, plan: PulseDietPlan) -> Caller:
    def call(system: str, prompt: str, schema: dict) -> tuple[dict, str, dict]:
        if cloud.slot_mode(db, SLOT) == "live":
            try:
                result = cloud.structured(db, slot_code=SLOT, app_name="pulse", system=system, user=prompt, schema=schema,
                                          related_entity_type="pulse_diet_plan", related_entity_id=plan.id)
                return result.output, "cloud", {"model": result.model}
            except cloud.CloudError as exc:
                logger.warning("pulse diet planner: cloud failed (%s)", str(exc)[:120])
        if local_executor.slot_mode(db, LOCAL_SLOT) == "live":
            try:
                result = local_executor.structured(slot_code=LOCAL_SLOT, app_name="pulse", system=system, user=prompt,
                                                   schema=schema, max_tokens=LOCAL_MAX_TOKENS,
                                                   related_entity_type="pulse_diet_plan", related_entity_id=plan.id)
                return result.output, "local", {"model": "local"}
            except local_executor.LocalExecutorError as exc:
                raise PlannerUnavailableError("Le modèle local n'a pas répondu ; redemande la semaine plus tard.") from exc
        raise PlannerUnavailableError(NO_BRAIN)
    return call
