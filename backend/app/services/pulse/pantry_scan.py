"""Scan du placard / frigo (PUL-13, doc 37 §5, doc 40 §11.1).

Photo → service local d'analyse d'image (tâche pulse.kitchen_inventory_photo) →
réponse validée strictement → comparaison au stock actif → proposition d'ajouts et
de mises à jour. Rien n'entre au stock avant la validation, qui ne garde que les
lignes renvoyées par l'utilisateur. Une mise à jour porte la version lue de la ligne
de stock : version dépassée → conflit, toute la validation est annulée.

La photo n'est jamais conservée : seuls son empreinte, la proposition et le résultat.
Un produit absent de la photo n'est pas retiré du stock (la photo ne montre qu'une partie).
"""

import hashlib
import re
import unicodedata
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import BinaryIO
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.imperium import FoodStockItem, PulsePantryScan
from app.schemas.pulse import FoodStockItemRead, PantryScanLineRead, PantryScanRead, PantryScanValidateRequest
from app.services.ai import ocr
from app.services.ai.knowledge_files import extension, safe_filename
from app.services.events.emitter import build_event

TASK = "pulse.kitchen_inventory_photo"
PROMPT = "ocr_kitchen_inventory"
MAX_BYTES = 25 * 1024 * 1024
ACCEPTED_EXTENSIONS = frozenset({"jpg", "jpeg", "png", "webp", "heic"})
CATEGORIES = frozenset({"vegetable", "fruit", "dairy", "meat", "fish", "dry", "condiment", "drink", "other"})
UNITS = frozenset({"piece", "g", "kg", "ml", "l"})
DLC_CATEGORIES = frozenset({"dairy", "meat", "fish"})  # date visible proposée en DLC, sinon DDM
LOW_CONFIDENCE = 0.6
EMPTY_CONFIDENCE = 0.3
MAX_ITEMS = 100
_DEFAULT = object()

AnalyzeImage = Callable[[bytes, str | None], dict]

MESSAGES = {
    "disabled": "L'analyse des photos n'est pas encore activée. Ajoute les produits à la main.",
    "unreachable": "Le service d'analyse ne répond pas. Réessaie dans un moment ou ajoute les produits à la main.",
    "unreadable": "Analyse illisible. Reprends la photo ou ajoute les produits à la main.",
}


class PantryScanFileError(ValueError):
    pass


class PantryScanNotFoundError(ValueError):
    pass


class PantryScanStateError(ValueError):
    pass


class PantryScanVersionConflictError(ValueError):
    def __init__(self, current: FoodStockItemRead) -> None:
        super().__init__("A stock line changed since the scan was read.")
        self.current = current


def create_scan(
    db: Session,
    *,
    current_user: User,
    filename: str,
    content_type: str | None,
    stream: BinaryIO,
    idempotency_key: str,
    analyze: AnalyzeImage | None | object = _DEFAULT,
) -> tuple[PantryScanRead, bool]:
    existing = db.scalar(
        select(PulsePantryScan).where(PulsePantryScan.user_id == current_user.id, PulsePantryScan.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return _read(db, existing), True
    if extension(safe_filename(filename)) not in ACCEPTED_EXTENSIONS:
        raise PantryScanFileError("Fichier refusé : photo (JPEG, PNG, WebP, HEIC) seulement.")
    data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise PantryScanFileError("Fichier refusé : 25 Mo maximum.")
    if not data:
        raise PantryScanFileError("Fichier refusé : vide.")
    scan = PulsePantryScan(
        id=uuid4(), user_id=current_user.id, status="failed", mime_type=(content_type or "application/octet-stream")[:120],
        size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), idempotency_key=idempotency_key, warnings=[],
    )
    analyzer = _default_analyzer() if analyze is _DEFAULT else analyze
    failure, payload = _call(analyzer, data, content_type)
    parsed = None if failure else parse_result(payload)
    if failure is None and parsed is None:
        failure = "unreadable"
    if failure:
        scan.error_message = MESSAGES[failure]
    else:
        items, quality, confidence, summary, warnings = parsed
        scan.status = "ready"
        scan.image_quality, scan.confidence, scan.summary = quality, confidence, summary
        scan.proposal = {"lines": _propose(db, current_user, items)}
        if quality == "poor":
            warnings.insert(0, "Photo trop floue. Reprendre une photo ?")
        if not items or (confidence is not None and confidence < EMPTY_CONFIDENCE):
            warnings.insert(0, "Aucun aliment détecté. Reprends la photo ou ajoute les produits à la main.")
        scan.warnings = warnings[:20]
    del data  # la photo n'est jamais conservée
    db.add(scan)
    db.flush()
    _emit(db, current_user, "pulse.pantry_scan.analyzed" if not failure else "pulse.pantry_scan.failed", scan,
          {"lines": len(scan.proposal["lines"])} if not failure else {"reason": failure})
    db.commit()
    return _read(db, scan), False


def get_scan(db: Session, *, current_user: User, scan_id: UUID) -> PantryScanRead:
    return _read(db, _get(db, current_user, scan_id))


def validate_scan(
    db: Session, *, current_user: User, scan_id: UUID, payload: PantryScanValidateRequest
) -> PantryScanRead:
    scan = _get(db, current_user, scan_id, lock=True)
    if scan.status == "validated":
        return _read(db, scan)
    if scan.status != "ready":
        raise PantryScanStateError("Only a ready scan can be validated.")
    added: list[FoodStockItem] = []
    updated: list[FoodStockItem] = []
    for index, line in enumerate(payload.lines):
        if line.action == "add":
            item = FoodStockItem(
                user_id=current_user.id, name=line.name, quantity=line.quantity, unit=line.unit,
                expiry_type=line.expiry_type, expiry_date=line.expiry_date, category=line.category,
                confidence=_line_confidence(scan, line.name), source="pantry_scan", source_ref=f"scan:{scan.id}:{index}",
                status="active", version=1,
            )
            db.add(item)
            added.append(item)
            continue
        item = db.get(FoodStockItem, line.stock_item_id, with_for_update=True)
        if item is None or item.user_id != current_user.id or item.status != "active":
            db.rollback()
            raise PantryScanNotFoundError("Stock item not found.")
        if item.version != line.stock_version:
            current = FoodStockItemRead.model_validate(item)
            db.rollback()
            raise PantryScanVersionConflictError(current)
        item.quantity, item.unit = line.quantity, line.unit
        if line.expiry_date is not None:
            item.expiry_type, item.expiry_date = line.expiry_type, line.expiry_date
        item.version += 1
        updated.append(item)
    db.flush()
    for item in added + updated:
        db.refresh(item)
    reads = [FoodStockItemRead.model_validate(item) for item in added + updated]
    scan.status = "validated"
    scan.validated_at = datetime.now(UTC)
    scan.result = {"stock_items": [read.model_dump(mode="json") for read in reads]}
    if added or updated:
        db.add(
            build_event(
                db, user_id=current_user.id, event_type="pulse.food_stock.updated",
                payload={"source": "pantry_scan", "scan_id": str(scan.id), "items_added": len(added),
                         "items_updated": len(updated), "stock_item_ids": [str(read.id) for read in reads]},
                idempotency_key=f"pulse.food_stock.updated.scan:{scan.id}", source_app=SourceApp.pulse,
                privacy_level=PrivacyLevel.medium,
            )
        )
    _emit(db, current_user, "pulse.pantry_scan.validated", scan, {"items_added": len(added), "items_updated": len(updated)})
    db.commit()
    return _read(db, scan)


def cancel_scan(db: Session, *, current_user: User, scan_id: UUID) -> PantryScanRead:
    scan = _get(db, current_user, scan_id)
    if scan.status == "validated":
        raise PantryScanStateError("A validated scan is corrected from the stock list.")
    if scan.status != "cancelled":
        scan.status = "cancelled"
        _emit(db, current_user, "pulse.pantry_scan.cancelled", scan, {})
        db.commit()
    return _read(db, scan)


# ---------- lecture de la réponse du modèle (doc 37 §5.2) ----------

def parse_result(payload: dict | None):
    """(items, qualité, confiance, résumé, avertissements) ou None si la forme n'est pas celle du prompt."""
    if not isinstance(payload, dict):
        return None
    structured = payload.get("structured_result")
    if not isinstance(structured, dict) or not isinstance(structured.get("items"), list):
        return None
    items = []
    for raw in structured["items"][:MAX_ITEMS]:
        if not isinstance(raw, dict) or not isinstance(raw.get("name_fr"), str) or not raw["name_fr"].strip():
            continue
        quantity = raw.get("estimated_quantity")
        quantity = float(quantity) if isinstance(quantity, int | float) and not isinstance(quantity, bool) and quantity > 0 else None
        category = raw.get("category") if raw.get("category") in CATEGORIES else "other"
        items.append({
            "name": raw["name_fr"].strip()[:120],
            "category": category,
            "quantity": quantity,
            "unit": raw.get("unit") if raw.get("unit") in UNITS else "piece",
            "expiry_date": _date(raw.get("expiry_visible")),
            "confidence": _unit_interval(raw.get("confidence")),
        })
    quality = structured.get("image_quality") if structured.get("image_quality") in ("good", "acceptable", "poor") else None
    summary = payload.get("summary")[:500] if isinstance(payload.get("summary"), str) else None
    warnings = [str(w)[:200] for w in payload.get("warnings") or [] if isinstance(w, str)] if isinstance(payload.get("warnings"), list) else []
    return items, quality, _unit_interval(payload.get("confidence_score")), summary, warnings


def normalize_name(name: str) -> frozenset[str]:
    ligatures = name.replace("œ", "oe").replace("Œ", "Oe").replace("æ", "ae").replace("Æ", "Ae")  # NFKD ne les décompose pas
    folded = unicodedata.normalize("NFKD", ligatures).encode("ascii", "ignore").decode("ascii").lower()
    tokens = re.findall(r"[a-z]+", folded)
    stop = {"de", "du", "des", "la", "le", "les", "a", "au", "aux", "en", "et", "d", "l"}
    return frozenset(token[:-1] if len(token) > 3 and token.endswith(("s", "x")) else token for token in tokens if token not in stop)


def match_stock(name: str, stock: list[FoodStockItem]) -> FoodStockItem | None:
    """Même nom normalisé d'abord, puis noms dont l'un contient l'autre ; la ligne la plus récente gagne."""
    wanted = normalize_name(name)
    if not wanted:
        return None
    exact = [item for item in stock if normalize_name(item.name) == wanted]
    close = [item for item in stock if (other := normalize_name(item.name)) and (wanted <= other or other <= wanted)]
    candidates = exact or close
    return max(candidates, key=lambda item: item.created_at) if candidates else None


# ---------- internes ----------

def _propose(db: Session, current_user: User, items: list[dict]) -> list[dict]:
    stock = list(db.scalars(select(FoodStockItem).where(FoodStockItem.user_id == current_user.id, FoodStockItem.status == "active")))
    lines = []
    for index, item in enumerate(items):
        match = match_stock(item["name"], stock)
        line = {
            "index": index,
            "name": item["name"],
            "category": item["category"],
            "quantity": item["quantity"] or 1.0,
            "quantity_estimated": item["quantity"] is not None,
            "unit": item["unit"],
            "expiry_date": item["expiry_date"].isoformat() if item["expiry_date"] else None,
            "expiry_type": ("DLC" if item["category"] in DLC_CATEGORIES else "DDM") if item["expiry_date"] else "unknown",
            "confidence": item["confidence"],
            "low_confidence": item["confidence"] is not None and item["confidence"] < LOW_CONFIDENCE,
            "action": "update" if match else "add",
        }
        if match:
            line.update(stock_item_id=str(match.id), stock_name=match.name, stock_quantity=float(match.quantity),
                        stock_unit=match.unit, stock_version=match.version)
        lines.append(line)
    return lines


def _line_confidence(scan: PulsePantryScan, name: str) -> Decimal | None:
    for line in (scan.proposal or {}).get("lines", []):
        if line["name"] == name and line.get("confidence") is not None:
            return Decimal(str(round(line["confidence"], 3)))
    return None


def _call(analyzer: AnalyzeImage | None, data: bytes, content_type: str | None):
    if analyzer is None:
        return "disabled", None
    try:
        return None, analyzer(data, content_type)
    except ocr.OcrServiceUnreachable:
        return "unreachable", None
    except ocr.OcrError:
        return "unreadable", None


def _date(value) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _unit_interval(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return round(min(max(float(value), 0.0), 1.0), 3)


def _get(db: Session, current_user: User, scan_id: UUID, *, lock: bool = False) -> PulsePantryScan:
    scan = db.get(PulsePantryScan, scan_id, with_for_update=lock)
    if scan is None or scan.user_id != current_user.id:
        raise PantryScanNotFoundError("Scan not found.")
    return scan


def _read(db: Session, scan: PulsePantryScan) -> PantryScanRead:
    return PantryScanRead(
        id=scan.id, status=scan.status, image_quality=scan.image_quality,
        confidence=float(scan.confidence) if scan.confidence is not None else None, summary=scan.summary,
        lines=[PantryScanLineRead(**line) for line in (scan.proposal or {}).get("lines", [])],
        warnings=list(scan.warnings or []), error_message=scan.error_message, created_at=scan.created_at,
        validated_at=scan.validated_at,
        stock_items=[FoodStockItemRead.model_validate(item) for item in (scan.result or {}).get("stock_items", [])],
    )


def _emit(db: Session, current_user: User, event_type: str, scan: PulsePantryScan, extra: dict) -> None:
    db.add(
        build_event(
            db, user_id=current_user.id, event_type=event_type, payload={"scan_id": str(scan.id), **extra},
            idempotency_key=f"{event_type}.{scan.id}", source_app=SourceApp.pulse, privacy_level=PrivacyLevel.medium,
        )
    )


def _default_analyzer() -> AnalyzeImage | None:
    if not ocr.ocr_available():
        return None
    prompt = ocr.load_prompt(PROMPT)
    return lambda data, content_type: ocr.analyze_image(data, task=TASK, prompt=prompt, content_type=content_type)
