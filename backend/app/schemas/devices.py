from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DeviceStatus


class DeviceRegisterRequest(BaseModel):
    device_label: str = Field(min_length=1)
    device_fingerprint: str | None = None
    platform: str | None = None


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    device_label: str
    device_fingerprint: str | None
    platform: str | None
    status: DeviceStatus
    trusted_at: datetime
    revoked_at: datetime | None
