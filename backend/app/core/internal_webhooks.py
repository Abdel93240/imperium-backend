import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from fastapi import Header, HTTPException, Request, status

from app.core.config import get_settings


@dataclass(frozen=True)
class InternalWebhookContext:
    idempotency_key: str
    timestamp: int


async def verify_internal_webhook(
    request: Request,
    x_signature: str | None = Header(default=None, alias="X-Signature"),
    x_timestamp: str | None = Header(default=None, alias="X-Timestamp"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> InternalWebhookContext:
    settings = get_settings()

    if not x_signature:
        raise _unauthorized("Missing signature.")
    if not x_timestamp:
        raise _unauthorized("Missing timestamp.")
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Idempotency-Key header.",
        )

    timestamp = _parse_timestamp(x_timestamp)
    _validate_timestamp_freshness(timestamp, settings.webhook_timestamp_tolerance_seconds)

    raw_body = await request.body()
    expected_signature = sign_internal_webhook_body(
        secret=settings.internal_webhook_secret,
        timestamp=timestamp,
        body=raw_body,
    )
    normalized_signature = _normalize_signature(x_signature)
    if not hmac.compare_digest(normalized_signature, expected_signature):
        raise _unauthorized("Invalid signature.")

    return InternalWebhookContext(idempotency_key=idempotency_key, timestamp=timestamp)


def sign_internal_webhook_body(*, secret: str, timestamp: int, body: bytes) -> str:
    message = str(timestamp).encode("utf-8") + b"." + body
    return hmac.new(secret.encode("utf-8"), message, sha256).hexdigest()


def _parse_timestamp(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-Timestamp header.",
        ) from None


def _validate_timestamp_freshness(timestamp: int, tolerance_seconds: int) -> None:
    now = int(datetime.now(UTC).timestamp())
    if abs(now - timestamp) > tolerance_seconds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Stale webhook timestamp.",
        )


def _normalize_signature(signature: str) -> str:
    return signature.removeprefix("sha256=").strip().lower()


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)
