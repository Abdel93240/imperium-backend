"""Santé sensible Pulse : consentement par domaine, relevé corporel PUL-08, douleurs PUL-09 et médical PUL-14
(doc 40 §14, §16, doc 34, doc 05)."""

import io
from datetime import date
from typing import Annotated
from urllib.parse import quote, unquote
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Path, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.pulse_health import (
    BodySnapshotCreate,
    BodySnapshotListResponse,
    BodySnapshotRead,
    ConsentGrantRequest,
    ConsentListResponse,
    ConsentRead,
    DeletedCountRead,
    HealthDomain,
    MedicalDocType,
    MedicalDocumentListResponse,
    MedicalDocumentRead,
    MedicalRuleActivateRequest,
    MedicalRuleCreate,
    MedicalRuleListResponse,
    MedicalRuleRead,
    PainLogCreate,
    PainLogListResponse,
    PainLogRead,
)
from app.services.pulse import body, health_consent, medical, pain

router = APIRouter()

DomainPath = Annotated[HealthDomain, Path()]


def consent_required_response(exc: health_consent.ConsentRequiredError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": str(exc), "code": "CONSENT_REQUIRED", "domain": exc.domain},
    )


@router.get("/consents", response_model=ConsentListResponse)
def list_consents_route(current_user: CurrentUserDep, db: SessionDep) -> ConsentListResponse:
    """État et texte à accepter pour chaque domaine (body, pain, medical)."""
    return health_consent.list_consents(db, current_user=current_user)


@router.post("/consents/{domain}", response_model=ConsentRead)
def grant_consent_route(
    domain: DomainPath, payload: ConsentGrantRequest, current_user: CurrentUserDep, db: SessionDep
) -> ConsentRead:
    """Accord explicite au texte affiché ; texte changé depuis → 409, l'écran doit le remontrer."""
    try:
        return health_consent.grant(db, current_user=current_user, domain=domain, text_version=payload.text_version)
    except health_consent.ConsentVersionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/consents/{domain}", response_model=ConsentRead)
def revoke_consent_route(domain: DomainPath, current_user: CurrentUserDep, db: SessionDep) -> ConsentRead:
    """Retrait : les écritures sont refusées ensuite ; les données restent lisibles et supprimables."""
    return health_consent.revoke(db, current_user=current_user, domain=domain)


@router.get("/body-snapshots", response_model=BodySnapshotListResponse)
def list_body_snapshots_route(current_user: CurrentUserDep, db: SessionDep) -> BodySnapshotListResponse:
    """Accès à ses relevés, même après retrait du consentement."""
    return body.list_snapshots(db, current_user=current_user)


@router.post("/body-snapshots", response_model=BodySnapshotRead, status_code=status.HTTP_201_CREATED)
def create_body_snapshot_route(
    payload: BodySnapshotCreate,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Sans consentement « body » actif → 403 `CONSENT_REQUIRED`."""
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    try:
        read, duplicate = body.create_snapshot(db, current_user=current_user, payload=payload, idempotency_key=idempotency_key)
    except health_consent.ConsentRequiredError as exc:
        db.rollback()
        return consent_required_response(exc)
    except body.BodyIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return read


@router.delete("/body-snapshots", response_model=DeletedCountRead)
def delete_all_body_snapshots_route(current_user: CurrentUserDep, db: SessionDep, confirm: bool = False) -> DeletedCountRead:
    """Suppression réelle de tous les relevés ; `confirm=true` obligatoire."""
    if not confirm:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Add confirm=true to delete everything.")
    return DeletedCountRead(deleted=body.delete_all(db, current_user=current_user))


@router.delete("/body-snapshots/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_body_snapshot_route(snapshot_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> Response:
    try:
        body.delete_snapshot(db, current_user=current_user, snapshot_id=snapshot_id)
    except body.BodySnapshotNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/pain-logs", response_model=PainLogListResponse)
def list_pain_logs_route(current_user: CurrentUserDep, db: SessionDep, include_resolved: bool = False) -> PainLogListResponse:
    """Douleurs en cours (toutes avec `include_resolved=true`), la plus récente d'abord."""
    return pain.list_logs(db, current_user=current_user, include_resolved=include_resolved)


@router.post("/pain-logs", response_model=PainLogRead, status_code=status.HTTP_201_CREATED)
def create_pain_log_route(
    payload: PainLogCreate,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Sans consentement « pain » actif → 403 `CONSENT_REQUIRED` ; douleur 8 à 10 → `suggest_replan`."""
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    try:
        read, duplicate = pain.create_log(db, current_user=current_user, payload=payload, idempotency_key=idempotency_key)
    except health_consent.ConsentRequiredError as exc:
        db.rollback()
        return consent_required_response(exc)
    except pain.PainLogNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except pain.PainIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return read


@router.post("/pain-logs/{pain_log_id}/resolve", response_model=PainLogRead)
def resolve_pain_log_route(pain_log_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    try:
        return pain.resolve_log(db, current_user=current_user, pain_log_id=pain_log_id)
    except health_consent.ConsentRequiredError as exc:
        db.rollback()
        return consent_required_response(exc)
    except pain.PainLogNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/pain-logs", response_model=DeletedCountRead)
def delete_all_pain_logs_route(current_user: CurrentUserDep, db: SessionDep, confirm: bool = False) -> DeletedCountRead:
    """Suppression réelle de tout le journal ; `confirm=true` obligatoire."""
    if not confirm:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Add confirm=true to delete everything.")
    return DeletedCountRead(deleted=pain.delete_all(db, current_user=current_user))


@router.delete("/pain-logs/{pain_log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pain_log_route(pain_log_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> Response:
    try:
        pain.delete_log(db, current_user=current_user, pain_log_id=pain_log_id)
    except pain.PainLogNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- médical (doc 34) ----------

def _require_key(idempotency_key: str | None) -> str:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    return idempotency_key


def _medical_error(db: SessionDep, exc: Exception):
    db.rollback()
    if isinstance(exc, health_consent.ConsentRequiredError):
        return consent_required_response(exc)
    if isinstance(exc, medical.UploadConsentMissingError):
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc), "code": "UPLOAD_CONSENT_REQUIRED"})
    if isinstance(exc, medical.MedicalNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, medical.MedicalFileError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


_MEDICAL_ERRORS = (
    health_consent.ConsentRequiredError,
    health_consent.ConsentVersionError,
    medical.UploadConsentMissingError,
    medical.MedicalNotFoundError,
    medical.MedicalFileError,
    medical.MedicalStateError,
    medical.MedicalIdempotencyConflictError,
)


@router.get("/medical-documents", response_model=MedicalDocumentListResponse)
def list_medical_documents_route(current_user: CurrentUserDep, db: SessionDep) -> MedicalDocumentListResponse:
    return medical.list_documents(db, current_user=current_user)


@router.post("/medical-documents", response_model=MedicalDocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_medical_document_route(
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    doc_type: MedicalDocType,
    x_filename: Annotated[str, Header(alias="X-Filename")],
    consent: bool = False,
    consent_version: str | None = None,
    doc_date: date | None = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    content_length: Annotated[int | None, Header(alias="Content-Length")] = None,
):
    """Corps brut ; consentement « medical » actif ET `consent=true` + `consent_version` pour cet envoi (doc 34 §5)."""
    key = _require_key(idempotency_key)
    if content_length is not None and content_length > medical.MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Fichier refusé : 25 Mo maximum.")
    buffer = bytearray()
    async for chunk in request.stream():
        buffer.extend(chunk)
        if len(buffer) > medical.MAX_BYTES:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Fichier refusé : 25 Mo maximum.")
    try:
        read, duplicate = await run_in_threadpool(
            medical.upload_document, db, current_user=current_user, filename=unquote(x_filename),
            content_type=request.headers.get("content-type"), stream=io.BytesIO(bytes(buffer)), idempotency_key=key,
            doc_type=doc_type, doc_date=doc_date, upload_consent=consent, consent_version=consent_version,
        )
    except _MEDICAL_ERRORS as exc:
        return _medical_error(db, exc)
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return read


@router.get("/medical-documents/{document_id}/file")
def medical_document_file_route(document_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    try:
        path, mime_type, name = medical.document_file(db, current_user=current_user, document_id=document_id)
    except _MEDICAL_ERRORS as exc:
        return _medical_error(db, exc)
    return FileResponse(path, media_type=mime_type,
                        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}", "Cache-Control": "no-store"})


@router.delete("/medical-documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_medical_document_route(document_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    """Suppression réelle du fichier, du document et des règles qui en sont tirées."""
    try:
        medical.delete_document(db, current_user=current_user, document_id=document_id)
    except _MEDICAL_ERRORS as exc:
        return _medical_error(db, exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/medical-rules", response_model=MedicalRuleListResponse)
def list_medical_rules_route(current_user: CurrentUserDep, db: SessionDep) -> MedicalRuleListResponse:
    return medical.list_rules(db, current_user=current_user)


@router.get("/medical-rules/active", response_model=MedicalRuleListResponse)
def active_medical_rules_route(current_user: CurrentUserDep, db: SessionDep) -> MedicalRuleListResponse:
    """Règles actives et non échues : celles que le planning et les suggestions peuvent lire."""
    return medical.list_rules(db, current_user=current_user, active_only=True)


@router.post("/medical-rules", response_model=MedicalRuleRead, status_code=status.HTTP_201_CREATED)
def create_medical_rule_route(
    payload: MedicalRuleCreate,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Règle saisie à la main : toujours « proposed », jamais active sans activation explicite."""
    try:
        read, duplicate = medical.create_rule(db, current_user=current_user, payload=payload, idempotency_key=_require_key(idempotency_key))
    except _MEDICAL_ERRORS as exc:
        return _medical_error(db, exc)
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return read


@router.post("/medical-rules/{rule_id}/activate", response_model=MedicalRuleRead)
def activate_medical_rule_route(
    rule_id: UUID,
    payload: MedicalRuleActivateRequest,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Trois confirmations obligatoires ; règle critique → `acknowledge_critical` ; `supersedes_rule_id` facultatif."""
    try:
        return medical.activate_rule(
            db, current_user=current_user, rule_id=rule_id, payload=payload, idempotency_key=_require_key(idempotency_key)
        )
    except _MEDICAL_ERRORS as exc:
        return _medical_error(db, exc)


@router.post("/medical-rules/{rule_id}/deactivate", response_model=MedicalRuleRead)
def deactivate_medical_rule_route(rule_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    try:
        return medical.deactivate_rule(db, current_user=current_user, rule_id=rule_id)
    except _MEDICAL_ERRORS as exc:
        return _medical_error(db, exc)


@router.delete("/medical-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_medical_rule_route(rule_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    try:
        medical.delete_rule(db, current_user=current_user, rule_id=rule_id)
    except _MEDICAL_ERRORS as exc:
        return _medical_error(db, exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
