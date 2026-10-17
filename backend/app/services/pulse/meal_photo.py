"""Photo d'un repas (PUL-02, doc 37 §5.3, doc 40 §10.1).

Photo → service local d'analyse d'image (tâche pulse.meal_photo_macros) → réponse
validée strictement → brouillon de repas : macros estimées (toujours à vérifier),
aliments vus comparés au stock pour la proposition de décompte. Rien n'est
enregistré ni décompté avant la validation PUL-03 (meals.confirm_meal).

La photo n'est jamais conservée : seule son empreinte. Une analyse en échec ne crée
pas de brouillon ; l'écran garde la photo et propose la saisie au texte.
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.imperium import PulseMeal
from app.schemas.pulse_meals import MealRead
from app.services.ai import ocr
from app.services.ai.knowledge_files import extension, safe_filename
from app.services.pulse import meals
from app.services.pulse.pantry_scan import ACCEPTED_EXTENSIONS, MAX_BYTES, _unit_interval
from app.services.pulse.stock_declaration import DeclaredLine

TASK = "pulse.meal_photo_macros"
PROMPT = "ocr_meal_photo_macros"
LOW_CONFIDENCE = 0.6
MAX_FOODS = 30
ESTIMATED = "Macros estimées depuis la photo : vérifie-les avant de valider."
_DEFAULT = object()
_LIMITS = {"calories": 99999.9, "protein_g": 9999.9, "carbs_g": 9999.9, "fat_g": 9999.9}

AnalyzeImage = Callable[[bytes, str | None], dict]

MESSAGES = {
    "disabled": "L'analyse des photos n'est pas encore activée. Décris le repas au texte.",
    "unreachable": "Le service d'analyse ne répond pas. Réessaie dans un moment ou décris le repas au texte.",
    "unreadable": "Analyse illisible. Reprends la photo ou décris le repas au texte.",
}


class MealPhotoFileError(ValueError):
    pass


class MealPhotoAnalysisError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(MESSAGES[reason])
        self.reason = reason


@dataclass
class DetectedFood(DeclaredLine):
    confidence: float | None = None


def create_photo_draft(
    db: Session,
    *,
    current_user: User,
    filename: str,
    content_type: str | None,
    stream: BinaryIO,
    idempotency_key: str,
    eaten_at: datetime | None = None,
    analyze: AnalyzeImage | None | object = _DEFAULT,
) -> tuple[MealRead, bool]:
    if extension(safe_filename(filename)) not in ACCEPTED_EXTENSIONS:
        raise MealPhotoFileError("Fichier refusé : photo (JPEG, PNG, WebP, HEIC) seulement.")
    data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise MealPhotoFileError("Fichier refusé : 25 Mo maximum.")
    if not data:
        raise MealPhotoFileError("Fichier refusé : vide.")
    sha256 = hashlib.sha256(data).hexdigest()
    fingerprint = meals.food_stock.request_hash(
        "pulse.meal.photo", {"sha256": sha256, "eaten_at": eaten_at.isoformat() if eaten_at else None}
    )
    previous = meals.find_draft(db, current_user, idempotency_key, fingerprint)
    if previous is not None:
        return previous, True
    analyzer = _default_analyzer() if analyze is _DEFAULT else analyze
    if analyzer is None:
        raise MealPhotoAnalysisError("disabled")
    try:
        parsed = parse_result(analyzer(data, content_type))
    except ocr.OcrServiceUnreachable as exc:
        raise MealPhotoAnalysisError("unreachable") from exc
    except ocr.OcrError as exc:
        raise MealPhotoAnalysisError("unreadable") from exc
    finally:
        del data  # la photo n'est jamais conservée
    if parsed is None:
        raise MealPhotoAnalysisError("unreadable")
    foods, macros, quality, confidence, summary, model_warnings = parsed
    lines, warnings = meals.propose(
        db, current_user, [(food, food.confidence is not None and food.confidence < LOW_CONFIDENCE) for food in foods]
    )
    estimated = any(value is not None for value in macros.values())
    head = [ESTIMATED if estimated else meals.NO_MACROS]
    if quality == "poor":
        head.append("Photo trop floue. Reprendre une photo ?")
    if confidence is not None and confidence < LOW_CONFIDENCE:
        head.append("Estimation peu sûre : vérifie les portions.")
    description = summary or "Repas en photo"
    meal = PulseMeal(
        user_id=current_user.id, status="draft", label=description[:120], description=description, source="photo",
        eaten_at=eaten_at or datetime.now(UTC),
        **{macro: Decimal(str(round(value, 1))) if value is not None else None for macro, value in macros.items()},
        macros_estimated=estimated, confidence=Decimal(str(confidence)) if confidence is not None else None,
        photo_sha256=sha256, proposal=[line.model_dump(mode="json") for line in lines],
        warnings=(head + model_warnings + warnings)[:20], idempotency_key=idempotency_key, request_hash=fingerprint,
    )
    return meals.save_draft(db, meal), False


# ---------- lecture de la réponse du modèle (doc 37 §5.3) ----------

def parse_result(payload: dict | None):
    """(aliments, macros, qualité, confiance, résumé, avertissements) ou None si la forme n'est pas celle du prompt."""
    if not isinstance(payload, dict):
        return None
    structured = payload.get("structured_result")
    if not isinstance(structured, dict) or not isinstance(structured.get("detected_foods"), list):
        return None
    raw_macros = structured.get("macros", {})
    if not isinstance(raw_macros, dict):
        return None
    foods = []
    for raw in structured["detected_foods"][:MAX_FOODS]:
        if not isinstance(raw, dict) or not isinstance(raw.get("name_fr"), str) or not raw["name_fr"].strip():
            continue
        quantity = _positive(raw.get("estimated_quantity"))
        unit = raw.get("unit") if raw.get("unit") in ("g", "ml", "piece") else "piece"
        assumed = quantity is None or raw.get("unit") not in ("g", "ml", "piece")
        foods.append(DetectedFood(
            name=raw["name_fr"].strip()[:120], quantity=Decimal(str(quantity)) if quantity else Decimal("1"), unit=unit,
            quantity_assumed=assumed, confidence=_unit_interval(raw.get("confidence")),
        ))
    macros = {macro: _positive(raw_macros.get(macro), limit=limit, allow_zero=True) for macro, limit in _LIMITS.items()}
    quality = structured.get("image_quality") if structured.get("image_quality") in ("good", "acceptable", "poor") else None
    summary = payload["summary"].strip()[:500] if isinstance(payload.get("summary"), str) else ""
    summary = summary or None
    warnings = [w[:200] for w in payload["warnings"] if isinstance(w, str)] if isinstance(payload.get("warnings"), list) else []
    return foods, macros, quality, _unit_interval(payload.get("confidence_score")), summary, warnings


def _positive(value, *, limit: float = 1_000_000, allow_zero: bool = False) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    if value < 0 or (value == 0 and not allow_zero) or value > limit:
        return None
    return value


def _default_analyzer() -> AnalyzeImage | None:
    if not ocr.ocr_available():
        return None
    prompt = ocr.load_prompt(PROMPT)
    return lambda data, content_type: ocr.analyze_image(data, task=TASK, prompt=prompt, content_type=content_type)
