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
