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
