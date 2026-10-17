"""Routes du navigateur des logs de l'IA (doc 72 §8) — lecture seule."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUserDep, SessionDep
from app.services.ai import logs as ai_logs

router = APIRouter()


@router.get("/logs", response_model=ai_logs.AILogListResponse)
def list_ai_logs_route(current_user: CurrentUserDep, db: SessionDep) -> ai_logs.AILogListResponse:
    return ai_logs.list_logs(db, current_user=current_user)


@router.get("/logs/{log_id}", response_model=ai_logs.AILogRead)
def read_ai_log_route(log_id: str, current_user: CurrentUserDep, db: SessionDep) -> ai_logs.AILogRead:
    try:
        return ai_logs.read_log(db, current_user=current_user, log_id=log_id)
    except ai_logs.AILogNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
