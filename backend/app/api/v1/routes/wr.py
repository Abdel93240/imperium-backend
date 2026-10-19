"""Docket du WR (spec WR §12) : `GET docket`, `GET docket/red`, `POST docket/{id}/decision`."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.wr import DocketDecisionRequest, DocketItemRead, DocketItemType, DocketListResponse, DocketStatus
from app.services.wr import docket

router = APIRouter()


@router.get("/docket", response_model=DocketListResponse)
def docket_route(
    current_user: CurrentUserDep,
    db: SessionDep,
    status_filter: Annotated[DocketStatus | None, Query(alias="status")] = None,
    item_type: Annotated[DocketItemType | None, Query(alias="type")] = None,
) -> DocketListResponse:
    """Items triés : décisions forcées en tête, puis priorité à l'instant."""
    return DocketListResponse(
        items=docket.list_items(db, current_user=current_user, status=status_filter, item_type=item_type)
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
