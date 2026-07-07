from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import PrivacyLevel, SourceApp


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
    depth: int | None = Field(default=None, ge=1)
    privacy_level: PrivacyLevel
    payload: dict


class EventIngestResponse(BaseModel):
    event_id: str
    status: str
    duplicate: bool = False
