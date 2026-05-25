from fastapi import APIRouter

from app.api.deps import CurrentUserDep
from app.schemas.home import HomeBootstrapResponse, ImperiumContractsIndexResponse
from app.services.imperium.home import get_home_bootstrap_metadata, get_imperium_contracts_index_metadata

router = APIRouter()


@router.get("/home/bootstrap", response_model=HomeBootstrapResponse)
def imperium_home_bootstrap_route(current_user: CurrentUserDep) -> HomeBootstrapResponse:
    _ = current_user
    return get_home_bootstrap_metadata()


@router.get("/contracts/index", response_model=ImperiumContractsIndexResponse)
def imperium_contracts_index_route(current_user: CurrentUserDep) -> ImperiumContractsIndexResponse:
    _ = current_user
    return get_imperium_contracts_index_metadata()
