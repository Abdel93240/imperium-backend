import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from urllib import request
from urllib.error import URLError
from urllib.parse import urljoin, urlparse

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class SignedN8NRequest:
    url: str
    body: bytes
    headers: dict[str, str]


@dataclass(frozen=True)
class N8NTriggerResult:
    dry_run: bool
    configured: bool
    status_code: int | None
    response_body: str | None
    request: SignedN8NRequest


class N8NConfigurationError(ValueError):
    pass


class N8NRequestError(RuntimeError):
    pass


def build_signed_n8n_request(
    *,
    path: str,
    payload: dict,
    idempotency_key: str,
    settings: Settings | None = None,
    timestamp: int | None = None,
) -> SignedN8NRequest:
    settings = settings or get_settings()
    base_url = _base_url(settings)
    secret = _webhook_secret(settings)
    body = _json_body(payload)
    timestamp = timestamp or int(datetime.now(UTC).timestamp())
    headers = {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotency_key,
        "X-Timestamp": str(timestamp),
        "X-Signature": _sign(secret=secret, timestamp=timestamp, body=body),
    }
    return SignedN8NRequest(
        url=urljoin(base_url, path.lstrip("/")),
        body=body,
        headers=headers,
    )


def trigger_n8n_webhook(
    *,
    path: str,
    payload: dict,
    idempotency_key: str,
    settings: Settings | None = None,
    dry_run: bool | None = None,
) -> N8NTriggerResult:
    settings = settings or get_settings()
    should_dry_run = settings.n8n_dry_run if dry_run is None else dry_run
    if should_dry_run and not n8n_is_configured(settings):
        return N8NTriggerResult(
            dry_run=True,
            configured=False,
            status_code=None,
            response_body=None,
            request=SignedN8NRequest(
                url=path,
                body=_json_body(payload),
                headers={
                    "Content-Type": "application/json",
                    "Idempotency-Key": idempotency_key,
                },
            ),
        )
    signed_request = build_signed_n8n_request(
        path=path,
        payload=payload,
        idempotency_key=idempotency_key,
        settings=settings,
    )
    if should_dry_run:
        return N8NTriggerResult(
            dry_run=True,
            configured=True,
            status_code=None,
            response_body=None,
            request=signed_request,
        )

    req = request.Request(
        signed_request.url,
        data=signed_request.body,
        headers=signed_request.headers,
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=settings.n8n_request_timeout_seconds) as response:  # nosec B310
            return N8NTriggerResult(
                dry_run=False,
                configured=True,
                status_code=response.status,
                response_body=response.read().decode("utf-8"),
                request=signed_request,
            )
    except URLError as exc:
        raise N8NRequestError("n8n webhook request failed.") from exc


def n8n_is_configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.n8n_base_url and settings.n8n_webhook_secret)


def _json_body(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _sign(*, secret: str, timestamp: int, body: bytes) -> str:
    message = str(timestamp).encode("utf-8") + b"." + body
    return hmac.new(secret.encode("utf-8"), message, sha256).hexdigest()


def _base_url(settings: Settings) -> str:
    if not settings.n8n_base_url:
        raise N8NConfigurationError("N8N_BASE_URL is not configured.")
    base_url = settings.n8n_base_url.rstrip("/") + "/"
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise N8NConfigurationError("N8N_BASE_URL must be an http(s) URL.")
    return base_url


def _webhook_secret(settings: Settings) -> str:
    if not settings.n8n_webhook_secret:
        raise N8NConfigurationError("N8N_WEBHOOK_SECRET is not configured.")
    return settings.n8n_webhook_secret
