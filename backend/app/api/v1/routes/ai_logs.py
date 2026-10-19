"""Routes du navigateur des logs de l'IA (doc 72 §8) et du journal des appels (doc 43 §17) — lecture seule."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUserDep, SessionDep
from app.services.ai import call_alerts, call_log
from app.services.ai import logs as ai_logs

router = APIRouter()


@router.get("/logs", response_model=ai_logs.AILogListResponse)
def list_ai_logs_route(current_user: CurrentUserDep, db: SessionDep) -> ai_logs.AILogListResponse:
    return ai_logs.list_logs(db, current_user=current_user)


@router.get("/call-logs", response_model=call_log.AICallLogListResponse)
def list_ai_call_logs_route(
    current_user: CurrentUserDep, db: SessionDep, limit: Annotated[int, Query(ge=1, le=500)] = 100
) -> call_log.AICallLogListResponse:
    """Journal central des appels de modèles (doc 43 §17) : métadonnées seulement, jamais le contenu."""
    return call_log.list_calls(db, limit=limit)


@router.get("/call-logs/daily", response_model=call_log.AIDailySpendResponse)
def ai_daily_spend_route(
    current_user: CurrentUserDep, db: SessionDep, days: Annotated[int, Query(ge=1, le=90)] = 30
) -> call_log.AIDailySpendResponse:
    """Appels et dépense par jour (vue ai_daily_spend, jour Europe/Paris)."""
    return call_log.daily_spend(db, days=days)


@router.get("/call-logs/alerts", response_model=call_log.AICallAlertsResponse)
def ai_call_alerts_route(current_user: CurrentUserDep, db: SessionDep) -> call_log.AICallAlertsResponse:
    """Seuils du doc 43 §17.6 franchis maintenant (lecture seule, aucune notification)."""
    return call_log.AICallAlertsResponse(
        alerts=[call_log.AICallAlertRead(**alert.__dict__) for alert in call_alerts.evaluate(db)]
    )


@router.get("/logs/{log_id}", response_model=ai_logs.AILogRead)
def read_ai_log_route(log_id: str, current_user: CurrentUserDep, db: SessionDep) -> ai_logs.AILogRead:
    try:
        return ai_logs.read_log(db, current_user=current_user, log_id=log_id)
    except ai_logs.AILogNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
