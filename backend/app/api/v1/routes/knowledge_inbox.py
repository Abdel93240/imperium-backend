"""Routes de Nourrir l'IA — /api/ai/knowledge-inbox (doc 70 §11).

Les fichiers sont envoyés en corps brut (un appel par fichier) : nom dans l'en-tête
X-Filename (encodé URL), type dans Content-Type. Taille plafonnée pendant la réception.
"""

import tempfile
from typing import Annotated
from urllib.parse import unquote
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentUserDep, SessionDep
from app.api.v1.routes.imperium_pulse_health import consent_required_response
from app.schemas.knowledge_inbox import (
    ExtractionUpdate,
    InboxItemCreate,
    InboxItemListResponse,
    InboxItemRead,
    InboxSourceRead,
    InboxValidateRequest,
    ZipExpansionRead,
)
from app.services.ai import knowledge_inbox as inbox
from app.services.ai.knowledge_files import SIZE_LIMITS, KnowledgeFileError
from app.services.pulse import health_consent

router = APIRouter()
MAX_UPLOAD_BYTES = max(SIZE_LIMITS.values())


def _http(db, exc: Exception) -> HTTPException:
    db.rollback()
    if isinstance(exc, inbox.InboxNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, KnowledgeFileError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Fichier refusé : {exc}")
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


_ERRORS = (inbox.InboxNotFoundError, inbox.InboxStateError, KnowledgeFileError)


@router.post("/items", response_model=InboxItemRead, status_code=status.HTTP_201_CREATED)
def create_item_route(
    payload: InboxItemCreate,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> InboxItemRead:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    return inbox.create_item(db, current_user=current_user, payload=payload, idempotency_key=idempotency_key)


@router.get("/items", response_model=InboxItemListResponse)
def list_items_route(current_user: CurrentUserDep, db: SessionDep) -> InboxItemListResponse:
    return inbox.list_items(db, current_user=current_user)


@router.get("/items/{item_id}", response_model=InboxItemRead)
def get_item_route(item_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> InboxItemRead:
    try:
        return inbox.get_item(db, current_user=current_user, item_id=item_id)
    except _ERRORS as exc:
        raise _http(db, exc) from exc


@router.post("/items/{item_id}/sources", response_model=InboxSourceRead | ZipExpansionRead, status_code=status.HTTP_201_CREATED)
async def add_source_route(
    item_id: UUID,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    filename: Annotated[str | None, Header(alias="X-Filename")] = None,
    content_type: Annotated[str | None, Header(alias="Content-Type")] = None,
    content_length: Annotated[int | None, Header(alias="Content-Length")] = None,
) -> InboxSourceRead | ZipExpansionRead:
    if not filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-Filename header.")
    if content_length is not None and content_length > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Fichier trop volumineux.")
    with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024) as buffer:
        received = 0
        async for chunk in request.stream():
            received += len(chunk)
            if received > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Fichier trop volumineux.")
            buffer.write(chunk)
        buffer.seek(0)
        try:
            return inbox.add_source(
                db, current_user=current_user, item_id=item_id, filename=unquote(filename), content_type=content_type, stream=buffer
            )
        except _ERRORS as exc:
            raise _http(db, exc) from exc


@router.get("/items/{item_id}/sources/{document_id}")
def get_source_route(item_id: UUID, document_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> FileResponse:
    """Aperçu d'une source (lecture seule)."""
    try:
        path, document = inbox.source_path(db, current_user=current_user, item_id=item_id, document_id=document_id)
    except _ERRORS as exc:
        raise _http(db, exc) from exc
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source file missing.")
    return FileResponse(path, media_type=document.mime_type, filename=document.original_filename)


@router.post("/items/{item_id}/analyze", response_model=InboxItemRead, status_code=status.HTTP_202_ACCEPTED)
def analyze_item_route(item_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> InboxItemRead:
    try:
        return inbox.request_analysis(db, current_user=current_user, item_id=item_id)
    except _ERRORS as exc:
        raise _http(db, exc) from exc


@router.patch("/items/{item_id}/extraction", response_model=InboxItemRead)
def update_extraction_route(item_id: UUID, payload: ExtractionUpdate, current_user: CurrentUserDep, db: SessionDep) -> InboxItemRead:
    try:
        return inbox.update_extraction(db, current_user=current_user, item_id=item_id, payload=payload)
    except _ERRORS as exc:
        raise _http(db, exc) from exc


@router.post("/items/{item_id}/validate", response_model=InboxItemRead)
def validate_item_route(item_id: UUID, payload: InboxValidateRequest, current_user: CurrentUserDep, db: SessionDep) -> InboxItemRead:
    try:
        return inbox.validate_item(db, current_user=current_user, item_id=item_id, payload=payload)
    except health_consent.ConsentRequiredError as exc:  # prise de sang : accord « medical » exigé
        db.rollback()
        return consent_required_response(exc)
    except _ERRORS as exc:
        raise _http(db, exc) from exc


@router.post("/items/{item_id}/retry", response_model=InboxItemRead)
def retry_item_route(item_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> InboxItemRead:
    try:
        return inbox.retry_item(db, current_user=current_user, item_id=item_id)
    except _ERRORS as exc:
        raise _http(db, exc) from exc


@router.post("/items/{item_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_item_route(item_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> Response:
    """Annuler avant validation : rien n'est gardé, le dépôt brut est supprimé."""
    try:
        inbox.cancel_item(db, current_user=current_user, item_id=item_id)
    except _ERRORS as exc:
        raise _http(db, exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/items/{item_id}")
def delete_item_route(item_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> dict:
    """Suppression (après confirmation, exécutée par le chatbot) : sources et informations retenues ensemble."""
    try:
        neutralized = inbox.delete_item(db, current_user=current_user, item_id=item_id)
    except _ERRORS as exc:
        raise _http(db, exc) from exc
    return {"deleted": True, "memories_neutralized": neutralized}
