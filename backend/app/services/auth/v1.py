import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token_parts,
    hash_refresh_token,
    verify_master_key,
    verify_password,
    verify_refresh_token,
)
from app.models.auth import AuthEvent, Device, RefreshToken, User
from app.models.enums import DeviceStatus
from app.schemas.auth import (
    AuthLoginRequest,
    AuthLogoutRequest,
    AuthLogoutResponse,
    AuthRefreshRequest,
    AuthTokenResponse,
)

logger = logging.getLogger(__name__)

SAFE_AUTH_REASON_CODES = {
    "invalid_credentials",
    "device_revoked",
    "user_missing",
    "token_invalid",
    "token_expired",
    "internal_error",
}


def log_auth_event(
    db: Session,
    *,
    event_type: str,
    success: bool,
    user_id: UUID | None = None,
    device_id: UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    reason: str | None = None,
) -> None:
    db.add(
        AuthEvent(
            user_id=user_id,
            device_id=device_id,
            event_type=event_type,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            reason=reason,
            created_at=datetime.now(UTC),
        )
    )


def login_user(
    db: Session,
    request: AuthLoginRequest,
    *,
    ip_address: str | None,
    user_agent: str | None,
) -> AuthTokenResponse:
    user = None
    try:
        user = db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
        if user is None:
            raise ValueError("Canonical user does not exist. Run python -m app.cli.create_user first.")

        _verify_existing_user_credentials(user, request)

        device = _get_or_create_trusted_device(db, user, request)
        refresh_token = _create_refresh_token(db, user, device)
        access_token, expires_in_seconds = create_access_token(user.id, device.id)

        log_auth_event(
            db,
            event_type="login",
            success=True,
            user_id=user.id,
            device_id=device.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.commit()

        return AuthTokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in_seconds=expires_in_seconds,
            device_id=str(device.id),
        )
    except Exception as exc:
        logger.exception("Auth login failed.")
        db.rollback()
        log_auth_event(
            db,
            event_type="login",
            success=False,
            user_id=user.id if user is not None else None,
            ip_address=ip_address,
            user_agent=user_agent,
            reason=_safe_auth_failure_reason(exc),
        )
        db.commit()
        raise


def refresh_user_token(
    db: Session,
    request: AuthRefreshRequest,
    *,
    ip_address: str | None,
    user_agent: str | None,
) -> AuthTokenResponse:
    user = None
    device = None
    try:
        old_token = _get_valid_refresh_token(db, request.refresh_token)
        if str(old_token.device_id) != request.device_id:
            raise ValueError("Invalid refresh token.")

        device = db.get(Device, old_token.device_id)
        if device is None or device.status != DeviceStatus.trusted:
            raise ValueError("Invalid refresh token.")

        user = db.get(User, old_token.user_id)
        if user is None:
            raise ValueError("Invalid refresh token.")

        raw_refresh_token, new_refresh_token = _build_refresh_token(db, user, device)
        db.flush()
        old_token.revoked_at = datetime.now(UTC)
        old_token.replaced_by_token_id = new_refresh_token.id
        access_token, expires_in_seconds = create_access_token(user.id, device.id)

        log_auth_event(
            db,
            event_type="auth.refresh.rotated",
            success=True,
            user_id=user.id,
            device_id=device.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.commit()

        return AuthTokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            expires_in_seconds=expires_in_seconds,
            device_id=str(device.id),
        )
    except Exception as exc:
        logger.exception("Auth refresh failed.")
        db.rollback()
        log_auth_event(
            db,
            event_type="auth.refresh.failed",
            success=False,
            user_id=user.id if user is not None else None,
            device_id=device.id if device is not None else None,
            ip_address=ip_address,
            user_agent=user_agent,
            reason=_safe_auth_failure_reason(exc),
        )
        db.commit()
        raise


def logout_user(
    db: Session,
    request: AuthLogoutRequest,
    *,
    ip_address: str | None,
    user_agent: str | None,
) -> AuthLogoutResponse:
    token = None
    try:
        token = _get_valid_refresh_token(db, request.refresh_token)
        if str(token.device_id) != request.device_id:
            raise ValueError("Invalid refresh token.")

        token.revoked_at = datetime.now(UTC)
        log_auth_event(
            db,
            event_type="auth.logout",
            success=True,
            user_id=token.user_id,
            device_id=token.device_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.commit()
        return AuthLogoutResponse(status="ok")
    except Exception as exc:
        logger.exception("Auth logout failed.")
        db.rollback()
        log_auth_event(
            db,
            event_type="auth.logout.failed",
            success=False,
            user_id=token.user_id if token is not None else None,
            device_id=token.device_id if token is not None else None,
            ip_address=ip_address,
            user_agent=user_agent,
            reason=_safe_auth_failure_reason(exc),
        )
        db.commit()
        raise


def _verify_existing_user_credentials(user: User, request: AuthLoginRequest) -> None:
    if request.email and request.password:
        if user.email != request.email or user.password_hash is None:
            raise ValueError("Invalid login credentials.")
        if not verify_password(request.password, user.password_hash):
            raise ValueError("Invalid login credentials.")
        return

    if request.master_key:
        if user.master_secret_hash is None:
            raise ValueError("Invalid login credentials.")
        if not verify_master_key(request.master_key, user.master_secret_hash):
            raise ValueError("Invalid login credentials.")
        return

    raise ValueError("Invalid login credentials.")


def _get_or_create_trusted_device(db: Session, user: User, request: AuthLoginRequest) -> Device:
    query = select(Device).where(Device.user_id == user.id)
    if request.device_fingerprint:
        query = query.where(Device.device_fingerprint == request.device_fingerprint)
    else:
        query = query.where(Device.device_label == request.device_label)

    device = db.scalar(query.order_by(Device.created_at.asc()).limit(1))
    now = datetime.now(UTC)

    if device is None:
        device = Device(
            user_id=user.id,
            device_label=request.device_label,
            device_fingerprint=request.device_fingerprint,
            platform=request.platform,
            status=DeviceStatus.trusted,
            trusted_at=now,
        )
        db.add(device)
        db.flush()
        return device

    if device.status == DeviceStatus.revoked:
        raise ValueError("Device is revoked.")

    device.device_label = request.device_label
    device.platform = request.platform
    return device


def _create_refresh_token(db: Session, user: User, device: Device) -> str:
    raw_token, _ = _build_refresh_token(db, user, device)
    return raw_token


def _build_refresh_token(db: Session, user: User, device: Device) -> tuple[str, RefreshToken]:
    settings = get_settings()
    raw_token, selector, secret = create_refresh_token_parts()
    now = datetime.now(UTC)
    refresh_token = RefreshToken(
        user_id=user.id,
        device_id=device.id,
        token_selector=selector,
        token_secret_hash=hash_refresh_token(secret),
        issued_at=now,
        expires_at=now + timedelta(days=settings.refresh_token_ttl_days),
        created_at=now,
    )
    db.add(refresh_token)
    return raw_token, refresh_token


def _get_valid_refresh_token(db: Session, raw_refresh_token: str) -> RefreshToken:
    selector, secret = _split_refresh_token(raw_refresh_token)
    refresh_token = db.scalar(
        select(RefreshToken).where(RefreshToken.token_selector == selector).limit(1)
    )
    now = datetime.now(UTC)
    if refresh_token is None:
        raise ValueError("Invalid refresh token.")
    if refresh_token.revoked_at is not None:
        raise ValueError("Invalid refresh token.")
    if refresh_token.expires_at <= now:
        raise ValueError("Refresh token expired.")
    if not verify_refresh_token(secret, refresh_token.token_secret_hash):
        raise ValueError("Invalid refresh token.")
    return refresh_token


def _split_refresh_token(raw_refresh_token: str) -> tuple[str, str]:
    parts = raw_refresh_token.split(".", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("Invalid refresh token.")
    return parts[0], parts[1]


def _safe_auth_failure_reason(exc: Exception) -> str:
    if not isinstance(exc, ValueError):
        return "internal_error"

    message = str(exc).lower()
    if "canonical user does not exist" in message:
        return "user_missing"
    if "device is revoked" in message:
        return "device_revoked"
    if "expired" in message:
        return "token_expired"
    if "refresh token" in message:
        return "token_invalid"
    if "credential" in message or "login" in message:
        return "invalid_credentials"
    return "internal_error"
