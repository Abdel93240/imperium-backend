"""Docket et digest du WR (spec WR §12) : `GET docket`, `GET docket/red`, `POST docket/{id}/decision`,
`POST digest`, `GET digest/current`, `GET metrics/weekly`."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.wr import (
    DigestRead,
    DocketDecisionRequest,
    DocketItemRead,
    DocketItemType,
    DocketListResponse,
    DocketStatus,
    SlotAuditStateRead,
    SlotAuditStatesResponse,
    SlotTransitionUpdateRequest,
    WrMetricsWeekRead,
    WrMetricsWeeklyResponse,
)
from app.services.ai import audit_loop
from app.services.wr import digest, docket, metrics

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
