"""Stock alimentaire de Pulse (doc 40 §11, écran PUL-12) — lecture V1."""

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.pulse import FoodStockListResponse
from app.services.pulse import food_stock

router = APIRouter()


@router.get("/food-stock", response_model=FoodStockListResponse)
def list_food_stock_route(
    current_user: CurrentUserDep, db: SessionDep, include_inactive: bool = False
) -> FoodStockListResponse:
    """Stock actif, date limite la plus proche en premier."""
    return food_stock.list_stock(db, current_user=current_user, include_inactive=include_inactive)
