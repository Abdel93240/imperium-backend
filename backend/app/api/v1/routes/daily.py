"""Daily (spec Daily §12).

Réglage des barèmes (`GET/PUT settings/scoring`, `GET settings/scoring/{code}/versions`) : servi
seulement si `daily.settings_enabled` (carte ACT-DLY-02), 409 DAILY_SETTINGS_DISABLED sinon.

Sélection Niveau 1 (`POST complete/{id}`, `POST next`, `GET current`, `GET selection-log`, contraintes et
dépendances des missions) : servie seulement si `daily.selection_enabled` (carte ACT-DLY-04), 409
DAILY_SELECTION_DISABLED sinon. `GET queue` (admin/debug) demande en plus `daily.queue_debug_enabled`.

Override (`POST override`) : servi seulement si `daily.override_enabled` (carte ACT-DLY-07), 409
DAILY_OVERRIDE_DISABLED sinon ; 400 OVERRIDE_REASON_REQUIRED sans raison.
"""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUserDep, SessionDep
from app.models.event import Event
from app.models.imperium import ImperiumMission
from app.schemas.daily import (
    DayReplanRead,
    DayReplanRequest,
    ProgrammeRead,
    DailyCompleteResponse,
    DailyCurrentRead,
    MissionConstraints,
    MissionDependencyCreate,
    MissionDependencyRead,
    OverrideCreate,
    OverrideRead,
    PrayerDayPlanRead,
    PrayerPlanRead,
    QueueRead,
    ScoringParameterVersionsResponse,
    ScoringSettingsRead,
    ScoringSettingsUpdateRequest,
    SelectionLogRead,
    SelectionLogResponse,
    SelectionRead,
    SelectionRequest,
)
from app.schemas.imperium import CompleteMissionRequest
from app.services.daily import constraints, day_flow, overrides, prayers, scoring_settings, selection
from app.services.imperium import missions
from app.services.path.fasting import paris_today
from app.services.travel import LatLng

router = APIRouter()

_ERROR_STATUS = {"SCORING_PARAMETER_UNKNOWN": status.HTTP_422_UNPROCESSABLE_ENTITY,
                 "SCORING_INVALID": status.HTTP_422_UNPROCESSABLE_ENTITY}


def _disabled() -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                        content={"detail": "Scoring settings are not enabled.", "code": "DAILY_SETTINGS_DISABLED"})


def _error(exc: scoring_settings.ScoringSettingsError) -> JSONResponse:
    return JSONResponse(status_code=_ERROR_STATUS.get(exc.code, status.HTTP_409_CONFLICT),
                        content={"detail": str(exc), "code": exc.code})


@router.get("/settings/scoring", response_model=ScoringSettingsRead)
def scoring_settings_route(current_user: CurrentUserDep, db: SessionDep) -> ScoringSettingsRead | JSONResponse:
    if not scoring_settings.settings_enabled(db):
        return _disabled()
    return scoring_settings.read_settings(db)


@router.get("/settings/scoring/{code}/versions", response_model=ScoringParameterVersionsResponse)
def scoring_versions_route(
    code: str, current_user: CurrentUserDep, db: SessionDep
) -> ScoringParameterVersionsResponse | JSONResponse:
    """Historique d'un barème : l'ancienne version reste interrogeable."""
    if not scoring_settings.settings_enabled(db):
        return _disabled()
    try:
        return ScoringParameterVersionsResponse(versions=scoring_settings.list_versions(db, code=code))
    except scoring_settings.ScoringSettingsError as exc:
        return _error(exc)


@router.put("/settings/scoring", response_model=ScoringSettingsRead)
def update_scoring_settings_route(
    payload: ScoringSettingsUpdateRequest,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ScoringSettingsRead | JSONResponse:
    """Nouvelle version de chaque barème changé, raison obligatoire, event `decision.scoring.updated`."""
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    if not scoring_settings.settings_enabled(db):
        return _disabled()
    try:
        return scoring_settings.update_settings(db, current_user=current_user, request=payload,
                                                idempotency_key=idempotency_key, request_path=request.url.path)
    except scoring_settings.ScoringSettingsError as exc:
        db.rollback()
        return _error(exc)


def _selection_disabled() -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                        content={"detail": "Daily selection is not enabled.", "code": "DAILY_SELECTION_DISABLED"})


def _coded(status_code: int, exc: Exception, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": str(exc), "code": code})


_CONSTRAINT_STATUS = {"MISSION_NOT_FOUND": status.HTTP_404_NOT_FOUND, "DEPENDENCY_EXISTS": status.HTTP_409_CONFLICT,
                      "MISSION_CLOSED": status.HTTP_409_CONFLICT}


@router.post("/complete/{mission_id}", response_model=DailyCompleteResponse)
def complete_route(
    mission_id: UUID,
    payload: CompleteMissionRequest,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DailyCompleteResponse | JSONResponse:
    """Le chemin nominal : clôt la mission active puis propose la suivante (jamais démarrée ici)."""
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    if not selection.selection_enabled(db):
        return _selection_disabled()
    try:
        completion, duplicate = missions.complete_mission(
            db, current_user=current_user, mission_id=mission_id, payload=payload, idempotency_key=idempotency_key,
            request_method=request.method, request_path=request.url.path,
        )
    except missions.MissionNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except missions.AnnexValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except (missions.MissionStateConflictError, missions.IdempotencyConflictError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Mission or event conflicts with an existing record.") from exc
    row = selection.last_for_trigger(db, current_user=current_user, trigger="mission_completed",
                                     trigger_ref=mission_id) if duplicate else None
    if row is None:
        mission = db.get(ImperiumMission, mission_id)
        origin = LatLng(float(mission.location_lat), float(mission.location_lng)) \
            if mission.location_lat is not None else None
        cause = db.get(Event, mission.ended_by_event_id) if mission.ended_by_event_id else None
        try:
            row = selection.select_next(db, current_user=current_user, trigger="mission_completed",
                                        trigger_ref=mission_id, origin=origin, causation_event=cause)
        except selection.SelectionError:
            db.rollback()
            return DailyCompleteResponse(completion=completion, selection=None)
        db.commit()
    return DailyCompleteResponse(completion=completion, selection=selection.to_read(db, row))


@router.post("/next", response_model=SelectionRead)
def next_route(payload: SelectionRequest, current_user: CurrentUserDep, db: SessionDep) -> SelectionRead | JSONResponse:
    """Déclenchement manuel (aucune mission active) ; la position sert au départage par trajet."""
    if not selection.selection_enabled(db):
        return _selection_disabled()
    origin = LatLng(payload.position.lat, payload.position.lng) if payload.position else None
    try:
        row = selection.select_next(db, current_user=current_user, trigger="manual", origin=origin)
    except selection.SelectionError as exc:
        db.rollback()
        return _coded(status.HTTP_409_CONFLICT, exc, exc.code)
    db.commit()
    return selection.to_read(db, row)


@router.get("/prayers", response_model=PrayerDayPlanRead)
def prayers_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    day: Annotated[date | None, Query(alias="date")] = None,
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
) -> PrayerDayPlanRead | JSONResponse:
    """Plan des prières du jour : mosquée retenue, départ et bloc, depuis le lieu de la mission précédente
    (sinon la position donnée). Lecture seule ; aucune mission n'est créée."""
    if not prayers.enabled(db):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"detail": "Prayer commitments are not enabled.", "code": "DAILY_PRAYERS_DISABLED"})
    if (lat is None) != (lng is None):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="lat and lng go together.")
    day = day or paris_today()
    origin = LatLng(lat, lng) if lat is not None else None
    plans = prayers.day_plan(db, user=current_user, day=day, origin=origin)
    return PrayerDayPlanRead(date=day, items=[PrayerPlanRead(**plan.__dict__) for plan in plans])


@router.get("/current", response_model=DailyCurrentRead)
def current_route(current_user: CurrentUserDep, db: SessionDep) -> DailyCurrentRead | JSONResponse:
    if not selection.selection_enabled(db):
        return _selection_disabled()
    return selection.current(db, current_user=current_user)


@router.get("/selection-log", response_model=SelectionLogResponse)
def selection_log_route(
    current_user: CurrentUserDep, db: SessionDep, day: Annotated[date, Query(alias="date")]
) -> SelectionLogResponse | JSONResponse:
    """Chaque choix du jour (Paris) rejouable : portes passées, porte bloquante, bande, trajets."""
    if not selection.selection_enabled(db):
        return _selection_disabled()
    rows = selection.selection_log(db, current_user=current_user, day=day)
    return SelectionLogResponse(date=day, entries=[SelectionLogRead.model_validate(row) for row in rows])


@router.get("/queue", response_model=QueueRead)
def queue_route(current_user: CurrentUserDep, db: SessionDep) -> QueueRead | JSONResponse:
    """Admin/debug uniquement : la file reste invisible dans le produit (décision UX gravée)."""
    if not selection.selection_enabled(db):
        return _selection_disabled()
    if not selection.queue_debug_enabled(db):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"detail": "The debug queue is not enabled.", "code": "DAILY_QUEUE_DISABLED"})
    return selection.queue(db, current_user=current_user)


@router.put("/missions/{mission_id}/constraints", response_model=MissionConstraints)
def constraints_route(
    mission_id: UUID, payload: MissionConstraints, current_user: CurrentUserDep, db: SessionDep
) -> MissionConstraints | JSONResponse:
    """Lieu, fenêtre, engagement fixe et charges : remplacés en entier."""
    if not selection.selection_enabled(db):
        return _selection_disabled()
    try:
        return constraints.update_constraints(db, current_user=current_user, mission_id=mission_id, payload=payload)
    except constraints.ConstraintsError as exc:
        db.rollback()
        return _coded(_CONSTRAINT_STATUS.get(exc.code, status.HTTP_422_UNPROCESSABLE_ENTITY), exc, exc.code)


@router.post("/dependencies", response_model=MissionDependencyRead, status_code=status.HTTP_201_CREATED)
def dependency_route(
    payload: MissionDependencyCreate, current_user: CurrentUserDep, db: SessionDep
) -> MissionDependencyRead | JSONResponse:
    """Arête parent → enfant ; 422 DEPENDENCY_CYCLE si elle ferme un cycle."""
    if not selection.selection_enabled(db):
        return _selection_disabled()
    try:
        return MissionDependencyRead.model_validate(
            constraints.add_dependency(db, current_user=current_user, payload=payload))
    except constraints.ConstraintsError as exc:
        db.rollback()
        return _coded(_CONSTRAINT_STATUS.get(exc.code, status.HTTP_422_UNPROCESSABLE_ENTITY), exc, exc.code)


@router.get("/missions/{mission_id}/dependencies", response_model=list[MissionDependencyRead])
def dependencies_route(
    mission_id: UUID, current_user: CurrentUserDep, db: SessionDep
) -> list[MissionDependencyRead] | JSONResponse:
    if not selection.selection_enabled(db):
        return _selection_disabled()
    try:
        rows = constraints.list_dependencies(db, current_user=current_user, mission_id=mission_id)
    except constraints.ConstraintsError as exc:
        return _coded(status.HTTP_404_NOT_FOUND, exc, exc.code)
    return [MissionDependencyRead.model_validate(row) for row in rows]


_OVERRIDE_STATUS = {"OVERRIDE_REASON_REQUIRED": status.HTTP_400_BAD_REQUEST,
                    "SELECTION_NOT_FOUND": status.HTTP_404_NOT_FOUND, "MISSION_NOT_FOUND": status.HTTP_404_NOT_FOUND,
                    "OVERRIDE_SAME_MISSION": status.HTTP_422_UNPROCESSABLE_ENTITY}


@router.post("/override", response_model=OverrideRead, status_code=status.HTTP_201_CREATED)
def override_route(payload: OverrideCreate, current_user: CurrentUserDep, db: SessionDep) -> OverrideRead | JSONResponse:
    """L'utilisateur prend une autre mission que la proposée : raison obligatoire, contexte figé, rien ne démarre."""
    if not overrides.override_enabled(db):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"detail": "Overrides are not enabled.", "code": "DAILY_OVERRIDE_DISABLED"})
    try:
        return OverrideRead.model_validate(overrides.record(db, current_user=current_user, payload=payload))
    except overrides.OverrideError as exc:
        db.rollback()
        return _coded(_OVERRIDE_STATUS.get(exc.code, status.HTTP_409_CONFLICT), exc, exc.code)


_DAY_FLOW_STATUS = {"MISSION_NOT_FOUND": status.HTTP_404_NOT_FOUND, "MISSION_NOT_AVAILABLE": status.HTTP_404_NOT_FOUND,
                    "BAD_BUSY_UNTIL": status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "REPLAN_COOLDOWN": status.HTTP_429_TOO_MANY_REQUESTS}


@router.post("/start/{mission_id}", response_model=DailyCurrentRead)
def start_route(
    mission_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DailyCurrentRead | JSONResponse:
    """Démarre la mission proposée (ou une autre en attente) : active, heures prévues = maintenant + durée."""
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    if not selection.selection_enabled(db):
        return _selection_disabled()
    try:
        day_flow.start_mission(db, current_user=current_user, mission_id=mission_id, idempotency_key=idempotency_key)
    except day_flow.DayFlowError as exc:
        db.rollback()
        return _coded(_DAY_FLOW_STATUS.get(exc.code, status.HTTP_409_CONFLICT), exc, exc.code)
    return selection.current(db, current_user=current_user)


@router.get("/programme", response_model=ProgrammeRead)
def programme_route(current_user: CurrentUserDep, db: SessionDep) -> ProgrammeRead | JSONResponse:
    """Programme du jour : fait, en cours, puis la proposition suivante (jamais la file)."""
    if not selection.selection_enabled(db):
        return _selection_disabled()
    return day_flow.programme(db, current_user=current_user)


@router.post("/replan", response_model=DayReplanRead)
def replan_route(
    payload: DayReplanRequest,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DayReplanRead | JSONResponse:
    """Replanifier la journée : une raison claire, puis la suite recalculée par la sélection (rien ne démarre)."""
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    if not selection.selection_enabled(db):
        return _selection_disabled()
    try:
        return day_flow.replan(db, current_user=current_user, payload=payload, idempotency_key=idempotency_key)
    except day_flow.DayFlowError as exc:
        db.rollback()
        return _coded(_DAY_FLOW_STATUS.get(exc.code, status.HTTP_409_CONFLICT), exc, exc.code)
    except selection.SelectionError as exc:
        db.rollback()
        return _coded(status.HTTP_409_CONFLICT, exc, exc.code)
