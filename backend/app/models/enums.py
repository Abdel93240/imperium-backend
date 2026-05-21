from enum import StrEnum


class SourceApp(StrEnum):
    imperium = "imperium"
    vector = "vector"
    vault = "vault"
    pulse = "pulse"
    path = "path"
    core = "core"
    external = "external"
    n8n = "n8n"
    ai_router = "ai_router"


class PrivacyLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    very_high = "very_high"


class DeviceStatus(StrEnum):
    trusted = "trusted"
    revoked = "revoked"


class IdempotencyStatus(StrEnum):
    processing = "processing"
    completed = "completed"
    failed = "failed"

