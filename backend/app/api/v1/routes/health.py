from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import CurrentUserDep, SessionDep
from app.core.config import get_settings
from app.services.service_health import ServiceHealthReport, check_services, default_probes

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
def database_health_check(db: SessionDep) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database health check failed.",
        ) from exc
    return {"status": "ok"}


@router.get("/health/services", response_model=ServiceHealthReport)
def services_health_check(current_user: CurrentUserDep, db: SessionDep) -> ServiceHealthReport:
    """État détaillé des services (écran « Connexion à Imperium ») ; réservé à l'utilisateur connecté."""
    settings = get_settings()
    return check_services(settings=settings, probes=default_probes(db, settings))
