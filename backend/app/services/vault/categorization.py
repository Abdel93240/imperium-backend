"""Catégorie suggérée d'une transaction (doc 42 §7.0–§7.2, décision utilisateur 2026-10-16).

Ordre de résolution, DÉTERMINISTE d'abord :
1. part utilisateur de la table (user_category_memory) ;
2. table en dur des libellés connus (LABEL_TABLE), comparaison normalisée ;
3. libellé inconnu seulement → modèle local, sortie validée contre le référentiel ;
4. sinon aucune catégorie : l'utilisateur choisit. Jamais de rangement silencieux.
Le livre business/perso est déduit de la catégorie (vault.category_map), jamais choisi.
"""

import json
import logging
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.vault import UserCategoryMemory
from app.services.params import get_parameter
from app.services.vault.weekly import DEFAULT_CATEGORY_MAP

logger = logging.getLogger(__name__)

HIGH_CONFIDENCE_CONFIRMATIONS = 3  # doc 42 §7.2
_DEFAULT = object()
_NOISE_TOKENS = {"cb", "carte", "achat", "paiement", "facture"}

ModelCall = Callable[[str], dict]

# Table en dur : mot-clé normalisé → catégorie du référentiel (vault.category_map).
LABEL_TABLE: dict[str, str] = {
    # Revenus VTC (business)
    "bolt": "bolt", "uber": "uber", "heetch": "heetch", "free now": "vtc", "freenow": "vtc", "marcel": "vtc",
    "le cab": "vtc", "g7": "vtc",
    # Carburant (business)
    "total energies": "carburant", "totalenergies": "carburant", "esso": "carburant", "shell": "carburant",
    "bp": "carburant", "avia": "carburant", "agip": "carburant", "station u": "carburant",
    "intermarche carburant": "carburant", "leclerc carburant": "carburant", "carrefour station": "carburant",
    # Charges et outils VTC (business)
    "urssaf": "urssaf", "dgfip": "tax", "impots gouv": "tax", "norauto": "entretien", "feu vert": "entretien",
    "midas": "entretien", "speedy": "entretien", "point s": "entretien", "euromaster": "entretien",
    "hiscox": "assurance pro", "axa pro": "assurance pro",
    # Courses (perso)
    "carrefour": "courses", "leclerc": "courses", "auchan": "courses", "lidl": "courses", "aldi": "courses",
    "intermarche": "courses", "monoprix": "courses", "franprix": "courses", "casino": "courses",
    "picard": "courses", "super u": "courses", "hyper u": "courses", "netto": "courses", "grand frais": "courses",
    # Restaurant (perso)
    "mcdonald": "restaurant", "mcdonalds": "restaurant", "burger king": "restaurant", "kfc": "restaurant",
    "quick": "restaurant", "deliveroo": "restaurant", "uber eats": "restaurant", "just eat": "restaurant",
    # Téléphone et abonnements (perso)
    "orange": "telephone", "sfr": "telephone", "bouygues telecom": "telephone", "free mobile": "telephone",
    "sosh": "telephone", "red by sfr": "telephone",
    "netflix": "abonnements", "spotify": "abonnements", "disney plus": "abonnements", "amazon prime": "abonnements",
    "deezer": "abonnements", "canal": "abonnements",
    # Santé, vêtements, loisirs (perso)
    "pharmacie": "santé", "doctolib": "santé", "ameli": "santé",
    "zara": "vêtements", "h m": "vêtements", "kiabi": "vêtements", "primark": "vêtements",
    "decathlon": "loisirs", "fnac": "loisirs", "cinema": "loisirs", "ugc": "loisirs", "pathe": "loisirs",
}


class CategoryValidationError(ValueError):
    pass


@dataclass
class CategorySuggestion:
    label_key: str
    category: str | None
    book: str | None
    source: str  # user_memory | table | ai | none
    confidence: str | None  # high | medium | low
    confirmations: int = 0


def normalize_label(label: str | None) -> str:
    """Casse, accents, ponctuation, références chiffrées (n° de carte, de magasin) ignorés."""
    if not label:
        return ""
    text = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode("ascii").lower()
    tokens = re.sub(r"[^a-z0-9]+", " ", text).split()
    return " ".join(token for token in tokens if not any(char.isdigit() for char in token) and token not in _NOISE_TOKENS)


def referential_from_map(category_map: dict) -> dict[str, tuple[str, str]]:
    """catégorie → (livre, sens) à partir de vault.category_map."""
    referential: dict[str, tuple[str, str]] = {}
    for key, values in category_map.items():
        book = "business" if key.startswith("business") else "personal"
        kind = "income" if key.endswith("income") else "expense"
        for value in values:
            referential.setdefault(value.strip().lower(), (book, kind))
    return referential


def get_referential(db: Session) -> dict[str, tuple[str, str]]:
    value = get_parameter(db, "vault.category_map", default=DEFAULT_CATEGORY_MAP)
    return referential_from_map(value if isinstance(value, dict) else DEFAULT_CATEGORY_MAP)


def lookup_table(label: str, *, referential: dict[str, tuple[str, str]]) -> tuple[str, str] | None:
    key = normalize_label(label)
    if not key:
        return None
    padded = f" {key} "
    # Mot-clé le plus long d'abord (« uber eats » avant « uber »).
    for keyword in sorted(LABEL_TABLE, key=len, reverse=True):
        if f" {keyword} " in padded:
            category = LABEL_TABLE[keyword]
            if category in referential:
                return category, referential[category][0]
    return None


def suggest_from_model(
    label: str,
    *,
    referential: dict[str, tuple[str, str]],
    call_model: ModelCall | None,
    amount_cents: int | None = None,
    transaction_type: str | None = None,
) -> CategorySuggestion:
    key = normalize_label(label)
    none = CategorySuggestion(label_key=key, category=None, book=None, source="none", confidence=None)
    if call_model is None or not key:
        return none
    prompt = (
        "Tu catégorises une transaction pour une application personnelle. "
        'Réponds en JSON strict : {"category": "<une catégorie de la liste>", "confidence": 0.0-1.0}. '
        f"Catégories autorisées : {json.dumps(sorted(referential), ensure_ascii=False)}. "
        f"Libellé : {label}. Montant (centimes) : {amount_cents}. Sens : {transaction_type}."
    )
    try:
        raw = call_model(prompt)
        category = str(raw.get("category", "")).strip().lower() if isinstance(raw, dict) else ""
    except Exception:  # noqa: BLE001 - le modèle ne bloque jamais la saisie
        logger.warning("Category model call failed; no suggestion.")
        return none
    if category not in referential:
        return none
    return CategorySuggestion(label_key=key, category=category, book=referential[category][0], source="ai", confidence="low")


def suggest_category(
    db: Session,
    *,
    current_user: User,
    label: str,
    amount_cents: int | None = None,
    transaction_type: str | None = None,
    call_model: ModelCall | None | object = _DEFAULT,
) -> CategorySuggestion:
    referential = get_referential(db)
    key = normalize_label(label)
    if key:
        memory = _memory(db, current_user=current_user, label_key=key)
        if memory is not None and memory.category in referential:
            confidence = "high" if memory.confirmations >= HIGH_CONFIDENCE_CONFIRMATIONS else "medium"
            return CategorySuggestion(key, memory.category, referential[memory.category][0], "user_memory", confidence,
                                      memory.confirmations)
        hit = lookup_table(label, referential=referential)
        if hit is not None:
            return CategorySuggestion(key, hit[0], hit[1], "table", "high")
    model = _default_model() if call_model is _DEFAULT else call_model
    return suggest_from_model(label, referential=referential, call_model=model, amount_cents=amount_cents,
                              transaction_type=transaction_type)


def confirm_category(db: Session, *, current_user: User, label: str, category: str) -> UserCategoryMemory:
    """Validation par l'utilisateur : le couple rejoint sa part de la table."""
    referential = get_referential(db)
    key = normalize_label(label)
    category = category.strip().lower()
    if not key:
        raise CategoryValidationError("label is empty once normalized.")
    if category not in referential:
        raise CategoryValidationError("category is not in the referential.")
    now = datetime.now(UTC)
    memory = _memory(db, current_user=current_user, label_key=key)
    if memory is None:
        memory = UserCategoryMemory(user_id=current_user.id, label_key=key, sample_label=label.strip()[:200],
                                    category=category, confirmations=1, last_confirmed_at=now)
        db.add(memory)
    elif memory.category == category:
        memory.confirmations += 1
        memory.last_confirmed_at = now
    else:
        memory.category = category
        memory.confirmations = 1
        memory.last_confirmed_at = now
    db.commit()
    return memory


def _memory(db: Session, *, current_user: User, label_key: str) -> UserCategoryMemory | None:
    return db.scalar(
        select(UserCategoryMemory).where(
            UserCategoryMemory.user_id == current_user.id, UserCategoryMemory.label_key == label_key
        )
    )


def _default_model() -> ModelCall | None:
    """Modèle local seulement s'il est activé ; en dry-run, aucune suggestion IA."""
    from app.services.ai.providers.qwen import QwenClient

    client = QwenClient()
    if client._should_dry_run():  # noqa: SLF001 - même règle que l'adaptateur Qwen
        return None
    return lambda prompt: client.call(prompt=prompt, mode="vault_category")
