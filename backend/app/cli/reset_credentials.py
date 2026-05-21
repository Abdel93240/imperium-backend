import getpass
import os
import sys
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.security import hash_master_key, hash_password
from app.db.session import SessionLocal
from app.models.auth import AuthEvent, Device, RefreshToken, User
from app.models.enums import DeviceStatus


def main() -> int:
    try:
        with SessionLocal() as db:
            _assert_imperium_core(db)
            user = _get_canonical_user(db)

            new_password = _read_optional_secret("IMPERIUM_RESET_PASSWORD", "New password optional")
            new_master_key = _read_optional_secret(
                "IMPERIUM_RESET_MASTER_KEY",
                "New master key optional",
            )
            revoke_refresh_tokens = _read_bool(
                "IMPERIUM_RESET_REVOKE_REFRESH_TOKENS",
                "Revoke all refresh tokens",
            )
            revoke_devices = _read_bool(
                "IMPERIUM_RESET_REVOKE_DEVICES",
                "Revoke trusted devices except selected",
            )
            keep_device_ids = _read_keep_device_ids() if revoke_devices else set()

            if not any([new_password, new_master_key, revoke_refresh_tokens, revoke_devices]):
                print("Refused: no reset action selected.", file=sys.stderr)
                return 1

            now = datetime.now(UTC)

            if new_password:
                user.password_hash = hash_password(new_password)
                _log_auth_event(
                    db,
                    user_id=user.id,
                    event_type="auth.password.reset",
                    reason="password reset by app.cli.reset_credentials",
                    created_at=now,
                )

            if new_master_key:
                user.master_secret_hash = hash_master_key(new_master_key)
                _log_auth_event(
                    db,
                    user_id=user.id,
                    event_type="auth.master_key.reset",
                    reason="master key reset by app.cli.reset_credentials",
                    created_at=now,
                )

            revoked_token_count = 0
            if revoke_refresh_tokens:
                revoked_token_count = _revoke_refresh_tokens(db, user, now)

            revoked_device_count = 0
            if revoke_devices:
                revoked_device_count = _revoke_devices(db, user, keep_device_ids, now)
                _log_auth_event(
                    db,
                    user_id=user.id,
                    event_type="auth.devices.revoked",
                    reason=f"revoked_devices={revoked_device_count}",
                    created_at=now,
                )

            db.commit()
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Failed to reset credentials: {exc}", file=sys.stderr)
        return 1

    print("Credential reset completed.")
    if revoke_refresh_tokens:
        print(f"Refresh tokens revoked: {revoked_token_count}")
    if revoke_devices:
        print(f"Trusted devices revoked: {revoked_device_count}")
    return 0


def _assert_imperium_core(db: Session) -> None:
    current_database = db.execute(text("select current_database()")).scalar_one()
    if current_database != "imperium_core":
        raise RuntimeError(f"Refusing to run on database '{current_database}'. Expected 'imperium_core'.")


def _get_canonical_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.single_user_mode.is_(True)).limit(1))
    if user is None:
        raise RuntimeError("Canonical user does not exist.")
    return user


def _read_optional_secret(env_name: str, prompt: str) -> str | None:
    value = os.getenv(env_name)
    if value is None:
        value = getpass.getpass(f"{prompt}: ")
    return value or None


def _read_bool(env_name: str, prompt: str) -> bool:
    value = os.getenv(env_name)
    if value is None:
        value = input(f"{prompt} [y/N]: ")
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _read_keep_device_ids() -> set[UUID]:
    raw_value = os.getenv("IMPERIUM_RESET_KEEP_DEVICE_IDS")
    if raw_value is None:
        raw_value = input("Device IDs to keep trusted, comma-separated optional: ")

    device_ids: set[UUID] = set()
    for value in raw_value.split(","):
        value = value.strip()
        if value:
            device_ids.add(UUID(value))
    return device_ids


def _revoke_refresh_tokens(db: Session, user: User, revoked_at: datetime) -> int:
    tokens = list(
        db.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id,
                RefreshToken.revoked_at.is_(None),
            )
        )
    )
    for token in tokens:
        token.revoked_at = revoked_at
    return len(tokens)


def _revoke_devices(
    db: Session,
    user: User,
    keep_device_ids: set[UUID],
    revoked_at: datetime,
) -> int:
    devices = list(
        db.scalars(
            select(Device).where(
                Device.user_id == user.id,
                Device.status == DeviceStatus.trusted,
                Device.id.not_in(keep_device_ids),
            )
        )
    )
    for device in devices:
        device.status = DeviceStatus.revoked
        device.revoked_at = revoked_at
    return len(devices)


def _log_auth_event(
    db: Session,
    *,
    user_id: UUID,
    event_type: str,
    reason: str,
    created_at: datetime,
) -> None:
    db.add(
        AuthEvent(
            user_id=user_id,
            event_type=event_type,
            success=True,
            reason=reason,
            created_at=created_at,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
