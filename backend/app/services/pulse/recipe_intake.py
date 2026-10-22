"""Recette déposée dans Nourrir l'IA (bloc 1, 2026-10-22) : reconnue à l'analyse, lue en recette structurée par le
modèle local (slot `pulse.recipe_extract`, semé éteint), corrigée par l'utilisateur, puis rangée dans le catalogue
Pulse (destination `recipe`). Sans modèle, la fenêtre propose une recette vide à remplir. Rien n'est inventé : une
quantité absente du texte reste à saisir ; les apports par portion ne sont jamais devinés.
"""

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.ai import KnowledgeInboxItem
from app.models.auth import User
from app.schemas.pulse_diet import RecipeCreate
from app.services.ai import local_executor
from app.services.pulse import diet
from app.services.pulse.labs import analyte_key

SLOT = "pulse.recipe_extract"
DESTINATION = "recipe"
_MARKERS = ("ingredients", "preparation", "etapes", "recette", "cuisson", "prechauffer", "cuillere a soupe",
            "cuillere a cafe", "pincee", "personnes", "portions", "faire revenir", "melanger", "laisser mijoter")
SYSTEM = (
    "Tu recopies une recette en données structurées : titre, nombre de portions, ingrédients avec quantité et unité "
    "(g, kg, ml, cl, l ou piece ; convertis cuillère à soupe = 15 ml, cuillère à café = 5 ml, pincée = 1 g), étapes "
    "courtes dans l'ordre, conditionnement et conservation s'ils sont écrits, durée de conservation en jours si elle "
    "est écrite. Tu n'inventes rien : un ingrédient sans quantité reçoit la quantité la plus prudente écrite ou est "
    "omis. Réponds uniquement selon le schéma JSON."
)


def looks_like_recipe(text: str, context: str | None = None) -> bool:
    folded = analyte_key(f"{context or ''} {text}")
    return "recette" in analyte_key(context or "") or sum(marker in folded for marker in _MARKERS) >= 3


def schema() -> dict:
    text = {"type": "string"}
    return {"type": "object", "additionalProperties": False,
            "required": ["title", "servings", "ingredients", "steps", "packaging", "shelf_life_days"],
            "properties": {"title": text, "servings": {"type": "integer"},
                           "ingredients": {"type": "array", "maxItems": 40, "items": {
                               "type": "object", "additionalProperties": False, "required": ["name", "quantity", "unit"],
                               "properties": {"name": text, "quantity": {"type": "number"},
                                              "unit": {"enum": ["g", "kg", "ml", "cl", "l", "piece"]}}}},
                           "steps": {"type": "array", "maxItems": 40, "items": text},
                           "packaging": {"type": "array", "maxItems": 20, "items": text},
                           "shelf_life_days": {"type": ["integer", "null"]}}}


def extract(db: Session, *, text: str, item_id=None) -> tuple[dict | None, str | None]:
    """(recette relue, moteur) ; modèle éteint ou sortie invalide → (None, None)."""
    if local_executor.slot_mode(db, SLOT) != "live":
        return None, None
    try:
        output = local_executor.structured(slot_code=SLOT, app_name="pulse", system=SYSTEM, user=f"Texte :\n{text[:12000]}",
                                           schema=schema(), max_tokens=4000, related_entity_type="knowledge_inbox_item",
                                           related_entity_id=item_id).output
        return RecipeCreate(**output).model_dump(mode="json"), "local"
    except (local_executor.LocalExecutorError, ValidationError, TypeError):
        return None, None


def store_from_inbox(db: Session, *, current_user: User, item: KnowledgeInboxItem, final: dict) -> str:
    """Recette corrigée → catalogue (idempotent par élément) ; ValueError si elle est incomplète."""
    try:
        payload = RecipeCreate(**(final.get("recipe") or {}))
    except ValidationError as exc:
        raise ValueError("Recette incomplète : titre, portions, au moins un ingrédient et une étape.") from exc
    recipe, _ = diet.create_recipe(db, current_user=current_user, payload=payload, idempotency_key=f"inbox:{item.id}",
                                   source="inbox")
    return recipe.title
