"""Stock alimentaire de Pulse (doc 40 §11, écran PUL-12) : lecture, ajout et modification manuels."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.pulse import FoodStockItemCreate, FoodStockItemRead, FoodStockItemUpdate, FoodStockListResponse
from app.services.pulse import food_stock

router = APIRouter()


def _require_key(idempotency_key: str | None) -> str:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    return idempotency_key


@router.get("/food-stock", response_model=FoodStockListResponse)
def list_food_stock_route(
    current_user: CurrentUserDep, db: SessionDep, include_inactive: bool = False
) -> FoodStockListResponse:
    """Stock actif, date limite la plus proche en premier."""
    return food_stock.list_stock(db, current_user=current_user, include_inactive=include_inactive)


@router.post("/food-stock", response_model=FoodStockItemRead, status_code=status.HTTP_201_CREATED)
def create_food_stock_route(
    payload: FoodStockItemCreate,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> FoodStockItemRead:
    try:
        item, duplicate = food_stock.create_item(
            db, current_user=current_user, payload=payload, idempotency_key=_require_key(idempotency_key),
            request_path=request.url.path,
        )
    except food_stock.FoodStockIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return item


@router.patch("/food-stock/{item_id}", response_model=FoodStockItemRead)
def update_food_stock_route(
    item_id: UUID,
    payload: FoodStockItemUpdate,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Version dépassée → 409 avec la ligne actuelle (dialogue de conflit de PUL-12)."""
    try:
        return food_stock.update_item(
            db, current_user=current_user, item_id=item_id, payload=payload,
            idempotency_key=_require_key(idempotency_key), request_path=request.url.path,
        )
    except food_stock.FoodStockNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except food_stock.FoodStockVersionConflictError as exc:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc), "code": "STOCK_VERSION_CONFLICT", "current": exc.current.model_dump(mode="json")},
        )
    except food_stock.FoodStockIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
