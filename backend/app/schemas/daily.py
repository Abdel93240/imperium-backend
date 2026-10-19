from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ScoringParameterRead(BaseModel):
    code: str
    version: int
    value: dict | list
    origin: str
    rationale_fr: str | None
    valid_from: datetime


class ScoringSettingsRead(BaseModel):
    """Barèmes `df.*` courants ; `source=code` si le service retombe sur les constantes (absent ou invalide)."""

    source: Literal["parameters", "code"]
    parameters: list[ScoringParameterRead]


class ScoringParameterVersionsResponse(BaseModel):
    versions: list[ScoringParameterRead]


class ScoringSettingsUpdateRequest(BaseModel):
    """Nouvelle version des paramètres cités (valeur complète de chacun) ; raison obligatoire."""

    model_config = ConfigDict(extra="forbid")

    changes: dict[str, dict | list] = Field(min_length=1, max_length=8)
    reason_fr: str = Field(min_length=3, max_length=500)
