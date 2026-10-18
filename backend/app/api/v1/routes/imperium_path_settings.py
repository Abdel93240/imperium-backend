"""Path : réglages du calcul local des horaires (PAT-11, doc 41 §6.4)."""

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.path_settings import PathSettingsRead, PathSettingsUpdate
from app.services.path import settings
from app.services.pulse import food_stock

router = APIRouter()


@router.get("/settings", response_model=PathSettingsRead)
def path_settings_route(current_user: CurrentUserDep, db: SessionDep) -> PathSettingsRead:
    """Méthode, madhhab et ville en vigueur, lieu et source actuels des horaires."""
    return settings.get_settings(db, current_user=current_user)


@router.patch("/settings", response_model=PathSettingsRead)
def update_path_settings_route(
    payload: PathSettingsUpdate,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Version lue obligatoire (0 avant le premier enregistrement) ; `city: null` revient à Paris."""
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    try:
        return settings.update_settings(db, current_user=current_user, payload=payload,
                                        idempotency_key=idempotency_key, request_path=request.url.path)
    except settings.PathSettingsVersionConflictError as exc:
        db.rollback()
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={
            "detail": str(exc), "code": "PATH_SETTINGS_VERSION_CONFLICT", "current": exc.current.model_dump(mode="json"),
        })
    except food_stock.FoodStockIdempotencyConflictError as exc:
        db.rollback()
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})
