"""Path : sadaqa (doc 41 §9) — réglages PAT-11d, objectif de la semaine, dons PAT-03."""

from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.path_sadaqa import (
    SadaqaDonationCreate,
    SadaqaDonationDeleteResult,
    SadaqaDonationListResponse,
    SadaqaDonationRead,
    SadaqaDonationResult,
    SadaqaSettingsRead,
    SadaqaSettingsUpdate,
    SadaqaWeekRead,
)
from app.services.path import fasting, sadaqa
from app.services.pulse import food_stock

router = APIRouter()


def _require_key(idempotency_key: str | None) -> str:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    return idempotency_key


def _error(db: SessionDep, exc: Exception) -> JSONResponse:
    db.rollback()
    if isinstance(exc, sadaqa.SadaqaSettingsConflictError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc), "code": "SADAQA_SETTINGS_CONFLICT", "current": exc.current.model_dump(mode="json")},
        )
    if isinstance(exc, sadaqa.SadaqaSecondChangeError):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc), "code": "SADAQA_SECOND_CHANGE"})
    if isinstance(exc, sadaqa.SadaqaVaultUnavailableError):
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": str(exc), "code": "VAULT_PENDING"})
    codes = {
        sadaqa.SadaqaNotFoundError: status.HTTP_404_NOT_FOUND,
        sadaqa.SadaqaInputError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    }
    return JSONResponse(status_code=codes.get(type(exc), status.HTTP_409_CONFLICT), content={"detail": str(exc)})


_ERRORS = (
    sadaqa.SadaqaInputError,
    sadaqa.SadaqaNotFoundError,
    sadaqa.SadaqaStateError,
    sadaqa.SadaqaIdempotencyConflictError,
    sadaqa.SadaqaVaultUnavailableError,
    sadaqa.SadaqaSecondChangeError,
    sadaqa.SadaqaSettingsConflictError,
    food_stock.FoodStockIdempotencyConflictError,
)


@router.get("/sadaqa/settings", response_model=SadaqaSettingsRead)
def sadaqa_settings_route(current_user: CurrentUserDep, db: SessionDep) -> SadaqaSettingsRead:
    """Pourcentage et marge en vigueur cette semaine, changement à venir ; lu aussi par le Vault (VAU-12)."""
    return sadaqa.get_settings(db, current_user=current_user)


@router.patch("/sadaqa/settings", response_model=SadaqaSettingsRead)
def update_sadaqa_settings_route(
    payload: SadaqaSettingsUpdate,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Vaut à partir de lundi prochain par défaut ; un deuxième changement dans la semaine demande confirmation."""
    try:
        read, _ = sadaqa.update_settings(
            db, current_user=current_user, payload=payload, idempotency_key=_require_key(idempotency_key),
            request_path=request.url.path,
        )
    except _ERRORS as exc:
        return _error(db, exc)
    return read


@router.get("/sadaqa/summary", response_model=SadaqaWeekRead)
def sadaqa_summary_route(current_user: CurrentUserDep, db: SessionDep, week_start: date | None = None):
    """Objectif de la semaine (lundi de Paris ; semaine en cours par défaut) : base, report, dons, reste."""
    try:
        return sadaqa.week_summary(db, current_user=current_user, week_start=week_start)
    except _ERRORS as exc:
        return _error(db, exc)


@router.get("/sadaqa/donations", response_model=SadaqaDonationListResponse)
def list_donations_route(current_user: CurrentUserDep, db: SessionDep, from_day: date | None = None, to_day: date | None = None):
    """Dons sur des jours de Paris (par défaut : les 90 derniers jours)."""
    end = to_day or fasting.paris_today()
    try:
        return sadaqa.list_donations(db, current_user=current_user, from_day=from_day or end - timedelta(days=89), to_day=end)
    except _ERRORS as exc:
        return _error(db, exc)


@router.post("/sadaqa/donations", response_model=SadaqaDonationResult, status_code=status.HTTP_201_CREATED)
def create_donation_route(
    payload: SadaqaDonationCreate,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Don déclaré ; dépense « sadaqa » écrite au Vault ensuite (en attente si l'écriture échoue)."""
    try:
        result, duplicate = sadaqa.create_donation(
            db, current_user=current_user, payload=payload, idempotency_key=_require_key(idempotency_key)
        )
    except _ERRORS as exc:
        return _error(db, exc)
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post("/sadaqa/donations/{donation_id}/vault-retry", response_model=SadaqaDonationRead)
def retry_vault_route(donation_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    """Nouvelle tentative d'écriture au Vault (même clé : jamais de doublon)."""
    try:
        return sadaqa.retry_vault(db, current_user=current_user, donation_id=donation_id)
    except _ERRORS as exc:
        return _error(db, exc)


@router.delete("/sadaqa/donations/{donation_id}", response_model=SadaqaDonationDeleteResult)
def delete_donation_route(donation_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    """Suppression réelle du don ; la dépense Vault est annulée par une écriture inverse."""
    try:
        return sadaqa.delete_donation(db, current_user=current_user, donation_id=donation_id)
    except _ERRORS as exc:
        return _error(db, exc)
