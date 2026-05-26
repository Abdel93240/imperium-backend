from pydantic import BaseModel, ConfigDict


class ImperiumFrontendNavigationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    route: str
    api_endpoint: str
    order: int
    enabled: bool


class ImperiumFrontendNavigationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    navigation_version: str
    read_only: bool
    items: list[ImperiumFrontendNavigationItem]
    safe_explanation: str


class ImperiumFrontendLayoutShell(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: str
    density: str
    navigation_position: str
    primary_surface: str


class ImperiumFrontendLayoutRegion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    purpose: str
    order: int
    enabled: bool


class ImperiumFrontendLayoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layout_version: str
    read_only: bool
    shell: ImperiumFrontendLayoutShell
    regions: list[ImperiumFrontendLayoutRegion]
    safe_explanation: str


class ImperiumFrontendThemeSurface(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    purpose: str
    token: str


class ImperiumFrontendThemeScaleItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    value: int


class ImperiumFrontendThemeTypographyItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    purpose: str


class ImperiumFrontendThemePalette(BaseModel):
    model_config = ConfigDict(extra="forbid")

    background: str
    surface: str
    primary: str
    secondary: str
    danger: str
    muted: str


class ImperiumFrontendThemeTokensResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme_version: str
    read_only: bool
    style_name: str
    palette: ImperiumFrontendThemePalette
    surfaces: list[ImperiumFrontendThemeSurface]
    spacing_scale: list[ImperiumFrontendThemeScaleItem]
    radius_scale: list[ImperiumFrontendThemeScaleItem]
    typography_scale: list[ImperiumFrontendThemeTypographyItem]
    safe_explanation: str


class ImperiumFrontendEmptyStateItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    module: str
    title: str
    message: str
    primary_action_label: str
    primary_route: str


class ImperiumFrontendEmptyStatesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    empty_states_version: str
    read_only: bool
    items: list[ImperiumFrontendEmptyStateItem]
    safe_explanation: str


class ImperiumFrontendActionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    module: str
    action_type: str
    route: str
    requires_confirmation: bool


class ImperiumFrontendActionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actions_version: str
    read_only: bool
    items: list[ImperiumFrontendActionItem]
    safe_explanation: str


class ImperiumFrontendApplicationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    tagline: str
    default_route: str
    default_locale: str
    default_timezone: str


class ImperiumFrontendAppManifestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_version: str
    read_only: bool
    application: ImperiumFrontendApplicationMetadata
    frontend_metadata_endpoints: list[str]
    safe_explanation: str


class ImperiumFrontendModuleCardItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    title: str
    subtitle: str
    route: str
    primary_endpoint: str
    order: int
    enabled: bool


class ImperiumFrontendModuleCardsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_cards_version: str
    read_only: bool
    items: list[ImperiumFrontendModuleCardItem]
    safe_explanation: str


class ImperiumFrontendAssetRegistryPlaceholderPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    placeholder_allowed: bool
    placeholder_style: str
    safe_explanation: str


class ImperiumFrontendAssetRegistryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    asset_type: str
    expected_filename: str
    usage: str
    status: str
    placeholder_allowed: bool


class ImperiumFrontendAssetRegistryGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    base_path: str
    items: list[ImperiumFrontendAssetRegistryItem]


class ImperiumFrontendAssetRegistryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_registry_version: str
    read_only: bool
    asset_base_path: str
    placeholder_policy: ImperiumFrontendAssetRegistryPlaceholderPolicy
    groups: list[ImperiumFrontendAssetRegistryGroup]
    safe_explanation: str
