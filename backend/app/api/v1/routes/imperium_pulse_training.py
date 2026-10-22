"""Programme d'entraînement Pulse : création manuelle, statut, cibles hebdo, volume et dette (spec Pulse §3.6)."""

from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.pulse_training import (
    ProgramCreate,
    ProgramRequestCreate,
    ProgramRequestLatest,
    ProgramRequestRead,
    ProgramCurrentRead,
    ProgramRead,
    ProgramStatusRequest,
    TargetRead,
    TargetsReplace,
)
from app.services.pulse import program_design, training

router = APIRouter()


def _disabled() -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                        content={"detail": "Disabled.", "code": "PULSE_PROGRAMS_DISABLED"})


@router.get("/programs/current", response_model=ProgramCurrentRead)
def current_route(current_user: CurrentUserDep, db: SessionDep):
    """Programme actif, cibles de la semaine avec le volume planifié, dettes ouvertes ou placées."""
    if not training.programs_enabled(db):
        return _disabled()
    return training.current(db, current_user=current_user)


@router.post("/programs", response_model=ProgramRead, status_code=status.HTTP_201_CREATED)
def create_route(
    payload: ProgramCreate,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if not training.programs_enabled(db):
        return _disabled()
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    try:
        program, replayed = training.create_program(db, current_user=current_user, payload=payload,
                                                    idempotency_key=idempotency_key)
    except training.ProgramIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if replayed:
        response.status_code = status.HTTP_200_OK
    return program


@router.post("/programs/{program_id}/status", response_model=ProgramRead)
def status_route(program_id: UUID, payload: ProgramStatusRequest, current_user: CurrentUserDep, db: SessionDep):
    if not training.programs_enabled(db):
        return _disabled()
    try:
        return training.set_status(db, current_user=current_user, program_id=program_id, status=payload.status)
    except training.ProgramNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except training.ProgramStateError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.put("/programs/{program_id}/targets", response_model=list[TargetRead])
def targets_route(program_id: UUID, payload: TargetsReplace, current_user: CurrentUserDep, db: SessionDep):
    if not training.programs_enabled(db):
        return _disabled()
    try:
        return training.replace_targets(db, current_user=current_user, program_id=program_id, payload=payload)
    except training.ProgramNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# --- Programme conçu par le cerveau (P3) ------------------------------------------------------------------------

def _design_call(db, action):
    try:
        return action()
    except program_design.ProgramDesignNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (program_design.ProgramDesignStateError, program_design.ProgramDesignIdempotencyError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/programs/requests", response_model=ProgramRequestRead, status_code=status.HTTP_202_ACCEPTED)
def request_program_route(
    payload: ProgramRequestCreate,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Demande un programme au cerveau ; la proposition arrive ensuite (generating → proposed)."""
    if not training.programs_enabled(db):
        return _disabled()
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    read, replayed = _design_call(db, lambda: program_design.request(db, current_user=current_user, payload=payload,
                                                                      idempotency_key=idempotency_key))
    if replayed:
        response.status_code = status.HTTP_200_OK
    return read


@router.get("/programs/requests/latest", response_model=ProgramRequestLatest)
def latest_request_route(current_user: CurrentUserDep, db: SessionDep):
    """Demande pas encore tranchée (en cours, proposée, échouée) ; `request` null sinon."""
    if not training.programs_enabled(db):
        return _disabled()
    return ProgramRequestLatest(request=program_design.latest(db, current_user=current_user))


@router.post("/programs/requests/{request_id}/accept", response_model=ProgramRequestRead)
def accept_request_route(request_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    """Validation : le programme remplace l'actif, ses séances sont créées."""
    if not training.programs_enabled(db):
        return _disabled()
    return _design_call(db, lambda: program_design.accept(db, current_user=current_user, request_id=request_id))


@router.post("/programs/requests/{request_id}/reject", response_model=ProgramRequestRead)
def reject_request_route(request_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    if not training.programs_enabled(db):
        return _disabled()
    return _design_call(db, lambda: program_design.reject(db, current_user=current_user, request_id=request_id))
