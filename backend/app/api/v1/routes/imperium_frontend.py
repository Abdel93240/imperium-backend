from fastapi import APIRouter

from app.api.deps import CurrentUserDep
from app.schemas.frontend import ImperiumFrontendNavigationResponse
from app.services.imperium.frontend import get_imperium_frontend_navigation_metadata

router = APIRouter()


@router.get("/frontend/navigation", response_model=ImperiumFrontendNavigationResponse)
def imperium_frontend_navigation_route(current_user: CurrentUserDep) -> ImperiumFrontendNavigationResponse:
    _ = current_user
    return get_imperium_frontend_navigation_metadata()
