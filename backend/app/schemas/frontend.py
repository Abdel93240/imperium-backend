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


class ImperiumFrontendStaticCopyItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    module: str
    text: str


class ImperiumFrontendStaticCopyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    static_copy_version: str
    read_only: bool
    items: list[ImperiumFrontendStaticCopyItem]
    safe_explanation: str
