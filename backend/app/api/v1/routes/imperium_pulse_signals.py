"""Board Pulse, signalements subjectifs et journal de la sentinelle (spec Pulse §3.1, §3.2, §14 ;
cartes ACT-PLS-08, ACT-PLS-05, ACT-PLS-10/13/15)."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.pulse_health import DeletedCountRead
from app.schemas.pulse_signals import (
    BoardRead,
    DispatchListResponse,
    DispatchRead,
    DispatchReactionRequest,
    SubjectiveReportCreate,
    SubjectiveReportListResponse,
    SubjectiveReportRead,
)
from app.services.path.fasting import paris_today
from app.services.pulse import sentinel, signals

router = APIRouter()


def _disabled(code: str) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": "Disabled.", "code": code})


@router.get("/board", response_model=BoardRead)
def board_route(current_user: CurrentUserDep, db: SessionDep):
    """Tableau courant : red flags ouverts, puis dernière valeur de chaque signal actif (lecture seule)."""
    if not signals.board_enabled(db):
        return _disabled("PULSE_BOARD_DISABLED")
    return signals.board(db, current_user=current_user)


@router.post("/reports", response_model=SubjectiveReportRead, status_code=status.HTTP_201_CREATED)
def create_report_route(
    payload: SubjectiveReportCreate,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if not signals.reports_enabled(db):
        return _disabled("PULSE_REPORTS_DISABLED")
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    try:
        report, replayed = signals.create_report(db, current_user=current_user, payload=payload,
                                                 idempotency_key=idempotency_key)
    except signals.ReportIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except signals.ReportInFutureError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if replayed:
        response.status_code = status.HTTP_200_OK
    return report


@router.get("/reports", response_model=SubjectiveReportListResponse)
def list_reports_route(current_user: CurrentUserDep, db: SessionDep, day: date | None = None):
    day = day or paris_today()
    listing = signals.list_reports(db, current_user=current_user, day=day)
    listing.day = day
    return listing


@router.delete("/reports", response_model=DeletedCountRead)
def delete_all_reports_route(current_user: CurrentUserDep, db: SessionDep):
    """Suppression réelle, toujours possible (même flag éteint)."""
    return DeletedCountRead(deleted=signals.delete_all_reports(db, current_user=current_user))


@router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report_route(report_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> Response:
    try:
        signals.delete_report(db, current_user=current_user, report_id=report_id)
    except signals.ReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/sentinel/dispatches", response_model=DispatchListResponse)
def list_dispatches_route(current_user: CurrentUserDep, db: SessionDep, limit: int = Query(default=50, ge=1, le=200)):
    """Réveils de la sentinelle, du plus récent au plus ancien (lecture seule, rien n'y est proposé)."""
    if not signals.board_enabled(db):
        return _disabled("PULSE_BOARD_DISABLED")
    return sentinel.list_dispatches(db, current_user=current_user, limit=limit)


@router.post("/sentinel/dispatches/{dispatch_id}/reaction", response_model=DispatchRead)
def react_route(dispatch_id: UUID, payload: DispatchReactionRequest, current_user: CurrentUserDep, db: SessionDep):
    if not signals.board_enabled(db):
        return _disabled("PULSE_BOARD_DISABLED")
    try:
        return sentinel.react(db, current_user=current_user, dispatch_id=dispatch_id, reaction=payload.reaction)
    except sentinel.DispatchNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/sentinel/history", response_model=DeletedCountRead)
def forget_history_route(current_user: CurrentUserDep, db: SessionDep):
    """Suppression réelle des réveils et boards figés, toujours possible (même flag éteint)."""
    return DeletedCountRead(deleted=sentinel.forget_history(db, current_user=current_user))
