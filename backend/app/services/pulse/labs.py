"""Analyses de sang Pulse (doc 34 « blood tests », 2026-10-22) — entrée par Nourrir l'IA, jamais par un autre bouton.

1. Analyse d'un dépôt (job `ai.knowledge_inbox`) : si le texte lu (OCR des PDF/photos) ressemble à une prise de sang,
   les valeurs sont extraites (rôle santé, slot `pulse.lab_results_extract`, sinon modèle local
   `pulse.lab_results_extract_local`) et placées dans le brouillon avec la destination proposée `lab_results`.
   Aucun cerveau branché → brouillon sans valeurs : l'utilisateur les saisit dans la même fenêtre.
2. Validation par l'utilisateur vers `lab_results` (accord « medical » exigé) : les valeurs corrigées entrent dans
   `pulse_lab_results` ; rien n'entre dans la mémoire vectorisée. Supprimer l'élément supprime ses valeurs.
3. Santé lit la dernière valeur de chaque analyse, la précédente et sa place par rapport à la norme DU LABO
   (below/within/above) : un repère factuel, jamais un diagnostic.
"""

import logging
import re
import unicodedata
from datetime import date
from decimal import InvalidOperation
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.ai import KnowledgeInboxItem
from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.pulse import PulseLabResult
from app.schemas.pulse_labs import (
    LabHistory,
    LabLatestList,
    LabLatestRead,
    LabPrevious,
    LabResultCreate,
    LabResultIn,
    LabResultRead,
)
from app.services.ai import cloud, local_executor
from app.services.events.emitter import build_event
from app.services.pulse import health_consent

logger = logging.getLogger(__name__)

SLOT = "pulse.lab_results_extract"
LOCAL_SLOT = "pulse.lab_results_extract_local"
DESTINATION = "lab_results"
MAX_RESULTS = 80
TEXT_LIMIT = 12000
LOCAL_MAX_TOKENS = 6000
# Mots d'un compte rendu de biologie : il en faut plusieurs pour proposer la destination « analyses ».
_MARKERS = ("hemoglobine", "hematies", "leucocytes", "plaquettes", "ferritine", "glycemie", "cholesterol",
            "triglycerides", "creatinine", "tsh", "vitamine d", "valeurs de reference", "biologie medicale",
            "laboratoire", "hematocrite", "transaminases", "crp", "testosterone", "cortisol", "uree", "fer serique",
            "vgm", "hba1c", "bilan sanguin", "prise de sang", "numeration")
SYSTEM = (
    "Tu lis le compte rendu d'une prise de sang (texte issu d'un OCR, parfois abîmé). Tu recopies chaque analyse : "
    "nom en français tel qu'écrit (« Ferritine », « Hémoglobine »), résultat chiffré (point décimal) ou texte "
    "(« négatif »), unité, et la norme du laboratoire (bornes basse et haute, ou texte). Tu n'inventes rien : une "
    "valeur illisible est omise, une norme absente reste null. Tu ne donnes aucune interprétation. measured_on = "
    "date du prélèvement (AAAA-MM-JJ) si elle est écrite, sinon null. Réponds uniquement selon le schéma JSON."
)


def analyte_key(name: str) -> str:
    """« Hémoglobine glyquée (HbA1c) » → « hemoglobine glyquee hba1c » : regroupe une analyse d'un compte rendu à l'autre."""
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(re.findall(r"[a-z0-9]+", folded))


def looks_like_lab(text: str, context: str | None = None) -> bool:
    folded = analyte_key(f"{context or ''} {text}")
    if "prise de sang" in folded or "bilan sanguin" in folded:
        return True
    return sum(marker in folded for marker in _MARKERS) >= 3


def schema() -> dict:
    number = {"type": ["number", "null"]}
    text = {"type": ["string", "null"]}
    return {
        "type": "object", "additionalProperties": False, "required": ["measured_on", "results"],
        "properties": {
            "measured_on": {"type": ["string", "null"], "pattern": r"^\d{4}-\d{2}-\d{2}$"},
            "results": {"type": "array", "maxItems": MAX_RESULTS, "items": {
                "type": "object", "additionalProperties": False,
                "required": ["analyte", "value", "value_text", "unit", "ref_low", "ref_high", "ref_text"],
                "properties": {"analyte": {"type": "string", "maxLength": 120}, "value": number, "value_text": text,
                               "unit": text, "ref_low": number, "ref_high": number, "ref_text": text}}}}}


def parse(output: dict | None) -> tuple[list[dict], str | None]:
    """Sortie du modèle relue : lignes valides seulement (nom + valeur), date au bon format ou rien."""
    if not isinstance(output, dict):
        return [], None
    results = []
    for raw in (output.get("results") or [])[:MAX_RESULTS]:
        try:
            clean = {k: (str(v) if k in ("value", "ref_low", "ref_high") and v is not None else v)
                     for k, v in raw.items()}
            results.append(LabResultIn(**clean).model_dump(mode="json"))
        except (ValidationError, TypeError, AttributeError, InvalidOperation):
            continue
    measured = output.get("measured_on")
    try:
        measured = date.fromisoformat(measured).isoformat() if isinstance(measured, str) else None
    except ValueError:
        measured = None
    return results, measured


def extract(db: Session, *, text: str, item_id: UUID | None = None) -> tuple[list[dict], str | None, str | None]:
    """(valeurs, date, moteur) ; aucun cerveau branché ou échec → ([], None, None), jamais d'invention."""
    prompt = f"Compte rendu :\n{text[:TEXT_LIMIT]}"
    if cloud.slot_mode(db, SLOT) == "live":
        try:
            output = cloud.structured(db, slot_code=SLOT, app_name="pulse", system=SYSTEM, user=prompt, schema=schema(),
                                      related_entity_type="knowledge_inbox_item", related_entity_id=item_id).output
            results, measured = parse(output)
            return results, measured, "cloud"
        except cloud.CloudError as exc:
            logger.warning("lab extraction: cloud failed (%s)", str(exc)[:120])
    if local_executor.slot_mode(db, LOCAL_SLOT) == "live":
        try:
            output = local_executor.structured(slot_code=LOCAL_SLOT, app_name="pulse", system=SYSTEM, user=prompt,
                                               schema=schema(), max_tokens=LOCAL_MAX_TOKENS,
                                               related_entity_type="knowledge_inbox_item", related_entity_id=item_id).output
            results, measured = parse(output)
            return results, measured, "local"
        except local_executor.LocalExecutorError as exc:
            logger.warning("lab extraction: local failed (%s)", str(exc)[:120])
    return [], None, None


# --- Validation depuis Nourrir l'IA --------------------------------------------------------------------------

def store_from_inbox(db: Session, *, current_user: User, item: KnowledgeInboxItem, final: dict) -> int:
    """Écrit les valeurs corrigées du brouillon ; accord « medical » exigé ; au moins une valeur et une date."""
    health_consent.require(db, current_user, "medical")
    lines = [LabResultIn(**line) for line in final.get("lab_results") or []]
    if not lines:
        raise ValueError("Aucune valeur à enregistrer : ajoute au moins une analyse.")
    if not final.get("measured_on"):
        raise ValueError("Date du prélèvement manquante.")
    measured = date.fromisoformat(str(final["measured_on"]))
    for index, line in enumerate(lines):
        db.add(PulseLabResult(user_id=current_user.id, inbox_item_id=item.id, analyte=line.analyte,
                              analyte_key=analyte_key(line.analyte), value=line.value, value_text=line.value_text,
                              unit=line.unit, ref_low=line.ref_low, ref_high=line.ref_high, ref_text=line.ref_text,
                              measured_on=measured, source="inbox", idempotency_key=f"inbox:{item.id}:{index}"))
    _emit(db, current_user.id, {"source": "inbox", "count": len(lines)}, f"inbox.{item.id}")
    return len(lines)


def delete_for_item(db: Session, *, user_id: UUID, item_id: UUID) -> int:
    return db.execute(delete(PulseLabResult).where(PulseLabResult.user_id == user_id,
                                                   PulseLabResult.inbox_item_id == item_id)).rowcount or 0


# --- Saisie, lectures --------------------------------------------------------------------------------------

def create(db: Session, *, current_user: User, payload: LabResultCreate, idempotency_key: str) -> tuple[LabResultRead, bool]:
    health_consent.require(db, current_user, "medical")
    existing = db.scalar(select(PulseLabResult).where(PulseLabResult.user_id == current_user.id,
                                                      PulseLabResult.idempotency_key == idempotency_key))
    if existing is not None:
        return LabResultRead.model_validate(existing), True
    row = PulseLabResult(user_id=current_user.id, analyte=payload.analyte, analyte_key=analyte_key(payload.analyte),
                         value=payload.value, value_text=payload.value_text, unit=payload.unit, ref_low=payload.ref_low,
                         ref_high=payload.ref_high, ref_text=payload.ref_text, measured_on=payload.measured_on,
                         source="manual", idempotency_key=idempotency_key)
    db.add(row)
    db.flush()
    _emit(db, current_user.id, {"source": "manual", "count": 1}, f"manual.{row.id}")
    db.refresh(row)
    read = LabResultRead.model_validate(row)
    db.commit()
    return read, False


def remove(db: Session, *, current_user: User, result_id: UUID) -> None:
    row = db.get(PulseLabResult, result_id)
    if row is None or row.user_id != current_user.id:
        raise LookupError("Lab result not found.")
    db.delete(row)
    db.commit()


def position(row: PulseLabResult) -> str:
    if row.value is None or (row.ref_low is None and row.ref_high is None):
        return "unknown"
    if row.ref_low is not None and row.value < row.ref_low:
        return "below"
    if row.ref_high is not None and row.value > row.ref_high:
        return "above"
    return "within"


def latest(db: Session, *, current_user: User) -> LabLatestList:
    health_consent.require(db, current_user, "medical")
    rows = list(db.scalars(select(PulseLabResult).where(PulseLabResult.user_id == current_user.id)
                           .order_by(PulseLabResult.measured_on.desc(), PulseLabResult.created_at.desc())))
    groups: dict[str, list[PulseLabResult]] = {}
    for row in rows:
        groups.setdefault(row.analyte_key, []).append(row)
    items = []
    for history in groups.values():
        last = history[0]
        before = history[1] if len(history) > 1 else None
        items.append(LabLatestRead(
            **LabResultRead.model_validate(last).model_dump(), position=position(last), count=len(history),
            previous=LabPrevious(value=before.value, value_text=before.value_text, measured_on=before.measured_on)
            if before else None))
    items.sort(key=lambda item: item.analyte.lower())
    pending = db.scalar(select(func.count()).select_from(KnowledgeInboxItem).where(
        KnowledgeInboxItem.user_id == current_user.id, KnowledgeInboxItem.status == "to_validate",
        KnowledgeInboxItem.extraction_draft["proposed_destination"].astext == DESTINATION)) or 0
    return LabLatestList(items=items, pending_inbox=pending)


def history(db: Session, *, current_user: User, key: str) -> LabHistory:
    health_consent.require(db, current_user, "medical")
    rows = db.scalars(select(PulseLabResult).where(PulseLabResult.user_id == current_user.id,
                                                   PulseLabResult.analyte_key == analyte_key(key))
                      .order_by(PulseLabResult.measured_on.desc()))
    return LabHistory(items=[LabResultRead.model_validate(row) for row in rows])


def out_of_range_lines(db: Session, user: User) -> list[str]:
    """Pour le planificateur de diète : dernières valeurs hors de la norme du labo, si l'accord « medical » est actif."""
    try:
        data = latest(db, current_user=user)
    except health_consent.ConsentRequiredError:
        return []
    labels = {"below": "sous la norme", "above": "au-dessus de la norme"}
    return [f"- {item.analyte} : {item.value} {item.unit or ''} ({labels[item.position]} du labo "
            f"{item.ref_low if item.ref_low is not None else '…'}–{item.ref_high if item.ref_high is not None else '…'}, "
            f"le {item.measured_on.isoformat()})" for item in data.items if item.position in labels]


def _emit(db: Session, user_id: UUID, payload: dict, ref: str) -> None:
    db.add(build_event(db, user_id=user_id, event_type="pulse.lab_results.recorded", payload=payload,
                       idempotency_key=f"pulse.lab_results.recorded.{ref}", source_app=SourceApp.pulse,
                       privacy_level=PrivacyLevel.very_high))
