"""Hydratation Pulse (doc 40 §12) : appuis rapides PUL-04 et journée."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.pulse_hydration import HydrationDayRead, HydrationLogCreate, HydrationLogResult
from app.services.pulse import hydration
from app.services.pulse.expiry import paris_today

router = APIRouter()


@router.get("/hydration-logs", response_model=HydrationDayRead)
def hydration_day_route(current_user: CurrentUserDep, db: SessionDep, day: date | None = None) -> HydrationDayRead:
    """Eau bue sur le jour de Paris demandé (aujourd'hui par défaut)."""
    return hydration.day_view(db, current_user=current_user, day=day or paris_today())


@router.post("/hydration-logs", response_model=HydrationLogResult, status_code=status.HTTP_201_CREATED)
def log_hydration_route(
    payload: HydrationLogCreate,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Enregistre l'eau bue et la décompte du stock d'eau ; stock insuffisant → avertissement, jamais de blocage.

    Heure dans la fenêtre d'un jeûne (Path) sans eau permise de jour → 409 FASTING_HYDRATION_BLOCKED.
    """
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    try:
        result, duplicate = hydration.log_hydration(
            db, current_user=current_user, payload=payload, idempotency_key=idempotency_key
        )
    except hydration.HydrationFastingError as exc:
        db.rollback()
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc), "code": "FASTING_HYDRATION_BLOCKED"})
    except hydration.HydrationIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result
