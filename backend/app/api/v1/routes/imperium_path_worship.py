"""Path : prières marquées (PAT-02, doc 41 §7) et jeûne (PAT-05, doc 41 §8)."""

from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Path, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.path_worship import (
    FastBreakRequest,
    FastEndRequest,
    FastingStateRead,
    FastListResponse,
    FastRead,
    FastStartRequest,
    PrayerClearRequest,
    PrayerDayRead,
    PrayerMarkRequest,
    PrayerName,
    PrayerRead,
)
from app.services.path import fasting, prayer_marks
from app.services.pulse import food_stock

router = APIRouter()

PrayerSlug = Annotated[PrayerName, Path(description="fajr, dhuhr, asr, maghrib ou isha")]


def _require_key(idempotency_key: str | None) -> str:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    return idempotency_key


def _error(db: SessionDep, exc: Exception) -> JSONResponse:
    db.rollback()
    if isinstance(exc, prayer_marks.PrayerStatusConflictError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc), "code": "PRAYER_STATUS_CONFLICT", "current": exc.current.model_dump(mode="json")},
        )
    if isinstance(exc, fasting.FastStateError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc), "code": "FAST_STATE_CONFLICT",
                     "current": exc.current.model_dump(mode="json") if exc.current else None},
        )
    if isinstance(exc, prayer_marks.PrayerNotFoundError | fasting.FastNotFoundError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, prayer_marks.PrayerInputError | fasting.FastInputError):
        code = status.HTTP_422_UNPROCESSABLE_ENTITY
    elif isinstance(exc, IntegrityError):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": "Écriture concurrente : relis puis réessaie."})
    else:
        code = status.HTTP_409_CONFLICT
    return JSONResponse(status_code=code, content={"detail": str(exc)})


_ERRORS = (
    prayer_marks.PrayerInputError,
    prayer_marks.PrayerNotFoundError,
    prayer_marks.PrayerStatusConflictError,
    fasting.FastInputError,
    fasting.FastNotFoundError,
    fasting.FastStateError,
    fasting.FastIdempotencyConflictError,
    food_stock.FoodStockIdempotencyConflictError,
    IntegrityError,
)


@router.get("/prayers", response_model=PrayerDayRead)
def prayer_day_route(current_user: CurrentUserDep, db: SessionDep, day: date | None = None) -> PrayerDayRead:
    """Les cinq prières du jour de Paris : heure (MAWAQIT puis calcul) et statut posé par l'utilisateur."""
    return prayer_marks.day_view(db, current_user=current_user, day=day or fasting.paris_today())


@router.post("/prayers/{prayer_name}/mark", response_model=PrayerRead)
def mark_prayer_route(
    prayer_name: PrayerSlug,
    payload: PrayerMarkRequest,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Accomplie ou « non marquée comme accomplie » ; changer un statut posé demande `base_version`."""
    try:
        read, _ = prayer_marks.mark_prayer(
            db, current_user=current_user, prayer_name=prayer_name, payload=payload,
            idempotency_key=_require_key(idempotency_key), request_path=request.url.path,
        )
    except _ERRORS as exc:
        return _error(db, exc)
    return read


@router.post("/prayers/{prayer_name}/clear", response_model=PrayerRead)
def clear_prayer_route(
    prayer_name: PrayerSlug,
    payload: PrayerClearRequest,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Efface le statut (la ligne est supprimée)."""
    try:
        read, _ = prayer_marks.clear_prayer(
            db, current_user=current_user, prayer_name=prayer_name, payload=payload,
            idempotency_key=_require_key(idempotency_key), request_path=request.url.path,
        )
    except _ERRORS as exc:
        return _error(db, exc)
    return read


@router.get("/fasting/state", response_model=FastingStateRead)
def fasting_state_route(current_user: CurrentUserDep, db: SessionDep) -> FastingStateRead:
    """État du moment : jeûne en cours, fenêtre suhoor → iftar, limites d'hydratation pour Pulse."""
    return fasting.state(db, current_user=current_user)


@router.get("/fasts", response_model=FastListResponse)
def list_fasts_route(
    current_user: CurrentUserDep, db: SessionDep, from_day: date | None = None, to_day: date | None = None
):
    """Jeûnes sur des jours de Paris (par défaut : les 30 derniers jours)."""
    end = to_day or fasting.paris_today()
    try:
        return fasting.list_fasts(db, current_user=current_user, from_day=from_day or end - timedelta(days=29), to_day=end)
    except _ERRORS as exc:
        return _error(db, exc)


@router.post("/fasts", response_model=FastRead, status_code=status.HTTP_201_CREATED)
def start_fast_route(
    payload: FastStartRequest,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Démarre un jeûne confirmé par l'utilisateur, le jour même ; un seul en cours."""
    try:
        read, duplicate = fasting.start_fast(
            db, current_user=current_user, payload=payload, idempotency_key=_require_key(idempotency_key)
        )
    except _ERRORS as exc:
        return _error(db, exc)
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return read


@router.post("/fasts/{fast_id}/end", response_model=FastRead)
def end_fast_route(
    fast_id: UUID,
    payload: FastEndRequest,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Fin confirmée à l'iftar ou plus tard (correction après coup)."""
    try:
        read, _ = fasting.end_fast(
            db, current_user=current_user, fast_id=fast_id, payload=payload,
            idempotency_key=_require_key(idempotency_key), request_path=request.url.path,
        )
    except _ERRORS as exc:
        return _error(db, exc)
    return read


@router.post("/fasts/{fast_id}/break", response_model=FastRead)
def break_fast_route(
    fast_id: UUID,
    payload: FastBreakRequest,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Rupture confirmée (`confirm: true`) avant l'iftar ; raison facultative, jamais dans les événements."""
    try:
        read, _ = fasting.break_fast(
            db, current_user=current_user, fast_id=fast_id, payload=payload,
            idempotency_key=_require_key(idempotency_key), request_path=request.url.path,
        )
    except _ERRORS as exc:
        return _error(db, exc)
    return read
