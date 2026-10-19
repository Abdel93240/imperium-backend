"""Daily (spec Daily §12) : `GET/PUT settings/scoring`, `GET settings/scoring/{code}/versions`.

Servis seulement si `daily.settings_enabled` (semé false, carte ACT-DLY-02) : 409 DAILY_SETTINGS_DISABLED sinon.
"""

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.daily import ScoringParameterVersionsResponse, ScoringSettingsRead, ScoringSettingsUpdateRequest
from app.services.daily import scoring_settings

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
