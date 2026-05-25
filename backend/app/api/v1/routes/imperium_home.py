from fastapi import APIRouter

from app.api.deps import CurrentUserDep
from app.schemas.home import HomeBootstrapResponse
from app.services.imperium.home import get_home_bootstrap_metadata

router = APIRouter()


@router.get("/home/bootstrap", response_model=HomeBootstrapResponse)
def imperium_home_bootstrap_route(current_user: CurrentUserDep) -> HomeBootstrapResponse:
    _ = current_user
    return get_home_bootstrap_metadata()
