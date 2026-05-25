from pydantic import BaseModel, ConfigDict


class HomeBootstrapModule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: str
    primary_endpoint: str


class HomeBootstrapResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backend_version: str
    read_only: bool
    modules: list[HomeBootstrapModule]
    safe_explanation: str
