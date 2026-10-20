"""Board Pulse et signalements subjectifs (spec Pulse §3.1, §14 ; cartes ACT-PLS-08, ACT-PLS-05)."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.pulse_health import DeletedCountRead
from app.schemas.pulse_signals import (
    BoardRead,
    SubjectiveReportCreate,
    SubjectiveReportListResponse,
    SubjectiveReportRead,
)
from app.services.path.fasting import paris_today
from app.services.pulse import signals

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
