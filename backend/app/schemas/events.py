from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import PrivacyLevel, SourceApp

ImperiumEventSourceModule = Literal[
    "mission",
    "vault",
    "path",
    "pulse",
    "vector",
    "dashboard",
    "daily_plan",
    "system",
    "manual",
]


class EventEnvelope(BaseModel):
    event_id: str = Field(min_length=1)
    event_type: str = Field(pattern=r"^[a-z][a-z0-9]*(\.[a-z][a-z0-9]*)+$")
    schema_version: str = Field(min_length=1)
    occurred_at: datetime
    received_at: datetime | None = None
    source_app: SourceApp
    device_id: UUID | None = None
    user_id: UUID
    idempotency_key: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    causation_id: str | None = None
    privacy_level: PrivacyLevel
    payload: dict


class EventIngestResponse(BaseModel):
    event_id: str
    status: str
    duplicate: bool = False


class ImperiumEventCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(min_length=1, max_length=120, pattern=r"^[a-z][a-z0-9_]*$")
    source_module: ImperiumEventSourceModule
    occurred_at: datetime
    payload_json: dict[str, Any] | None = None
    schema_version: str = Field(default="v1", min_length=1, max_length=8, pattern=r"^v1$")

    @field_validator("event_type", "source_module", "schema_version", mode="before")
    @classmethod
    def strip_event_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be empty.")
        return stripped

    @field_validator("occurred_at")
    @classmethod
    def require_timezone_aware_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware.")
        return value

    @model_validator(mode="after")
    def validate_payload_json(self) -> "ImperiumEventCreateRequest":
        if self.payload_json is not None and _contains_user_id_key(self.payload_json):
            raise ValueError("payload_json must not contain user_id.")
        return self


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    event_type: str
    source_module: ImperiumEventSourceModule
    occurred_at: datetime
    payload_json: dict[str, Any] | None
    schema_version: str
    created_at: datetime
    updated_at: datetime
    safe_explanation: str = "Imperium event record for current user."


class ImperiumEventWriteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: EventRead
    safe_explanation: str = "Imperium event appended for current user."


class ImperiumEventListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[EventRead]
    count: int
    limit: int
    offset: int
    safe_explanation: str = "Imperium events for current user."


class ImperiumEventDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: EventRead
    safe_explanation: str = "Imperium event detail for current user."


def _contains_user_id_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "user_id":
                return True
            if _contains_user_id_key(child):
                return True
    elif isinstance(value, list):
        for item in value:
            if _contains_user_id_key(item):
                return True
    return False
