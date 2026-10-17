"""Paramètres avancés de l'IA (doc 73, brief B8)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Provider = Literal["local", "openrouter", "openai", "anthropic", "google"]


class RoleModelRead(BaseModel):
    role: str
    provider: str | None
    model_id: str | None
    effort: str | None
    sensitivity_route: str
    version: int | None


class RoleModelListResponse(BaseModel):
    roles: list[RoleModelRead]


class RoleModelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Provider
    model_id: str = Field(min_length=1, max_length=200)
    effort: Literal["minimal", "low", "medium", "high", "xhigh"] | None = None

    @field_validator("model_id")
    @classmethod
    def strip_model(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped or any(char.isspace() for char in stripped):
            raise ValueError("model_id must be a single identifier.")
        return stripped


class CatalogResponse(BaseModel):
    providers: dict[str, list[str]]
    effort_levels: list[str]
    remote_catalog_available: bool
    note: str


class ThresholdBand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=60)
    start: int = Field(ge=0, le=200)
    end: int = Field(ge=0, le=200)


class ThresholdsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bands: list[ThresholdBand] = Field(min_length=4, max_length=4)


class ThresholdsRead(ThresholdsUpdate):
    version: int | None = None


class ApiKeyStatus(BaseModel):
    provider: str
    present: bool


class ApiKeyListResponse(BaseModel):
    keys: list[ApiKeyStatus]


class ApiKeyReplace(BaseModel):
    """Écriture seule : la clé n'est jamais renvoyée (doc 73, doc 63 §13.4)."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(max_length=4096)
