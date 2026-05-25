from fastapi import APIRouter

from app.api.deps import CurrentUserDep
from app.schemas.contracts import (
    ImperiumContractsComplianceResponse,
    ImperiumContractsIndexResponse,
)
from app.services.imperium.contracts import (
    get_imperium_contracts_compliance_metadata,
    get_imperium_contracts_index_metadata,
)

router = APIRouter()


@router.get("/contracts/index", response_model=ImperiumContractsIndexResponse)
def imperium_contracts_index_route(current_user: CurrentUserDep) -> ImperiumContractsIndexResponse:
    _ = current_user
    return get_imperium_contracts_index_metadata()


@router.get("/contracts/compliance", response_model=ImperiumContractsComplianceResponse)
def imperium_contracts_compliance_route(current_user: CurrentUserDep) -> ImperiumContractsComplianceResponse:
    _ = current_user
    return get_imperium_contracts_compliance_metadata()
