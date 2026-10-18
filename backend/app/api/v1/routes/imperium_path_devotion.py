"""Path : adhkar (doc 41 §11, PAT-06) et progression du Coran (doc 41 §12, PAT-07)."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.path_adhkar import (
    AdhkarCounterRead,
    AdhkarIncrementRequest,
    AdhkarResetRequest,
    AdhkarRoutineCreate,
    AdhkarRoutineListResponse,
    AdhkarRoutineRead,
    AdhkarRoutineUpdate,
    AdhkarSuggestionRead,
)
from app.schemas.path_quran import (
    QuranContinuationRead,
    QuranKhatmRequest,
    QuranObjectiveRequest,
    QuranPlanCreate,
    QuranPlanRead,
    QuranProgressRequest,
)
from app.services.path import adhkar, quran
from app.services.pulse import food_stock

router = APIRouter()


def _require_key(idempotency_key: str | None) -> str:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    return idempotency_key


def _error(db: SessionDep, exc: Exception) -> JSONResponse:
    db.rollback()
    conflicts = {
        adhkar.AdhkarVersionConflictError: "ADHKAR_VERSION_CONFLICT",
        adhkar.AdhkarResetConflictError: "ADHKAR_RESET_CONFLICT",
    }
    if type(exc) in conflicts:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc), "code": conflicts[type(exc)], "current": exc.current.model_dump(mode="json")},
        )
    if isinstance(exc, quran.QuranConflictError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc), "code": exc.code, "current": exc.current.model_dump(mode="json")},
        )
    if isinstance(exc, adhkar.AdhkarNotFoundError | quran.QuranNotFoundError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, adhkar.AdhkarInputError | quran.QuranInputError):
        code = status.HTTP_422_UNPROCESSABLE_ENTITY
    else:
        code = status.HTTP_409_CONFLICT
    return JSONResponse(status_code=code, content={"detail": str(exc)})


_ERRORS = (
    adhkar.AdhkarInputError,
    adhkar.AdhkarNotFoundError,
    adhkar.AdhkarStateError,
    adhkar.AdhkarIdempotencyConflictError,
    adhkar.AdhkarVersionConflictError,
    adhkar.AdhkarResetConflictError,
    quran.QuranInputError,
    quran.QuranNotFoundError,
    quran.QuranConflictError,
    food_stock.FoodStockIdempotencyConflictError,
)


# ---------- adhkar ----------

@router.get("/adhkar/suggestions", response_model=list[AdhkarSuggestionRead])
def adhkar_suggestions_route(current_user: CurrentUserDep) -> list[AdhkarSuggestionRead]:
    """Routines proposées ; aucune n'est créée sans action de l'utilisateur."""
    return adhkar.suggestions()


@router.get("/adhkar/routines", response_model=AdhkarRoutineListResponse)
def list_routines_route(current_user: CurrentUserDep, db: SessionDep, day: date | None = None) -> AdhkarRoutineListResponse:
    """Routines et compteurs de la période en cours (jour de Paris par défaut)."""
    return adhkar.list_routines(db, current_user=current_user, day=day or adhkar.paris_today())


@router.post("/adhkar/routines", response_model=AdhkarRoutineRead, status_code=status.HTTP_201_CREATED)
def create_routine_route(
    payload: AdhkarRoutineCreate,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Active une routine (8 actives au plus)."""
    try:
        read, duplicate = adhkar.create_routine(db, current_user=current_user, payload=payload,
                                                idempotency_key=_require_key(idempotency_key))
    except _ERRORS as exc:
        return _error(db, exc)
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return read


@router.patch("/adhkar/routines/{routine_id}", response_model=AdhkarRoutineRead)
def update_routine_route(
    routine_id: UUID,
    payload: AdhkarRoutineUpdate,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Libellé, cible, fréquence, pause ; version lue obligatoire."""
    try:
        return adhkar.update_routine(db, current_user=current_user, routine_id=routine_id, payload=payload,
                                     idempotency_key=_require_key(idempotency_key), request_path=request.url.path)
    except _ERRORS as exc:
        return _error(db, exc)


@router.delete("/adhkar/routines/{routine_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_routine_route(routine_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    try:
        adhkar.delete_routine(db, current_user=current_user, routine_id=routine_id)
    except _ERRORS as exc:
        return _error(db, exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/adhkar/routines/{routine_id}/increment", response_model=AdhkarCounterRead)
def increment_route(
    routine_id: UUID,
    payload: AdhkarIncrementRequest,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """+amount sur la période ; clés distinctes = sommes, même clé = rejeu."""
    try:
        read, _ = adhkar.increment(db, current_user=current_user, routine_id=routine_id, payload=payload,
                                   idempotency_key=_require_key(idempotency_key))
    except _ERRORS as exc:
        return _error(db, exc)
    return read


@router.post("/adhkar/routines/{routine_id}/reset", response_model=AdhkarCounterRead)
def reset_route(
    routine_id: UUID,
    payload: AdhkarResetRequest,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Remise à zéro avec le compte affiché ; différent → 409 ADHKAR_RESET_CONFLICT."""
    try:
        return adhkar.reset(db, current_user=current_user, routine_id=routine_id, payload=payload,
                            idempotency_key=_require_key(idempotency_key), request_path=request.url.path)
    except _ERRORS as exc:
        return _error(db, exc)


# ---------- Coran ----------

@router.get("/quran/continuation", response_model=QuranContinuationRead)
def quran_continuation_route(current_user: CurrentUserDep, db: SessionDep) -> QuranContinuationRead:
    """« Continuer ma lecture » : dernier point validé, page suivante, objectif, plan du jour."""
    return quran.continuation(db, current_user=current_user)


@router.post("/quran/progress", response_model=QuranContinuationRead)
def quran_progress_route(
    payload: QuranProgressRequest,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Valide la dernière page lue (page, sourate ou juz) ; retour en arrière confirmé."""
    try:
        return quran.record_progress(db, current_user=current_user, payload=payload,
                                     idempotency_key=_require_key(idempotency_key), request_path=request.url.path)
    except _ERRORS as exc:
        return _error(db, exc)


@router.patch("/quran/objective", response_model=QuranContinuationRead)
def quran_objective_route(
    payload: QuranObjectiveRequest,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    try:
        return quran.set_objective(db, current_user=current_user, payload=payload,
                                   idempotency_key=_require_key(idempotency_key), request_path=request.url.path)
    except _ERRORS as exc:
        return _error(db, exc)


@router.post("/quran/khatm", response_model=QuranContinuationRead)
def quran_khatm_route(
    payload: QuranKhatmRequest,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Khatm confirmé par l'utilisateur, une fois la page 604 validée."""
    try:
        return quran.confirm_khatm(db, current_user=current_user, payload=payload,
                                   idempotency_key=_require_key(idempotency_key), request_path=request.url.path)
    except _ERRORS as exc:
        return _error(db, exc)


@router.post("/quran/plans", response_model=QuranPlanRead, status_code=status.HTTP_201_CREATED)
def create_plan_route(
    payload: QuranPlanCreate,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """« Choisir un plan » : remplace le plan actif, part de la page suivant le point de reprise."""
    try:
        read, duplicate = quran.create_plan(db, current_user=current_user, payload=payload,
                                            idempotency_key=_require_key(idempotency_key))
    except _ERRORS as exc:
        return _error(db, exc)
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return read


@router.post("/quran/plans/{plan_id}/stop", response_model=QuranPlanRead)
def stop_plan_route(plan_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    try:
        return quran.stop_plan(db, current_user=current_user, plan_id=plan_id)
    except _ERRORS as exc:
        return _error(db, exc)
