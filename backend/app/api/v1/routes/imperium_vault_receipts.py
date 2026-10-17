"""Justificatifs du Vault (doc 37 §3, doc 59 VAU-04/05, maquette 05).

Module séparé des routes du registre Vault : celles-ci restent sans IA ni OCR
(invariants patch 9B–9D). La dépense n'est écrite qu'à la validation, par le
service canonique du registre.
"""

import io
from typing import Annotated, Literal
from urllib.parse import unquote
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.vault import VaultReceiptExtractionRead, VaultReceiptValidateRequest, VaultReceiptValidateResponse
from app.services.imperium.vault_transactions import VaultTransactionIdempotencyConflictError
from app.services.vault import receipts

router = APIRouter()


def _require_key(idempotency_key: str | None) -> str:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    return idempotency_key


@router.post("/receipt-extractions", response_model=VaultReceiptExtractionRead, status_code=status.HTTP_201_CREATED)
async def create_receipt_extraction_route(
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    x_filename: Annotated[str, Header(alias="X-Filename")],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    content_length: Annotated[int | None, Header(alias="Content-Length")] = None,
    entry_app: Literal["vault", "imperium"] = "vault",
) -> VaultReceiptExtractionRead:
    """Photo (ou PDF) du ticket en corps brut ; renvoie le brouillon prêt, ou l'échec avec son message."""
    key = _require_key(idempotency_key)
    if content_length is not None and content_length > receipts.MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Fichier refusé : 25 Mo maximum.")
    buffer = bytearray()
    async for chunk in request.stream():
        buffer.extend(chunk)
        if len(buffer) > receipts.MAX_BYTES:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Fichier refusé : 25 Mo maximum.")
    try:
        # La lecture OCR peut prendre jusqu'à 60 s : hors de la boucle d'événements.
        extraction, duplicate = await run_in_threadpool(
            receipts.create_extraction, db, current_user=current_user, filename=unquote(x_filename),
            content_type=request.headers.get("content-type"), stream=io.BytesIO(bytes(buffer)), idempotency_key=key,
            entry_app=entry_app,
        )
    except receipts.ReceiptFileError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return extraction


@router.get("/receipt-extractions/{extraction_id}", response_model=VaultReceiptExtractionRead)
def get_receipt_extraction_route(extraction_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> VaultReceiptExtractionRead:
    try:
        return receipts.get_extraction(db, current_user=current_user, extraction_id=extraction_id)
    except receipts.ReceiptNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/receipt-extractions/{extraction_id}/image")
def get_receipt_image_route(extraction_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> FileResponse:
    """Vignette de l'écran de vérification, puis justificatif conservé."""
    try:
        path, mime_type = receipts.image_path(db, current_user=current_user, extraction_id=extraction_id)
    except receipts.ReceiptNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FileResponse(path, media_type=mime_type, headers={"Cache-Control": "private, no-store"})


@router.post("/receipt-extractions/{extraction_id}/validate", response_model=VaultReceiptValidateResponse)
def validate_receipt_extraction_route(
    extraction_id: UUID,
    payload: VaultReceiptValidateRequest,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> VaultReceiptValidateResponse:
    key = _require_key(idempotency_key)
    try:
        return receipts.validate_extraction(
            db, current_user=current_user, extraction_id=extraction_id, payload=payload, idempotency_key=key,
            request_method=request.method, request_path=request.url.path,
        )
    except receipts.ReceiptNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (receipts.ReceiptStateError, VaultTransactionIdempotencyConflictError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Receipt conflicts with an existing record.") from exc


@router.post("/receipt-extractions/{extraction_id}/cancel", response_model=VaultReceiptExtractionRead)
def cancel_receipt_extraction_route(extraction_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> VaultReceiptExtractionRead:
    try:
        return receipts.cancel_extraction(db, current_user=current_user, extraction_id=extraction_id)
    except receipts.ReceiptNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except receipts.ReceiptStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
