"""Estimation des apports d'un repas décrit hors stock (kit Pulse P03 « Autre », doc 40 §10.1 `pulse.meal_estimate`).

Modèle local seulement (slot `pulse.meal_estimate`, semé éteint) : description → kcal, protéines, glucides, lipides,
confiance et hypothèses (portion supposée…). Bornes vérifiées par le code ; sortie invalide ou slot éteint → aucune
estimation (le repas reste « apports non renseignés »). Toujours marquée « estimation », corrigeable avant validation.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.services.ai import local_executor

SLOT = "pulse.meal_estimate"
SYSTEM = (
    "Tu estimes les apports d'un repas décrit en quelques mots par un utilisateur français : énergie (kcal), "
    "protéines, glucides et lipides en grammes, pour ce qu'il a réellement mangé. Si la quantité n'est pas dite, "
    "suppose une portion adulte courante et dis-le dans assumptions_fr. confidence = high si les quantités sont "
    "claires, medium sinon, low si le repas est vague. Réponds uniquement selon le schéma JSON."
)
LIMITS = {"calories": 5000, "protein_g": 400, "carbs_g": 800, "fat_g": 400}
WARNING = "Apports estimés depuis ta description : vérifie-les avant de valider."


@dataclass
class Estimate:
    calories: Decimal
    protein_g: Decimal
    carbs_g: Decimal
    fat_g: Decimal
    confidence: Decimal
    assumptions_fr: str


def schema() -> dict:
    number = {"type": "number"}
    return {"type": "object", "additionalProperties": False,
            "required": ["calories", "protein_g", "carbs_g", "fat_g", "confidence", "assumptions_fr"],
            "properties": {"calories": number, "protein_g": number, "carbs_g": number, "fat_g": number,
                           "confidence": {"enum": ["high", "medium", "low"]},
                           "assumptions_fr": {"type": "string", "maxLength": 300}}}


def parse(output: dict | None) -> Estimate | None:
    if not isinstance(output, dict):
        return None
    values = {}
    for key, limit in LIMITS.items():
        value = output.get(key)
        if not isinstance(value, (int, float)) or not 0 <= value <= limit:
            return None
        values[key] = Decimal(str(value)).quantize(Decimal("0.1"))
    confidence = {"high": Decimal("0.85"), "medium": Decimal("0.6"), "low": Decimal("0.35")}.get(output.get("confidence"))
    if confidence is None:
        return None
    return Estimate(**values, confidence=confidence, assumptions_fr=str(output.get("assumptions_fr") or "").strip()[:300])


def estimate(db: Session, description: str) -> Estimate | None:
    if local_executor.slot_mode(db, SLOT) != "live":
        return None
    try:
        result = local_executor.structured(slot_code=SLOT, app_name="pulse", system=SYSTEM,
                                           user=f"Repas : {description[:600]}", schema=schema(), max_tokens=300,
                                           related_entity_type="pulse_meal")
    except local_executor.LocalExecutorError:
        return None
    return parse(result.output)
