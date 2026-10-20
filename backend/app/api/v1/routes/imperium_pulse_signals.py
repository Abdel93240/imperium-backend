"""Board Pulse, signalements subjectifs et journal de la sentinelle (spec Pulse §3.1, §3.2, §14 ;
cartes ACT-PLS-08, ACT-PLS-05, ACT-PLS-10/13/15, ACT-PLS-27 ; propositions §3.3)."""

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
    MetricsSummaryRead,
    ProposalDecisionRequest,
    ProposalListResponse,
    ProposalRead,
    SubjectiveReportCreate,
    SubjectiveReportListResponse,
    SubjectiveReportRead,
)
from app.services.path.fasting import paris_today
from app.services.pulse import metrics, procedures, sentinel, signals

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


@router.get("/metrics/summary", response_model=MetricsSummaryRead)
def metrics_summary_route(current_user: CurrentUserDep, db: SessionDep, days: int = Query(default=7, ge=1, le=90)):
    """Jours clos enregistrés, aujourd'hui à la volée et état d'audit des slots Pulse (lecture seule)."""
    if not signals.board_enabled(db):
        return _disabled("PULSE_BOARD_DISABLED")
    return metrics.summary(db, current_user=current_user, days=days)


@router.get("/proposals", response_model=ProposalListResponse)
def list_proposals_route(current_user: CurrentUserDep, db: SessionDep):
    """Propositions présentées en attente de décision (jamais celles d'un essai à blanc)."""
    if not procedures.proposals_enabled(db):
        return _disabled("PULSE_PROPOSALS_DISABLED")
    return procedures.list_pending(db, current_user=current_user)


@router.post("/proposals/{proposal_id}/decision", response_model=ProposalRead)
def decide_route(proposal_id: UUID, payload: ProposalDecisionRequest, current_user: CurrentUserDep, db: SessionDep):
    """Seule voie d'application d'un effet : accepter ou modifier (coup revalidé) ; refuser sans rien changer."""
    if not procedures.proposals_enabled(db):
        return _disabled("PULSE_PROPOSALS_DISABLED")
    try:
        return procedures.decide(db, current_user=current_user, proposal_id=proposal_id, payload=payload)
    except procedures.ProposalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except procedures.ProposalStateError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except procedures.ProposalStaleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail={"code": "PROPOSAL_STALE", "message": str(exc)}) from exc
