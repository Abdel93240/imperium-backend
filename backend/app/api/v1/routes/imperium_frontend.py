from fastapi import APIRouter

from app.api.deps import CurrentUserDep
from app.schemas.frontend import (
    ImperiumFrontendAssetRegistryResponse,
    ImperiumFrontendAppManifestResponse,
    ImperiumFrontendActionsResponse,
    ImperiumFrontendDesignHandoffResponse,
    ImperiumFrontendEmptyStatesResponse,
    ImperiumFrontendLayoutResponse,
    ImperiumFrontendModuleCardsResponse,
    ImperiumFrontendNavigationResponse,
    ImperiumFrontendThemeTokensResponse,
)
from app.services.imperium.frontend import (
    get_imperium_frontend_asset_registry_metadata,
    get_imperium_frontend_app_manifest_metadata,
    get_imperium_frontend_actions_metadata,
    get_imperium_frontend_design_handoff_metadata,
    get_imperium_frontend_empty_states_metadata,
    get_imperium_frontend_layout_metadata,
    get_imperium_frontend_module_cards_metadata,
    get_imperium_frontend_navigation_metadata,
    get_imperium_frontend_theme_tokens_metadata,
)

router = APIRouter()


@router.get("/frontend/actions", response_model=ImperiumFrontendActionsResponse)
def imperium_frontend_actions_route(current_user: CurrentUserDep) -> ImperiumFrontendActionsResponse:
    _ = current_user
    return get_imperium_frontend_actions_metadata()


@router.get("/frontend/navigation", response_model=ImperiumFrontendNavigationResponse)
def imperium_frontend_navigation_route(current_user: CurrentUserDep) -> ImperiumFrontendNavigationResponse:
    _ = current_user
    return get_imperium_frontend_navigation_metadata()


@router.get("/frontend/layout", response_model=ImperiumFrontendLayoutResponse)
def imperium_frontend_layout_route(current_user: CurrentUserDep) -> ImperiumFrontendLayoutResponse:
    _ = current_user
    return get_imperium_frontend_layout_metadata()


@router.get("/frontend/module-cards", response_model=ImperiumFrontendModuleCardsResponse)
def imperium_frontend_module_cards_route(current_user: CurrentUserDep) -> ImperiumFrontendModuleCardsResponse:
    _ = current_user
    return get_imperium_frontend_module_cards_metadata()


@router.get("/frontend/asset-registry", response_model=ImperiumFrontendAssetRegistryResponse)
def imperium_frontend_asset_registry_route(current_user: CurrentUserDep) -> ImperiumFrontendAssetRegistryResponse:
    _ = current_user
    return get_imperium_frontend_asset_registry_metadata()


@router.get("/frontend/theme-tokens", response_model=ImperiumFrontendThemeTokensResponse)
def imperium_frontend_theme_tokens_route(current_user: CurrentUserDep) -> ImperiumFrontendThemeTokensResponse:
    _ = current_user
    return get_imperium_frontend_theme_tokens_metadata()


@router.get("/frontend/empty-states", response_model=ImperiumFrontendEmptyStatesResponse)
def imperium_frontend_empty_states_route(current_user: CurrentUserDep) -> ImperiumFrontendEmptyStatesResponse:
    _ = current_user
    return get_imperium_frontend_empty_states_metadata()


@router.get("/frontend/app-manifest", response_model=ImperiumFrontendAppManifestResponse)
def imperium_frontend_app_manifest_route(current_user: CurrentUserDep) -> ImperiumFrontendAppManifestResponse:
    _ = current_user
    return get_imperium_frontend_app_manifest_metadata()


@router.get("/frontend/design-handoff", response_model=ImperiumFrontendDesignHandoffResponse)
def imperium_frontend_design_handoff_route(current_user: CurrentUserDep) -> ImperiumFrontendDesignHandoffResponse:
    _ = current_user
    return get_imperium_frontend_design_handoff_metadata()
