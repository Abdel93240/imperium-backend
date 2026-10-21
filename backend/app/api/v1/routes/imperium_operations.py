"""Routes Opérations : projets, missions de projet, routines (doc 71 §3, §4.1, §8)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Response, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.operations import (
    IntrinsicMissionCreate,
    IntrinsicMissionListResponse,
    IntrinsicMissionRead,
    MissionContentUpdate,
    MissionReorderRequest,
    ProjectCreate,
    ProjectListResponse,
    ProjectMissionCreate,
    ProjectMissionRead,
    ProjectRead,
    ProjectReorderRequest,
    ProjectUpdate,
    RoutineCheckRequest,
    RoutineCreate,
    RoutineListResponse,
    RoutinePlaceRequest,
    RoutineRead,
    RoutineTodayResponse,
    RoutineUpdate,
)
from app.services.imperium import operations as ops

router = APIRouter()

IdempotencyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]


def _key(idempotency_key: str | None) -> str:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    return idempotency_key


def _http(db, exc: Exception) -> HTTPException:
    db.rollback()
    if isinstance(exc, ops.OperationsNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ops.OperationsValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


_ERRORS = (ops.OperationsNotFoundError, ops.OperationsConflictError, ops.OperationsValidationError)


# ---------- Projets ----------

@router.get("/projects", response_model=ProjectListResponse)
def list_projects_route(current_user: CurrentUserDep, db: SessionDep) -> ProjectListResponse:
    return ops.list_projects(db, current_user=current_user)


@router.get("/projects/completed", response_model=list[ProjectRead])
def completed_projects_route(current_user: CurrentUserDep, db: SessionDep) -> list[ProjectRead]:
    return ops.list_completed_projects(db, current_user=current_user)


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project_route(
    payload: ProjectCreate, current_user: CurrentUserDep, db: SessionDep, idempotency_key: IdempotencyHeader = None
) -> ProjectRead:
    try:
        return ops.create_project(db, current_user=current_user, payload=payload, idempotency_key=_key(idempotency_key))
    except _ERRORS as exc:
        raise _http(db, exc) from exc


@router.post("/projects/reorder", response_model=ProjectListResponse)
def reorder_projects_route(payload: ProjectReorderRequest, current_user: CurrentUserDep, db: SessionDep) -> ProjectListResponse:
    try:
        return ops.reorder_projects(db, current_user=current_user, project_ids=payload.project_ids)
    except _ERRORS as exc:
        raise _http(db, exc) from exc


@router.patch("/projects/{project_id}", response_model=ProjectRead)
def update_project_route(project_id: UUID, payload: ProjectUpdate, current_user: CurrentUserDep, db: SessionDep) -> ProjectRead:
    try:
        return ops.update_project(db, current_user=current_user, project_id=project_id, payload=payload)
    except _ERRORS as exc:
        raise _http(db, exc) from exc


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_route(project_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> Response:
    """Ses missions à venir sont annulées ; l'historique est conservé."""
    try:
        ops.delete_project(db, current_user=current_user, project_id=project_id)
    except _ERRORS as exc:
        raise _http(db, exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/projects/{project_id}/complete", response_model=ProjectRead)
def complete_project_route(project_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> ProjectRead:
    try:
        return ops.complete_project(db, current_user=current_user, project_id=project_id)
    except _ERRORS as exc:
        raise _http(db, exc) from exc


# ---------- Missions de projet ----------

@router.post("/projects/{project_id}/missions", response_model=ProjectMissionRead, status_code=status.HTTP_201_CREATED)
def add_project_mission_route(
    project_id: UUID,
    payload: ProjectMissionCreate,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: IdempotencyHeader = None,
) -> ProjectMissionRead:
    try:
        return ops.add_project_mission(
            db, current_user=current_user, project_id=project_id, payload=payload, idempotency_key=_key(idempotency_key)
        )
    except _ERRORS as exc:
        raise _http(db, exc) from exc


@router.post("/projects/{project_id}/missions/reorder", status_code=status.HTTP_204_NO_CONTENT)
def reorder_project_missions_route(
    project_id: UUID, payload: MissionReorderRequest, current_user: CurrentUserDep, db: SessionDep
) -> Response:
    try:
        ops.reorder_project_missions(db, current_user=current_user, project_id=project_id, mission_ids=payload.mission_ids)
    except _ERRORS as exc:
        raise _http(db, exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/missions/{mission_id}", response_model=ProjectMissionRead)
def update_mission_content_route(
    mission_id: UUID, payload: MissionContentUpdate, current_user: CurrentUserDep, db: SessionDep
) -> ProjectMissionRead:
    """Nom, description, durée estimée, notes ; domaine et dates (missions hors projet) ; une mission terminée
    est en lecture seule."""
    try:
        return ops.update_mission_content(db, current_user=current_user, mission_id=mission_id, payload=payload)
    except _ERRORS as exc:
        raise _http(db, exc) from exc


@router.delete("/missions/{mission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mission_route(mission_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> Response:
    try:
        ops.delete_mission(db, current_user=current_user, mission_id=mission_id)
    except _ERRORS as exc:
        raise _http(db, exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Missions hors projet ----------

@router.get("/intrinsic-missions", response_model=IntrinsicMissionListResponse)
def list_intrinsic_missions_route(current_user: CurrentUserDep, db: SessionDep) -> IntrinsicMissionListResponse:
    """Missions sans projet : à faire, puis les dernières faites."""
    return ops.list_intrinsic_missions(db, current_user=current_user)


@router.post("/intrinsic-missions", response_model=IntrinsicMissionRead, status_code=status.HTTP_201_CREATED)
def create_intrinsic_mission_route(
    payload: IntrinsicMissionCreate, current_user: CurrentUserDep, db: SessionDep, idempotency_key: IdempotencyHeader = None
) -> IntrinsicMissionRead:
    try:
        return ops.create_intrinsic_mission(db, current_user=current_user, payload=payload,
                                            idempotency_key=_key(idempotency_key))
    except _ERRORS as exc:
        raise _http(db, exc) from exc


@router.post("/missions/{mission_id}/done", response_model=IntrinsicMissionRead)
def mark_mission_done_route(mission_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> IntrinsicMissionRead:
    """« Faite » hors du plan du jour (mission en attente ou en standby)."""
    try:
        return ops.mark_mission_done(db, current_user=current_user, mission_id=mission_id)
    except _ERRORS as exc:
        raise _http(db, exc) from exc


# ---------- Routines ----------

@router.get("/routines", response_model=RoutineListResponse)
def list_routines_route(current_user: CurrentUserDep, db: SessionDep) -> RoutineListResponse:
    return ops.list_routines(db, current_user=current_user)


@router.get("/routines/today", response_model=RoutineTodayResponse)
def today_routines_route(current_user: CurrentUserDep, db: SessionDep) -> RoutineTodayResponse:
    return ops.today_routines(db, current_user=current_user)


@router.post("/routines", response_model=RoutineRead, status_code=status.HTTP_201_CREATED)
def create_routine_route(
    payload: RoutineCreate, current_user: CurrentUserDep, db: SessionDep, idempotency_key: IdempotencyHeader = None
) -> RoutineRead:
    try:
        return ops.create_routine(db, current_user=current_user, payload=payload, idempotency_key=_key(idempotency_key))
    except _ERRORS as exc:
        raise _http(db, exc) from exc


@router.patch("/routines/{routine_id}", response_model=RoutineRead)
def update_routine_route(routine_id: UUID, payload: RoutineUpdate, current_user: CurrentUserDep, db: SessionDep) -> RoutineRead:
    try:
        return ops.update_routine(db, current_user=current_user, routine_id=routine_id, payload=payload)
    except _ERRORS as exc:
        raise _http(db, exc) from exc


@router.delete("/routines/{routine_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_routine_route(routine_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> Response:
    """Elle ne sera plus planifiée ; l'historique est conservé."""
    try:
        ops.delete_routine(db, current_user=current_user, routine_id=routine_id)
    except _ERRORS as exc:
        raise _http(db, exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/routines/{routine_id}/place", response_model=RoutineTodayResponse)
def place_routine_route(
    routine_id: UUID, payload: RoutinePlaceRequest, current_user: CurrentUserDep, db: SessionDep
) -> RoutineTodayResponse:
    try:
        return ops.place_routine(db, current_user=current_user, routine_id=routine_id, operational_date=payload.operational_date)
    except _ERRORS as exc:
        raise _http(db, exc) from exc


@router.post("/routines/{routine_id}/check", response_model=RoutineTodayResponse)
def check_routine_route(
    routine_id: UUID, payload: RoutineCheckRequest, current_user: CurrentUserDep, db: SessionDep
) -> RoutineTodayResponse:
    try:
        return ops.check_routine(db, current_user=current_user, routine_id=routine_id, done=payload.done)
    except _ERRORS as exc:
        raise _http(db, exc) from exc
