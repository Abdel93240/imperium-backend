"""Docket et digest du WR (spec WR §12) : `GET docket`, `GET docket/red`, `POST docket/{id}/decision`,
`POST docket/{id}/red-ack`,
`POST digest`, `GET digest/current`, `GET metrics/weekly`, `GET plan/current`, `GET plan/versions`,
`POST plan/initial`, `POST plan/shock`, `POST plan/versions/{id}/activate|supersede`."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.wr import (
    AutoacceptClassCreateRequest,
    AutoacceptClassListResponse,
    AutoacceptClassRead,
    DigestRead,
    DocketDecisionRequest,
    DocketItemRead,
    DocketItemType,
    DocketListResponse,
    DocketStatus,
    PlanCurrentRead,
    PlanInitialRequest,
    PlanShockRequest,
    PlanSupersedeRequest,
    PlanVersionListResponse,
    PlanVersionRead,
    RedAckRead,
    SlotAuditStateRead,
    SlotAuditStatesResponse,
    SlotTransitionUpdateRequest,
    WalkNextResponse,
    WalkRead,
    WalkStartRequest,
    WrMetricsWeekRead,
    WrMetricsWeeklyResponse,
)
from app.services.ai import audit_loop
from app.services.wr import autoaccept, digest, docket, metrics, plan, walker

router = APIRouter()


@router.get("/docket", response_model=DocketListResponse)
def docket_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    status_filter: Annotated[DocketStatus | None, Query(alias="status")] = None,
    item_type: Annotated[DocketItemType | None, Query(alias="type")] = None,
    mode: Literal["full", "light"] = "full",
) -> DocketListResponse:
    """Items triés : décisions forcées en tête, puis priorité à l'instant ; `light` = WR court (§9 P4)."""
    return DocketListResponse(
        items=docket.list_items(db, current_user=current_user, status=status_filter, item_type=item_type, mode=mode)
    )


@router.get("/docket/red", response_model=DocketListResponse)
def docket_red_route(current_user: CurrentUserDep, db: SessionDep) -> DocketListResponse:
    """Items rouges encore ouverts : à trancher sans attendre le rituel."""
    return DocketListResponse(items=docket.list_items(db, current_user=current_user, red_only=True))


@router.post("/docket/{item_id}/decision", response_model=DocketItemRead)
def docket_decision_route(
    item_id: UUID,
    payload: DocketDecisionRequest,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DocketItemRead | JSONResponse:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    try:
        return docket.decide(
            db, current_user=current_user, item_id=item_id, request=payload,
            idempotency_key=idempotency_key, request_path=request.url.path,
        )
    except docket.DocketItemNotFoundError as exc:
        db.rollback()
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})
    except docket.DocketStateError as exc:
        db.rollback()
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc), "code": exc.code})
    except docket.DocketIdempotencyConflictError as exc:
        db.rollback()
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


@router.post("/docket/{item_id}/red-ack", response_model=RedAckRead)
def docket_red_ack_route(item_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> RedAckRead | JSONResponse:
    """Accusé de réception d'un rouge notifié (idempotent) : ne décide pas l'item."""
    try:
        return docket.red_ack(db, current_user=current_user, item_id=item_id)
    except docket.DocketItemNotFoundError as exc:
        db.rollback()
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})
    except docket.DocketStateError as exc:
        db.rollback()
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc), "code": exc.code})


@router.post("/digest", response_model=DigestRead, status_code=status.HTTP_201_CREATED)
def assemble_digest_route(current_user: CurrentUserDep, db: SessionDep) -> DigestRead | JSONResponse:
    """Assemble le digest de la session WR ouverte (201) ; déjà figé, il est rendu tel quel (200)."""
    try:
        row, created = digest.assemble_digest(db, current_user=current_user)
    except digest.DigestStateError as exc:
        db.rollback()
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc), "code": exc.code})
    except digest.DigestWhitelistError as exc:
        db.rollback()
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": str(exc), "code": "DIGEST_WHITELIST"})
    read = DigestRead.model_validate(row)
    if created:
        return read
    return JSONResponse(status_code=status.HTTP_200_OK, content=read.model_dump(mode="json"))


@router.get("/digest/current", response_model=DigestRead)
def current_digest_route(current_user: CurrentUserDep, db: SessionDep) -> DigestRead:
    row = digest.current_digest(db, current_user=current_user)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No digest for the open weekly review.")
    return DigestRead.model_validate(row)


@router.get("/metrics/weekly", response_model=WrMetricsWeeklyResponse)
def weekly_metrics_route(
    current_user: CurrentUserDep, db: SessionDep, weeks: Annotated[int, Query(ge=1, le=12)] = 4
) -> WrMetricsWeeklyResponse:
    """Dernières semaines, en cours comprise, calculées à l'instant (lecture seule)."""
    rows = metrics.recent_weeks(db, current_user=current_user, weeks=weeks)
    return WrMetricsWeeklyResponse(weeks=[WrMetricsWeekRead.model_validate(row) for row in rows])


@router.get("/admin/transition", response_model=SlotAuditStatesResponse)
def slot_transition_states_route(current_user: CurrentUserDep, db: SessionDep) -> SlotAuditStatesResponse:
    """Slots IA, agreement des semaines closes et décroissance proposée (lecture seule)."""
    return SlotAuditStatesResponse(slots=audit_loop.slot_states(db))


@router.post("/admin/transition", response_model=SlotAuditStateRead)
def slot_transition_update_route(
    payload: SlotTransitionUpdateRequest,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> SlotAuditStateRead | JSONResponse:
    """Décision utilisateur : taux d'audit ou cible d'agreement d'un slot (jamais le tier)."""
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    try:
        return audit_loop.update_slot(
            db, current_user=current_user, request=payload,
            idempotency_key=idempotency_key, request_path=request.url.path,
        )
    except audit_loop.UnknownSlotError as exc:
        db.rollback()
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})
    except audit_loop.SlotIdempotencyConflictError as exc:
        db.rollback()
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


@router.get("/autoaccept-classes", response_model=AutoacceptClassListResponse)
def autoaccept_classes_route(current_user: CurrentUserDep, db: SessionDep) -> AutoacceptClassListResponse:
    """Classes d'auto-acceptation, agreement du slot à l'instant et bilan des contrôles (lecture seule)."""
    return AutoacceptClassListResponse(classes=autoaccept.list_classes(db, current_user=current_user))


@router.post("/autoaccept-classes", response_model=AutoacceptClassRead, status_code=status.HTTP_201_CREATED)
def create_autoaccept_class_route(
    payload: AutoacceptClassCreateRequest,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AutoacceptClassRead | JSONResponse:
    """Activation d'une classe : décision de l'utilisateur, raison obligatoire."""
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    try:
        return autoaccept.create_class(
            db, current_user=current_user, request=payload,
            idempotency_key=idempotency_key, request_path=request.url.path,
        )
    except audit_loop.UnknownSlotError as exc:
        db.rollback()
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})
    except autoaccept.AutoacceptStateError as exc:
        db.rollback()
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc), "code": exc.code})


@router.post("/autoaccept-classes/{class_id}/disable", response_model=AutoacceptClassRead)
def disable_autoaccept_class_route(class_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> AutoacceptClassRead:
    try:
        return autoaccept.disable_class(db, current_user=current_user, class_id=class_id)
    except autoaccept.AutoacceptClassNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _walk_conflict(exc: walker.WalkStateError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc), "code": exc.code})


@router.post("/walk", response_model=WalkRead, status_code=status.HTTP_201_CREATED)
def start_walk_route(payload: WalkStartRequest, current_user: CurrentUserDep, db: SessionDep) -> WalkRead | JSONResponse:
    """Démarre la marche du docket de la session WR ouverte (201) ; déjà démarrée, elle est rendue (200)."""
    try:
        walk, created = walker.start_walk(db, current_user=current_user, mode=payload.mode)
    except walker.WalkStateError as exc:
        db.rollback()
        return _walk_conflict(exc)
    read = WalkRead.model_validate(walk)
    if created:
        return read
    return JSONResponse(status_code=status.HTTP_200_OK, content=read.model_dump(mode="json"))


@router.get("/walk/next", response_model=WalkNextResponse)
def walk_next_route(current_user: CurrentUserDep, db: SessionDep) -> WalkNextResponse | JSONResponse:
    """Prochain item à trancher sous le budget du mode (lecture seule)."""
    try:
        return walker.next_item(db, current_user=current_user)
    except walker.WalkStateError as exc:
        return _walk_conflict(exc)


@router.post("/walk/close", response_model=WalkRead)
def close_walk_route(current_user: CurrentUserDep, db: SessionDep) -> WalkRead | JSONResponse:
    try:
        return WalkRead.model_validate(walker.close_walk(db, current_user=current_user))
    except walker.WalkStateError as exc:
        db.rollback()
        return _walk_conflict(exc)


def _plan_conflict(exc: plan.PlanStateError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc), "code": exc.code})


@router.get("/plan/current", response_model=PlanCurrentRead)
def current_plan_route(current_user: CurrentUserDep, db: SessionDep) -> PlanCurrentRead | JSONResponse:
    """v_plan_current : version active + deltas appliqués ; servi seulement si `wr.plan_enabled`."""
    if not plan.plan_enabled(db):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"detail": "The WR plan is not enabled.", "code": "PLAN_DISABLED"})
    current = plan.current_plan(db, current_user=current_user)
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active plan.")
    return current


@router.get("/plan/versions", response_model=PlanVersionListResponse)
def plan_versions_route(current_user: CurrentUserDep, db: SessionDep) -> PlanVersionListResponse:
    return PlanVersionListResponse(versions=plan.list_versions(db, current_user=current_user))


@router.post("/plan/initial", response_model=PlanVersionRead, status_code=status.HTTP_201_CREATED)
def create_initial_plan_route(
    payload: PlanInitialRequest,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PlanVersionRead | JSONResponse:
    """Plan initial saisi par l'utilisateur, créé `proposed` : il ne devient actif que par activate."""
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    try:
        return plan.create_initial(db, current_user=current_user, request=payload,
                                   idempotency_key=idempotency_key, request_path=request.url.path)
    except plan.PlanStateError as exc:
        db.rollback()
        return _plan_conflict(exc)


@router.post("/plan/shock", response_model=PlanVersionRead, status_code=status.HTTP_201_CREATED)
def plan_shock_route(
    payload: PlanShockRequest,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PlanVersionRead | JSONResponse:
    """Choc exogène : régénération complète proposée, jamais activée seule (`wr.plan_shock_enabled`)."""
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    if not (plan.plan_enabled(db) and plan.shock_enabled(db)):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"detail": "Shock regeneration is not enabled.", "code": "PLAN_SHOCK_DISABLED"})
    try:
        return plan.request_shock(db, current_user=current_user, request=payload,
                                  idempotency_key=idempotency_key, request_path=request.url.path)
    except plan.PlanShockReasonError as exc:
        db.rollback()
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            content={"detail": str(exc), "code": "SHOCK_REASON_UNKNOWN"})
    except plan.PlanStateError as exc:
        db.rollback()
        return _plan_conflict(exc)


@router.post("/plan/versions/{version_id}/activate", response_model=PlanVersionRead)
def activate_plan_route(version_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> PlanVersionRead | JSONResponse:
    try:
        return plan.activate(db, current_user=current_user, version_id=version_id)
    except plan.PlanVersionNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except plan.PlanStateError as exc:
        db.rollback()
        return _plan_conflict(exc)


@router.post("/plan/versions/{version_id}/supersede", response_model=PlanVersionRead)
def supersede_plan_route(
    version_id: UUID, payload: PlanSupersedeRequest, current_user: CurrentUserDep, db: SessionDep
) -> PlanVersionRead:
    """Retour arrière (jamais de DELETE) : la version passe superseded, raison obligatoire."""
    try:
        return plan.supersede(db, current_user=current_user, version_id=version_id, reason_fr=payload.reason_fr)
    except plan.PlanVersionNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
