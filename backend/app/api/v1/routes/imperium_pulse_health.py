"""Santé sensible Pulse : consentement par domaine et relevé corporel PUL-08 (doc 40 §14, doc 05)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Path, Response, status
from fastapi.responses import JSONResponse

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
)
from app.services.pulse import body, health_consent

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
