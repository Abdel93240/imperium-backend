"""Job runner ai.knowledge_inbox (doc 70 §7–§12).

1. Analyse des éléments « to_analyze » : lecture des sources texte (txt, md, csv) +
   texte de contexte ; modèle local si activé (sortie validée), sinon brouillon
   déterministe. Les PDF, images, audio et vidéo ne sont pas lus tant que l'OCR et la
   transcription ne sont pas branchés : le brouillon le dit (sources_unread).
2. Vectorisation des éléments VALIDÉS vers la mémoire (destination « memory ») :
   la version corrigée est découpée, embarquée par le service local, et écrite dans
   ai_memories avec source_table/source_id. GPU injoignable → l'élément reste validé
   et sera repris au réveil suivant.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai import AIMemory, KnowledgeInboxDocument, KnowledgeInboxItem
from app.services.ai.knowledge_files import TEXT_EXTENSIONS, extension
from app.services.ai import knowledge_inbox
from app.services.ai.knowledge_inbox import SOURCE_TABLE, _emit

logger = logging.getLogger(__name__)

BATCH = 50
TEXT_READ_LIMIT = 100_000
CHUNK_CHARS = 800
_DEFAULT = object()

ModelCall = Callable[[str], dict]
EmbedTexts = Callable[[list[str]], list[list[float]]]


def knowledge_inbox_job(ctx, window) -> None:  # noqa: ARG001 - signature du runner
    process_inbox(ctx)


def process_inbox(ctx, *, call_model: ModelCall | None | object = _DEFAULT, embed_texts: EmbedTexts | None | object = _DEFAULT) -> None:
    db: Session = ctx.db
    model = _default_model() if call_model is _DEFAULT else call_model
    embedder = _default_embedder() if embed_texts is _DEFAULT else embed_texts
    analyzed = failed = vectorized = 0
    for item_id in list(db.scalars(select(KnowledgeInboxItem.id).where(KnowledgeInboxItem.status == "to_analyze").limit(BATCH))):
        outcome = _analyze(db, item_id=item_id, model=model)
        analyzed += outcome == "analyzed"
        failed += outcome == "failed"
    if embedder is not None:
        for item_id in list(
            db.scalars(
                select(KnowledgeInboxItem.id)
                .where(KnowledgeInboxItem.status == "validated", KnowledgeInboxItem.destination == "memory")
                .limit(BATCH)
            )
        ):
            vectorized += _vectorize(db, item_id=item_id, embedder=embedder)
    ctx.items_in = analyzed + failed
    ctx.items_out = analyzed + vectorized
    ctx.detail = {"analyzed": analyzed, "failed": failed, "vectorized": vectorized}


def _analyze(db: Session, *, item_id: UUID, model: ModelCall | None) -> str:
    item = db.get(KnowledgeInboxItem, item_id)
    item.status = "analyzing"
    db.commit()
    documents = list(
        db.scalars(
            select(KnowledgeInboxDocument).where(
                KnowledgeInboxDocument.item_id == item.id, KnowledgeInboxDocument.deleted_at.is_(None)
            )
        )
    )
    texts, read, unread = [], [], []
    for document in documents:
        path = knowledge_inbox.storage_root() / document.storage_pointer if document.storage_pointer else None
        if extension(document.original_filename) in TEXT_EXTENSIONS and path is not None and path.is_file():
            texts.append(path.read_bytes()[:TEXT_READ_LIMIT].decode("utf-8", errors="replace"))
            read.append(document.original_filename)
        else:
            unread.append(document.original_filename)

    draft = _model_draft(model, item.context_text, texts) if model is not None else None
    engine = "local_executor" if draft else "deterministic"
    if draft is None:
        parts = [part for part in [item.context_text, *(text.strip()[:1500] for text in texts)] if part and part.strip()]
        draft = {"summary": "\n\n".join(parts), "facts": []}
    if not draft["summary"].strip():
        item.status = "failed"
        item.error_message = (
            "Erreur de lecture : aucun contenu lisible. L'OCR et la transcription ne sont pas encore branchés ; "
            "ajoute un texte de contexte ou un fichier texte."
        )
        db.commit()
        return "failed"
    item.extraction_draft = {
        **draft,
        "sources_read": read,
        "sources_unread": unread,
        "proposed_destination": "memory",
        "engine": engine,
    }
    item.status = "to_validate"
    item.analyzed_at = datetime.now(UTC)
    _emit(db, item.user_id, "inbox.document.analyzed", item, {"engine": engine, "sources_unread": len(unread)})
    db.commit()
    return "analyzed"


def _model_draft(model: ModelCall, context: str | None, texts: list[str]) -> dict | None:
    prompt = (
        "Tu es le modèle local d'Imperium. Résume ce que l'utilisateur transmet et ce qu'il faut en retenir. "
        'Réponds en JSON strict : {"summary": "texte en français, tutoiement", "facts": ["fait court", ...]}. '
        f"Contexte de l'utilisateur : {context or '(aucun)'}\n"
        + "\n".join(f"Source {index + 1} :\n{text[:4000]}" for index, text in enumerate(texts))
    )
    try:
        raw = model(prompt)
    except Exception:  # noqa: BLE001 - repli déterministe
        logger.warning("Knowledge inbox model call failed; deterministic draft used.")
        return None
    if not isinstance(raw, dict) or not isinstance(raw.get("summary"), str) or not raw["summary"].strip():
        return None
    facts = raw.get("facts") if isinstance(raw.get("facts"), list) else []
    return {"summary": raw["summary"].strip(), "facts": [str(fact)[:500] for fact in facts][:50]}


def _vectorize(db: Session, *, item_id: UUID, embedder: EmbedTexts) -> int:
    from app.services.ai.embedding import GpuServiceUnreachable

    item = db.get(KnowledgeInboxItem, item_id)
    final = item.extraction_final or {}
    text = "\n".join([final.get("summary") or "", *(f"- {fact}" for fact in final.get("facts") or [])]).strip()
    chunks = [text[start : start + CHUNK_CHARS] for start in range(0, len(text), CHUNK_CHARS)] or [item.title]
    try:
        vectors = embedder(chunks)
    except GpuServiceUnreachable:
        logger.info("Embedding service unreachable; item stays validated.", extra={"item_id": str(item_id)})
        return 0
    for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
        db.add(
            AIMemory(
                user_id=item.user_id,
                content=chunk,
                embedding=vector,
                embedding_model="embedding_service",
                memory_type="user_knowledge",
                source_domain="system",  # provenance, pas un périmètre (doc 70 §2)
                source_table=SOURCE_TABLE,
                source_id=str(item.id),
                privacy_level="private",
                is_active=True,
                metadata_json={"chunk": index, "chunks": len(chunks), "entry_app": item.entry_app},
                idempotency_key=f"inbox:{item.id}:{index}",
            )
        )
    item.status = "vectorized"
    item.vectorized_at = datetime.now(UTC)
    _emit(db, item.user_id, "inbox.document.vectorized", item, {"chunks": len(chunks)})
    db.commit()
    return 1


def _default_model() -> ModelCall | None:
    from app.services.ai.providers.qwen import QwenClient

    client = QwenClient()
    if client._should_dry_run():  # noqa: SLF001 - même règle que l'adaptateur Qwen
        return None
    return lambda prompt: client.call(prompt=prompt, mode="knowledge_inbox")


def _default_embedder() -> EmbedTexts | None:
    if not get_settings().embeddings_enabled:
        return None
    from app.services.ai.embedding import embed

    return lambda texts: embed(texts)
