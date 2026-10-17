"""Justificatifs du Vault : photo du ticket → OCR → brouillon → validation (doc 37 §3).

Module séparé du registre (routes imperium_vault sans IA, invariants 9B–9D) : il
appelle le service OCR et la catégorie suggérée, puis écrit la dépense par le
service canonique du registre, et seulement quand l'utilisateur a validé.

Mécanique d'écran (doc 59 VAU-04/05, maquette 05) : l'appel est synchrone, l'écran
de chargement standard couvre la lecture ; un échec renvoie un message lisible que
l'écran affiche 10 s. Image : effacée si la lecture échoue ou si l'utilisateur annule,
conservée comme justificatif quand la dépense est validée.
"""

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.vault import ImperiumVaultTransaction, VaultReceiptExtraction
from app.schemas.vault import (
    ImperiumVaultTransactionCreate,
    ImperiumVaultTransactionRead,
    VaultReceiptExtractionRead,
    VaultReceiptValidateRequest,
    VaultReceiptValidateResponse,
)
from app.services.ai import ocr
from app.services.ai.knowledge_files import extension, safe_filename
from app.services.events.emitter import build_event
from app.services.imperium.vault_transactions import create_vault_transaction
from app.services.vault import categorization
from app.services.vault.receipt_parser import parse_receipt_text

MAX_BYTES = 25 * 1024 * 1024
ACCEPTED_EXTENSIONS = frozenset({"jpg", "jpeg", "png", "webp", "heic", "pdf"})
LOW_CONFIDENCE = Decimal("0.6")
WALLET_BY_PAYMENT = {"card": "bank", "cash": "cash"}
_DEFAULT = object()

RecognizeFile = Callable[[bytes, str, str | None], ocr.OcrResult]

MESSAGES = {
    "disabled": "La lecture des tickets n'est pas encore activée. Saisis la dépense à la main ou recopie le ticket dans le chat.",
    "unreachable": "Le service de lecture ne répond pas. Réessaie dans un moment ou saisis la dépense à la main.",
    "unreadable": "Ticket illisible. Reprends la photo bien à plat, avec plus de lumière, ou saisis la dépense à la main.",
    "empty": "Aucun texte trouvé sur l'image. Reprends la photo ou saisis la dépense à la main.",
}


class ReceiptFileError(ValueError):
    pass


class ReceiptNotFoundError(ValueError):
    pass


class ReceiptStateError(ValueError):
    pass


def storage_root() -> Path:
    root = Path(get_settings().vault_receipts_storage_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[3] / root
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def create_extraction(
    db: Session,
    *,
    current_user: User,
    filename: str,
    content_type: str | None,
    stream: BinaryIO,
    idempotency_key: str,
    entry_app: str = "vault",
    recognize_file: RecognizeFile | None | object = _DEFAULT,
    call_model: object = _DEFAULT,
) -> tuple[VaultReceiptExtractionRead, bool]:
    existing = db.scalar(
        select(VaultReceiptExtraction).where(
            VaultReceiptExtraction.user_id == current_user.id, VaultReceiptExtraction.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        return _read(existing), True
    name = safe_filename(filename)
    if extension(name) not in ACCEPTED_EXTENSIONS:
        raise ReceiptFileError("Fichier refusé : photo (JPEG, PNG, WebP, HEIC) ou PDF seulement.")
    data = _read_limited(stream)
    extraction = VaultReceiptExtraction(
        id=uuid4(),
        user_id=current_user.id,
        entry_app=entry_app,
        status="failed",
        original_filename=name,
        mime_type=(content_type or "application/octet-stream")[:120],
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        idempotency_key=idempotency_key,
    )
    recognize = _default_recognizer() if recognize_file is _DEFAULT else recognize_file
    failure, result = _recognize(recognize, data, name, content_type)
    if failure is None:
        extraction.raw_text = result.text
        extraction.ocr_confidence = _confidence(result.confidence)
        extraction.draft = _draft(db, current_user, result.text, extraction.ocr_confidence, call_model)
        extraction.status = "ready"
        extraction.storage_pointer = _store(current_user, extraction.id, name, data)
    else:
        extraction.error_message = MESSAGES[failure]
    db.add(extraction)
    db.flush()
    _emit(db, current_user, "finance.receipt.extracted" if failure is None else "finance.receipt.failed", extraction,
          {"reason": failure} if failure else {"warnings": len(extraction.draft["warnings"])})
    db.commit()
    return _read(extraction), False


def get_extraction(db: Session, *, current_user: User, extraction_id: UUID) -> VaultReceiptExtractionRead:
    return _read(_get(db, current_user=current_user, extraction_id=extraction_id))


def image_path(db: Session, *, current_user: User, extraction_id: UUID) -> tuple[Path, str]:
    extraction = _get(db, current_user=current_user, extraction_id=extraction_id)
    path = storage_root() / extraction.storage_pointer if extraction.storage_pointer else None
    if path is None or not path.is_file():
        raise ReceiptNotFoundError("Receipt image not found.")
    return path, extraction.mime_type


def validate_extraction(
    db: Session,
    *,
    current_user: User,
    extraction_id: UUID,
    payload: VaultReceiptValidateRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> VaultReceiptValidateResponse:
    extraction = _get(db, current_user=current_user, extraction_id=extraction_id)
    if extraction.status == "validated":
        transaction = ImperiumVaultTransactionRead.model_validate(db.get(ImperiumVaultTransaction, extraction.transaction_id))
        return VaultReceiptValidateResponse(extraction=_read(extraction), transaction=transaction)
    if extraction.status != "ready":
        raise ReceiptStateError("Only a ready receipt can be validated.")
    merchant = (extraction.draft or {}).get("merchant")
    category = payload.category.strip().lower() if payload.category else None
    transaction, _ = create_vault_transaction(
        db,
        current_user=current_user,
        payload=ImperiumVaultTransactionCreate(
            transaction_type="expense",
            amount_cents=payload.amount_cents,
            wallet=payload.wallet,
            occurred_at=payload.occurred_at,
            timezone=payload.timezone,
            category=category,
            source="scan_ticket",
            note=payload.note or merchant,
            external_ref=f"receipt:{extraction.id}",
        ),
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
    )
    extraction.status = "validated"
    extraction.transaction_id = transaction.id
    extraction.validated_at = datetime.now(UTC)
    _emit(db, current_user, "finance.receipt.validated", extraction, {"transaction_id": str(transaction.id)})
    db.commit()
    if merchant and category and category in categorization.get_referential(db):
        categorization.confirm_category(db, current_user=current_user, label=merchant, category=category)
    return VaultReceiptValidateResponse(extraction=_read(extraction), transaction=transaction)


def cancel_extraction(db: Session, *, current_user: User, extraction_id: UUID) -> VaultReceiptExtractionRead:
    """Annulation (ou re-scan) : l'image est effacée tout de suite, rien n'est écrit au registre."""
    extraction = _get(db, current_user=current_user, extraction_id=extraction_id)
    if extraction.status == "validated":
        raise ReceiptStateError("A validated receipt is undone by reversing its transaction.")
    if extraction.status != "cancelled":
        _remove_file(extraction)
        extraction.status = "cancelled"
        extraction.raw_text = None
        _emit(db, current_user, "finance.receipt.cancelled", extraction, {})
        db.commit()
    return _read(extraction)


# ---------- internes ----------

def _recognize(recognize: RecognizeFile | None, data: bytes, name: str, content_type: str | None):
    if recognize is None:
        return "disabled", None
    try:
        result = recognize(data, name, content_type)
    except ocr.OcrServiceUnreachable:
        return "unreachable", None
    except ocr.OcrError:
        return "unreadable", None
    if not result.text.strip():
        return "empty", None
    return None, result


def _draft(db: Session, current_user: User, raw_text: str, confidence: Decimal | None, call_model: object) -> dict:
    parsed = parse_receipt_text(raw_text)
    warnings = list(parsed.warnings)
    if confidence is not None and confidence < LOW_CONFIDENCE:
        warnings.append("Lecture peu sûre : vérifie chaque champ.")
    suggestion = None
    if parsed.merchant:
        kwargs = {} if call_model is _DEFAULT else {"call_model": call_model}
        suggestion = categorization.suggest_category(
            db, current_user=current_user, label=parsed.merchant, amount_cents=parsed.total_cents,
            transaction_type="expense", **kwargs,
        )
    return {
        "merchant": parsed.merchant,
        "purchase_date": parsed.purchase_date.isoformat() if parsed.purchase_date else None,
        "purchase_time": parsed.purchase_time.strftime("%H:%M") if parsed.purchase_time else None,
        "total_cents": parsed.total_cents,
        "payment_method": parsed.payment_method,
        "wallet": WALLET_BY_PAYMENT.get(parsed.payment_method),
        "category": suggestion.category if suggestion else None,
        "book": suggestion.book if suggestion else None,
        "category_source": suggestion.source if suggestion else None,
        "warnings": warnings,
    }


def _confidence(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(round(min(max(value, 0.0), 1.0), 3)))


def _store(current_user: User, extraction_id: UUID, name: str, data: bytes) -> str:
    pointer = f"{current_user.id}/{extraction_id}.{extension(name)}"
    path = storage_root() / pointer
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(data)
    path.chmod(0o600)
    return pointer


def _remove_file(extraction: VaultReceiptExtraction) -> None:
    if extraction.storage_pointer:
        (storage_root() / extraction.storage_pointer).unlink(missing_ok=True)
        extraction.storage_pointer = None


def _read_limited(stream: BinaryIO) -> bytes:
    data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ReceiptFileError("Fichier refusé : 25 Mo maximum.")
    if not data:
        raise ReceiptFileError("Fichier refusé : vide.")
    return data


def _get(db: Session, *, current_user: User, extraction_id: UUID) -> VaultReceiptExtraction:
    extraction = db.get(VaultReceiptExtraction, extraction_id)
    if extraction is None or extraction.user_id != current_user.id:
        raise ReceiptNotFoundError("Receipt not found.")
    return extraction


def _read(extraction: VaultReceiptExtraction) -> VaultReceiptExtractionRead:
    return VaultReceiptExtractionRead.model_validate(extraction)


def _emit(db: Session, current_user: User, event_type: str, extraction: VaultReceiptExtraction, extra: dict) -> None:
    db.add(
        build_event(
            db,
            user_id=current_user.id,
            event_type=event_type,
            payload={"extraction_id": str(extraction.id), "entry_app": extraction.entry_app, **extra},
            idempotency_key=f"{event_type}.{extraction.id}",
            source_app=SourceApp.vault if extraction.entry_app == "vault" else SourceApp.imperium,
            privacy_level=PrivacyLevel.high,
        )
    )


def _default_recognizer() -> RecognizeFile | None:
    if not ocr.ocr_available():
        return None
    return lambda data, filename, content_type: ocr.recognize(data, filename=filename, content_type=content_type)
