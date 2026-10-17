"""Nourrir l'IA — Knowledge Inbox (doc 70 ; décisions utilisateur 2026-10-15/16).

Règles non négociables (doc 70 §4) :
- la source est TOUJOURS conservée (pointeur abstrait, VPS en V1), indépendamment de
  la vectorisation ;
- rien n'entre en mémoire sans validation explicite ; c'est la version corrigée
  (extraction_final) qui est vectorisée, jamais le brouillon ;
- aucune entité canonique (projet) sans validation explicite de l'utilisateur ;
- annuler avant validation supprime tout de suite le dépôt brut ;
- supprimer plus tard efface la source et neutralise les mémoires directes
  (source_table/source_id) ; les influences indirectes ne sont pas réécrites.
"""

import hashlib
import shutil
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai import AIMemory, KnowledgeInboxDocument, KnowledgeInboxItem
from app.models.auth import User
from app.models.enums import PrivacyLevel
from app.schemas.knowledge_inbox import (
    ExtractionUpdate,
    InboxItemCreate,
    InboxItemListResponse,
    InboxItemRead,
    InboxSourceRead,
    InboxValidateRequest,
    ZipExpansionRead,
)
from app.services.ai.knowledge_files import (
    KnowledgeFileError,
    classify,
    expand_zip,
    extension,
    max_bytes,
    safe_filename,
    ui_state,
)
from app.services.events.emitter import build_event

CHUNK = 1024 * 1024
SOURCE_TABLE = "knowledge_inbox_items"
OPEN_FOR_UPLOAD = ("uploading", "to_analyze", "failed")


class InboxNotFoundError(ValueError):
    pass


class InboxStateError(ValueError):
    pass


def storage_root() -> Path:
    root = Path(get_settings().knowledge_inbox_storage_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[3] / root
    root.mkdir(parents=True, exist_ok=True)
    return root


# ---------- Création et sources ----------

def create_item(db: Session, *, current_user: User, payload: InboxItemCreate, idempotency_key: str) -> InboxItemRead:
    existing = db.scalar(
        select(KnowledgeInboxItem).where(
            KnowledgeInboxItem.user_id == current_user.id, KnowledgeInboxItem.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        return _read(db, existing)
    item = KnowledgeInboxItem(
        id=uuid4(),
        user_id=current_user.id,
        entry_app=payload.entry_app,
        title=payload.title or _title_from(payload.context_text),
        context_text=payload.context_text,
        status="uploading",
        idempotency_key=idempotency_key,
    )
    db.add(item)
    db.commit()
    return _read(db, item)


def add_source(
    db: Session, *, current_user: User, item_id: UUID, filename: str, content_type: str | None, stream: BinaryIO
) -> InboxSourceRead | ZipExpansionRead:
    """Ajoute un fichier ; une archive zip est dépliée en éléments séparés (doc 70 §6)."""
    item = _get(db, current_user=current_user, item_id=item_id)
    if item.status not in OPEN_FOR_UPLOAD:
        raise InboxStateError("Sources can only be added before validation.")
    name = safe_filename(filename)
    kind = classify(name)
    if kind is None:
        raise KnowledgeFileError("type non accepté")
    if kind == "archive":
        data = _read_limited(stream, max_bytes("archive"))
        accepted, rejected = expand_zip(data)
        created = []
        for inner_name, content in accepted:
            child = KnowledgeInboxItem(
                id=uuid4(), user_id=current_user.id, entry_app=item.entry_app, title=inner_name,
                context_text=item.context_text, status="uploading",
            )
            db.add(child)
            db.flush()
            _store(db, current_user, child, inner_name, "application/octet-stream", _iter_bytes(content))
            _mark_to_analyze(db, current_user, child)
            created.append(child)
        db.commit()
        return ZipExpansionRead(
            created_items=[_read(db, child) for child in created],
            rejected=[{"name": rejected_name, "reason": reason} for rejected_name, reason in rejected],
        )
    document = _store(db, current_user, item, name, content_type or "application/octet-stream", _iter_stream(stream))
    db.commit()
    return InboxSourceRead.model_validate(document)


def request_analysis(db: Session, *, current_user: User, item_id: UUID) -> InboxItemRead:
    item = _get(db, current_user=current_user, item_id=item_id)
    if item.status not in ("uploading", "failed"):
        raise InboxStateError("Analysis was already requested.")
    if not item.context_text and not _documents(db, item):
        raise InboxStateError("Add a file or a context text before analysis.")
    _mark_to_analyze(db, current_user, item)
    db.commit()
    return _read(db, item)


def retry_item(db: Session, *, current_user: User, item_id: UUID) -> InboxItemRead:
    item = _get(db, current_user=current_user, item_id=item_id)
    if item.status != "failed":
        raise InboxStateError("Only a failed item can be retried.")
    item.error_message = None
    _mark_to_analyze(db, current_user, item)
    db.commit()
    return _read(db, item)


# ---------- Lecture ----------

def list_items(db: Session, *, current_user: User) -> InboxItemListResponse:
    items = db.scalars(
        select(KnowledgeInboxItem)
        .where(KnowledgeInboxItem.user_id == current_user.id, KnowledgeInboxItem.status != "deleted")
        .order_by(KnowledgeInboxItem.created_at.desc())
    )
    return InboxItemListResponse(items=[_read(db, item) for item in items])


def get_item(db: Session, *, current_user: User, item_id: UUID) -> InboxItemRead:
    return _read(db, _get(db, current_user=current_user, item_id=item_id))


def source_path(db: Session, *, current_user: User, item_id: UUID, document_id: UUID) -> tuple[Path, KnowledgeInboxDocument]:
    item = _get(db, current_user=current_user, item_id=item_id)
    document = db.get(KnowledgeInboxDocument, document_id)
    if document is None or document.item_id != item.id or document.storage_pointer is None:
        raise InboxNotFoundError("Source not found.")
    return storage_root() / document.storage_pointer, document


# ---------- Correction, validation, annulation, suppression ----------

def update_extraction(db: Session, *, current_user: User, item_id: UUID, payload: ExtractionUpdate) -> InboxItemRead:
    item = _get(db, current_user=current_user, item_id=item_id)
    if item.status != "to_validate":
        raise InboxStateError("Only an analyzed item can be corrected.")
    draft = dict(item.extraction_draft or {})
    for field in payload.model_fields_set:
        draft[field] = getattr(payload, field)
    draft["edited_by_user"] = True
    item.extraction_draft = draft
    db.commit()
    return _read(db, item)


def validate_item(db: Session, *, current_user: User, item_id: UUID, payload: InboxValidateRequest) -> InboxItemRead:
    """Validation explicite : seule étape qui ouvre la mémoire (ou crée un projet)."""
    item = _get(db, current_user=current_user, item_id=item_id)
    if item.status != "to_validate":
        raise InboxStateError("Only an analyzed item can be validated.")
    item.extraction_final = dict(item.extraction_draft or {})
    item.destination = payload.destination
    if payload.destination == "project":
        from app.schemas.operations import ProjectCreate
        from app.services.imperium.operations import create_project

        project = create_project(
            db,
            current_user=current_user,
            payload=ProjectCreate(title=payload.project_title, description=item.extraction_final.get("summary"), source="chatbot"),
            idempotency_key=f"inbox-project:{item.id}",
        )
        item = _get(db, current_user=current_user, item_id=item_id)
        item.created_entity_type = "project"
        item.created_entity_id = project.id
    item.status = "validated"
    item.validated_at = datetime.now(UTC)
    _emit(db, current_user.id, "inbox.document.validated", item, {"destination": payload.destination})
    db.commit()
    return _read(db, item)


def cancel_item(db: Session, *, current_user: User, item_id: UUID) -> None:
    """Annulation avant validation : dépôt brut supprimé immédiatement, rien de conservé (doc 70 §7)."""
    item = _get(db, current_user=current_user, item_id=item_id)
    if item.status in ("validated", "vectorized"):
        raise InboxStateError("A validated item is removed with delete, not cancel.")
    _emit(db, current_user.id, "inbox.document.rejected", item, {"reason": "user_cancelled"})
    for document in _documents(db, item):
        _remove_file(document)
        db.delete(document)
    db.delete(item)
    db.commit()


def delete_item(db: Session, *, current_user: User, item_id: UUID) -> int:
    """Suppression délibérée (niveau 3, doc 72 §4) : sources + mémoires directes ensemble."""
    item = _get(db, current_user=current_user, item_id=item_id)
    now = datetime.now(UTC)
    for document in _documents(db, item):
        _remove_file(document)
        document.storage_pointer = None
        document.deleted_at = now
    neutralized = 0
    for memory in db.scalars(
        select(AIMemory).where(
            AIMemory.user_id == current_user.id, AIMemory.source_table == SOURCE_TABLE, AIMemory.source_id == str(item.id)
        )
    ):
        memory.is_active = False
        memory.correction_reason = "Supprimé par l'utilisateur (Nourrir l'IA)."
        neutralized += 1
    item.status = "deleted"
    item.deleted_at = now
    _emit(db, current_user.id, "inbox.document.deleted", item, {"memories_neutralized": neutralized})
    db.commit()
    return neutralized


# ---------- internes ----------

def _get(db: Session, *, current_user: User, item_id: UUID) -> KnowledgeInboxItem:
    item = db.get(KnowledgeInboxItem, item_id)
    if item is None or item.user_id != current_user.id or item.status == "deleted":
        raise InboxNotFoundError("Item not found.")
    return item


def _documents(db: Session, item: KnowledgeInboxItem) -> list[KnowledgeInboxDocument]:
    return list(
        db.scalars(
            select(KnowledgeInboxDocument)
            .where(KnowledgeInboxDocument.item_id == item.id, KnowledgeInboxDocument.deleted_at.is_(None))
            .order_by(KnowledgeInboxDocument.created_at.asc())
        )
    )


def _read(db: Session, item: KnowledgeInboxItem) -> InboxItemRead:
    read = InboxItemRead.model_validate(item)
    read.ui_state = ui_state(item.status)
    read.sources = [InboxSourceRead.model_validate(document) for document in _documents(db, item)]
    return read


def _mark_to_analyze(db: Session, current_user: User, item: KnowledgeInboxItem) -> None:
    item.status = "to_analyze"
    _emit(db, current_user.id, "inbox.document.uploaded", item, {"sources": len(_documents(db, item))})


def _store(db, current_user, item, name: str, content_type: str, chunks: Iterable[bytes]) -> KnowledgeInboxDocument:
    kind = classify(name)
    if kind is None or kind == "archive":
        raise KnowledgeFileError("type non accepté")
    limit = max_bytes(kind)
    document_id = uuid4()
    pointer = f"{current_user.id}/{item.id}/{document_id}.{extension(name)}"
    target = storage_root() / pointer
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    try:
        with target.open("wb") as handle:
            for chunk in chunks:
                size += len(chunk)
                if size > limit:
                    raise KnowledgeFileError(f"fichier trop volumineux (max {limit // (1024 * 1024)} Mo)")
                digest.update(chunk)
                handle.write(chunk)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    document = KnowledgeInboxDocument(
        id=document_id,
        user_id=current_user.id,
        item_id=item.id,
        original_filename=name,
        kind=kind,
        mime_type=content_type[:120],
        size_bytes=size,
        sha256=digest.hexdigest(),
        storage_pointer=pointer,
        storage_location="vps_local",
        source_retained_at=datetime.now(UTC),
    )
    db.add(document)
    db.flush()
    return document


def _remove_file(document: KnowledgeInboxDocument) -> None:
    if document.storage_pointer:
        path = storage_root() / document.storage_pointer
        path.unlink(missing_ok=True)
        parent = path.parent
        if parent.exists() and not any(parent.iterdir()):
            shutil.rmtree(parent, ignore_errors=True)


def _iter_stream(stream: BinaryIO) -> Iterable[bytes]:
    while chunk := stream.read(CHUNK):
        yield chunk


def _iter_bytes(data: bytes) -> Iterable[bytes]:
    for start in range(0, len(data), CHUNK):
        yield data[start : start + CHUNK]


def _read_limited(stream: BinaryIO, limit: int) -> bytes:
    data = bytearray()
    for chunk in _iter_stream(stream):
        data.extend(chunk)
        if len(data) > limit:
            raise KnowledgeFileError("archive trop volumineuse")
    return bytes(data)


def _title_from(context: str | None) -> str:
    if context:
        first = context.strip().splitlines()[0]
        return first[:60] + ("…" if len(first) > 60 else "")
    return "Élément du " + datetime.now(UTC).strftime("%d/%m/%Y")


def _emit(db: Session, user_id: UUID, event_type: str, item: KnowledgeInboxItem, extra: dict) -> None:
    db.add(
        build_event(
            db,
            user_id=user_id,
            event_type=event_type,
            payload={"item_id": str(item.id), "entry_app": item.entry_app, **extra},
            idempotency_key=f"{event_type}:{item.id}:{uuid4().hex}",
            privacy_level=PrivacyLevel.high,
        )
    )
