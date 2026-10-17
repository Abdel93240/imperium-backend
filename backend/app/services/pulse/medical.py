"""Médical Pulse (doc 34) sous consentement « medical » (doc 08 PULSE-004).

Documents : envoi sous double consentement (domaine actif + accord de cet envoi à la
version courante du texte, §5), fichier hors base sous un nom interne (droits 0600),
conservé 90 jours par défaut (§11) puis purgé par le job `pulse.medical_retention`.
L'extraction automatique (spécialiste santé, §6–§8) n'est pas encore active.

Règles : saisies à la main en V1, toujours « proposed » d'abord ; activation avec les
trois confirmations du §10.1, et un accusé de lecture pour une règle critique (§15.1).
Une règle peut en remplacer une autre (superseded, §15.2) ; une règle échue passe
« expired » (§15.3). Retirer une règle ou supprimer un document reste toujours
possible, même sans consentement. Supprimer un document supprime ses règles (§16.3) ;
la purge de rétention, elle, garde les règles validées (le lien est retiré).

Événements : identifiants, type et sévérité de règle seulement — jamais le contenu.
Pulse ne pose pas de diagnostic.
"""

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.imperium import PulseMedicalDocument, PulseMedicalRule
from app.schemas.pulse_health import (
    MedicalDocumentListResponse,
    MedicalDocumentRead,
    MedicalRuleActivateRequest,
    MedicalRuleCreate,
    MedicalRuleListResponse,
    MedicalRuleRead,
)
from app.services.ai.knowledge_files import extension, safe_filename
from app.services.events.emitter import build_event
from app.services.pulse import food_stock, health_consent
from app.services.pulse.expiry import paris_today

ACCEPTED_EXTENSIONS = frozenset({"pdf", "jpg", "jpeg", "png", "webp", "heic"})
MAX_BYTES = 25 * 1024 * 1024
RETENTION_DAYS = 90
CONSENT_SCOPE = "extract_constraints_for_pulse_and_imperium"
NO_EXTRACTION = "Analyse automatique pas encore active : ajoute les règles à la main."
CRITICAL_ACK = "Règle critique : consulte ton médecin rapidement, puis confirme l'avoir lue pour l'activer."


class MedicalNotFoundError(ValueError):
    pass


class MedicalFileError(ValueError):
    pass


class MedicalStateError(ValueError):
    pass


class MedicalIdempotencyConflictError(ValueError):
    pass


class UploadConsentMissingError(PermissionError):
    pass


def storage_root() -> Path:
    root = Path(get_settings().medical_documents_storage_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[3] / root
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


# ---------- documents ----------

def upload_document(
    db: Session,
    *,
    current_user: User,
    filename: str,
    content_type: str | None,
    stream: BinaryIO,
    idempotency_key: str,
    doc_type: str,
    doc_date,
    upload_consent: bool,
    consent_version: str | None,
) -> tuple[MedicalDocumentRead, bool]:
    data = stream.read(MAX_BYTES + 1)
    sha256 = hashlib.sha256(data).hexdigest()
    fingerprint = food_stock.request_hash(
        "pulse.medical_document.upload",
        {"sha256": sha256, "doc_type": doc_type, "doc_date": doc_date.isoformat() if doc_date else None},
    )
    existing = db.scalar(
        select(PulseMedicalDocument).where(
            PulseMedicalDocument.user_id == current_user.id, PulseMedicalDocument.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise MedicalIdempotencyConflictError("Idempotency key already used with a different document.")
        return _doc_read(existing), True
    health_consent.require(db, current_user, "medical")
    if not upload_consent:
        raise UploadConsentMissingError("Each medical upload needs explicit consent (consent=true).")
    if consent_version != health_consent.TEXT_VERSION:
        raise health_consent.ConsentVersionError("The consent text changed: show the current text and ask again.")
    name = safe_filename(filename)
    ext = extension(name)
    if ext not in ACCEPTED_EXTENSIONS:
        raise MedicalFileError("Fichier refusé : PDF ou photo (JPEG, PNG, WebP, HEIC) seulement.")
    if len(data) > MAX_BYTES:
        raise MedicalFileError("Fichier refusé : 25 Mo maximum.")
    if not data:
        raise MedicalFileError("Fichier refusé : vide.")
    document_id = uuid4()
    storage_name = f"{current_user.id}/{document_id}.{ext}"
    path = storage_root() / storage_name
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(data)
    path.chmod(0o600)
    now = datetime.now(UTC)
    document = PulseMedicalDocument(
        id=document_id, user_id=current_user.id, doc_type=doc_type, doc_date=doc_date, original_name=name,
        mime_type=(content_type or "application/octet-stream")[:120], size_bytes=len(data), sha256=sha256,
        storage_name=storage_name, status="uploaded", consent_version=consent_version, consent_scope=CONSENT_SCOPE,
        consented_at=now, retention_delete_after=now + timedelta(days=RETENTION_DAYS), idempotency_key=idempotency_key,
        request_hash=fingerprint,
    )
    db.add(document)
    try:
        db.flush()
        _emit(db, current_user, "pulse.medical_document.uploaded", {"document_id": str(document.id)}, str(document.id))
        db.refresh(document)
        read = _doc_read(document)
        db.commit()
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return read, False


def list_documents(db: Session, *, current_user: User) -> MedicalDocumentListResponse:
    rows = db.scalars(
        select(PulseMedicalDocument)
        .where(PulseMedicalDocument.user_id == current_user.id)
        .order_by(PulseMedicalDocument.created_at.desc())
    )
    return MedicalDocumentListResponse(items=[_doc_read(row) for row in rows])


def document_file(db: Session, *, current_user: User, document_id: UUID) -> tuple[Path, str, str]:
    document = _get_document(db, current_user, document_id)
    path = storage_root() / document.storage_name
    if not path.is_file():
        raise MedicalNotFoundError("Document file not found.")
    return path, document.mime_type, document.original_name


def delete_document(db: Session, *, current_user: User, document_id: UUID) -> None:
    """Suppression réelle : fichier, document et règles qui en sont tirées (doc 34 §16.3)."""
    document = _get_document(db, current_user, document_id)
    rules = list(db.scalars(select(PulseMedicalRule).where(PulseMedicalRule.source_document_id == document.id)))
    for rule in rules:
        if rule.status == "active":
            _emit_rule(db, current_user, "pulse.medical_rule.deactivated", rule)
        db.delete(rule)
    _remove_file(document)
    db.delete(document)
    _emit(db, current_user, "pulse.medical_document.deleted",
          {"document_id": str(document_id), "rules_deleted": len(rules)}, str(document_id))
    db.commit()


# ---------- règles ----------

def create_rule(
    db: Session, *, current_user: User, payload: MedicalRuleCreate, idempotency_key: str
) -> tuple[MedicalRuleRead, bool]:
    fingerprint = food_stock.request_hash("pulse.medical_rule.create", payload.model_dump(mode="json"))
    existing = db.scalar(
        select(PulseMedicalRule).where(PulseMedicalRule.user_id == current_user.id, PulseMedicalRule.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise MedicalIdempotencyConflictError("Idempotency key already used with a different rule.")
        return MedicalRuleRead.model_validate(existing), True
    health_consent.require(db, current_user, "medical")
    if payload.source_document_id is not None:
        _get_document(db, current_user, payload.source_document_id)
    rule = PulseMedicalRule(
        user_id=current_user.id, source_document_id=payload.source_document_id, rule_type=payload.rule_type,
        rule_text=payload.rule_text.strip(), source_quote=(payload.source_quote or "").strip() or None,
        severity=payload.severity, status="proposed", expires_at=payload.expires_at,
        idempotency_key=idempotency_key, request_hash=fingerprint,
    )
    db.add(rule)
    db.flush()
    db.refresh(rule)
    read = MedicalRuleRead.model_validate(rule)
    db.commit()
    return read, False


def activate_rule(
    db: Session, *, current_user: User, rule_id: UUID, payload: MedicalRuleActivateRequest, idempotency_key: str
) -> MedicalRuleRead:
    fingerprint = food_stock.request_hash("pulse.medical_rule.activate", {"rule_id": str(rule_id), **payload.model_dump(mode="json")})
    rule = _get_rule(db, current_user, rule_id, lock=True)
    if rule.status == "active" and rule.activation_idempotency_key == idempotency_key:
        if rule.activation_request_hash != fingerprint:
            raise MedicalIdempotencyConflictError("Idempotency key already used with a different activation.")
        return MedicalRuleRead.model_validate(rule)
    if rule.status != "proposed":
        raise MedicalStateError(f"Rule is {rule.status}: only a proposed rule can be activated.")
    health_consent.require(db, current_user, "medical")
    now = datetime.now(UTC)
    if rule.severity == "critical":
        if not payload.acknowledge_critical:
            raise MedicalStateError(CRITICAL_ACK)
        rule.critical_acknowledged_at = now
    if rule.expires_at is not None and rule.expires_at < paris_today():
        raise MedicalStateError("Rule already expired: change its date or create a new one.")
    if payload.supersedes_rule_id is not None:
        old = _get_rule(db, current_user, payload.supersedes_rule_id, lock=True)
        if old.status != "active" or old.id == rule.id:
            raise MedicalStateError("Only another active rule can be superseded.")
        old.status, old.superseded_by, old.deactivated_at = "superseded", rule.id, now
        _emit_rule(db, current_user, "pulse.medical_rule.deactivated", old)
    rule.status, rule.validated_at = "active", now
    rule.activation_idempotency_key, rule.activation_request_hash = idempotency_key, fingerprint
    _emit_rule(db, current_user, "pulse.medical_rule.activated", rule)
    db.flush()
    db.refresh(rule)
    read = MedicalRuleRead.model_validate(rule)
    db.commit()
    return read


def deactivate_rule(db: Session, *, current_user: User, rule_id: UUID) -> MedicalRuleRead:
    """Toujours possible, même sans consentement (réduire l'usage d'une donnée)."""
    rule = _get_rule(db, current_user, rule_id, lock=True)
    if rule.status in ("proposed", "active"):
        if rule.status == "active":
            _emit_rule(db, current_user, "pulse.medical_rule.deactivated", rule)
        rule.status, rule.deactivated_at = "inactive", datetime.now(UTC)
        db.flush()
        db.refresh(rule)
    read = MedicalRuleRead.model_validate(rule)
    db.commit()
    return read


def delete_rule(db: Session, *, current_user: User, rule_id: UUID) -> None:
    rule = _get_rule(db, current_user, rule_id)
    if rule.status == "active":
        _emit_rule(db, current_user, "pulse.medical_rule.deactivated", rule)
    db.delete(rule)
    db.commit()


def list_rules(db: Session, *, current_user: User, active_only: bool = False) -> MedicalRuleListResponse:
    query = select(PulseMedicalRule).where(PulseMedicalRule.user_id == current_user.id)
    if active_only:
        today = paris_today()
        query = query.where(
            PulseMedicalRule.status == "active",
            (PulseMedicalRule.expires_at.is_(None)) | (PulseMedicalRule.expires_at >= today),
        )
    rows = db.scalars(query.order_by(PulseMedicalRule.created_at.desc()))
    return MedicalRuleListResponse(items=[MedicalRuleRead.model_validate(row) for row in rows])


def active_count(db: Session, *, current_user: User) -> int:
    return len(list_rules(db, current_user=current_user, active_only=True).items)


# ---------- job de rétention (doc 34 §11, §15.3) ----------

def medical_retention_job(ctx, window) -> None:
    """Tous les jours : purge les documents arrivés au terme, passe les règles échues en expired."""
    now = window.to_ts or datetime.now(UTC)
    today = paris_today(now)
    expired = list(ctx.db.scalars(
        select(PulseMedicalRule).where(PulseMedicalRule.status == "active", PulseMedicalRule.expires_at < today)
    ))
    for rule in expired:
        rule.status, rule.deactivated_at = "expired", now
        _emit_rule(ctx.db, SimpleUser(rule.user_id), "pulse.medical_rule.expired", rule)
    documents = list(ctx.db.scalars(select(PulseMedicalDocument).where(PulseMedicalDocument.retention_delete_after <= now)))
    for document in documents:
        for rule in ctx.db.scalars(select(PulseMedicalRule).where(PulseMedicalRule.source_document_id == document.id)):
            rule.source_document_id = None  # la règle validée reste, le document part
        _remove_file(document)
        ctx.db.delete(document)
        _emit(ctx.db, SimpleUser(document.user_id), "pulse.medical_document.deleted",
              {"document_id": str(document.id), "reason": "retention"}, str(document.id))
    ctx.items_in = len(expired) + len(documents)
    ctx.items_out = ctx.items_in
    ctx.detail = {"rules_expired": len(expired), "documents_purged": len(documents)}


class SimpleUser:
    """Propriétaire d'une ligne, pour émettre ses événements depuis le job."""

    def __init__(self, user_id: UUID) -> None:
        self.id = user_id


# ---------- internes ----------

def _remove_file(document: PulseMedicalDocument) -> None:
    (storage_root() / document.storage_name).unlink(missing_ok=True)


def _get_document(db: Session, current_user: User, document_id: UUID) -> PulseMedicalDocument:
    document = db.get(PulseMedicalDocument, document_id)
    if document is None or document.user_id != current_user.id:
        raise MedicalNotFoundError("Medical document not found.")
    return document


def _get_rule(db: Session, current_user: User, rule_id: UUID, *, lock: bool = False) -> PulseMedicalRule:
    rule = db.get(PulseMedicalRule, rule_id, with_for_update=lock)
    if rule is None or rule.user_id != current_user.id:
        raise MedicalNotFoundError("Medical rule not found.")
    return rule


def _doc_read(document: PulseMedicalDocument) -> MedicalDocumentRead:
    read = MedicalDocumentRead.model_validate(document)
    return read.model_copy(update={"message": NO_EXTRACTION}) if document.status == "uploaded" else read


def _emit_rule(db: Session, current_user, event_type: str, rule: PulseMedicalRule) -> None:
    _emit(db, current_user, event_type,
          {"rule_id": str(rule.id), "rule_type": rule.rule_type, "severity": rule.severity}, f"{rule.id}.{uuid4()}")


def _emit(db: Session, current_user, event_type: str, payload: dict, ref: str) -> None:
    db.add(
        build_event(
            db, user_id=current_user.id, event_type=event_type, payload=payload, idempotency_key=f"{event_type}.{ref}",
            source_app=SourceApp.pulse, privacy_level=PrivacyLevel.very_high,
        )
    )
