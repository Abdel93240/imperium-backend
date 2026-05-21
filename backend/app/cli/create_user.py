import getpass
import os
import sys
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.security import hash_master_key, hash_password
from app.db.session import SessionLocal
from app.models.auth import AuthEvent, Device, User
from app.models.enums import DeviceStatus


def main() -> int:
    try:
        with SessionLocal() as db:
            _assert_imperium_core(db)
            if _canonical_user_exists(db):
                print("Refused: canonical user already exists.", file=sys.stderr)
                return 1

            email = _read_value("IMPERIUM_BOOTSTRAP_EMAIL", "Email")
            password = _read_secret("IMPERIUM_BOOTSTRAP_PASSWORD", "Password")
            master_key = _read_secret("IMPERIUM_BOOTSTRAP_MASTER_KEY", "Master key")
            device_label = _read_optional_value("IMPERIUM_BOOTSTRAP_DEVICE_LABEL", "Device label optional")

            user = User(
                email=email,
                password_hash=hash_password(password),
                master_secret_hash=hash_master_key(master_key),
                timezone=os.getenv("IMPERIUM_BOOTSTRAP_TIMEZONE", "Europe/Paris"),
                locale=os.getenv("IMPERIUM_BOOTSTRAP_LOCALE"),
                single_user_mode=True,
            )
            db.add(user)
            db.flush()

            device = None
            if device_label:
                device = Device(
                    user_id=user.id,
                    device_label=device_label,
                    platform=os.getenv("IMPERIUM_BOOTSTRAP_DEVICE_PLATFORM"),
                    device_fingerprint=os.getenv("IMPERIUM_BOOTSTRAP_DEVICE_FINGERPRINT"),
                    status=DeviceStatus.trusted,
                    trusted_at=datetime.now(UTC),
                )
                db.add(device)
                db.flush()

            db.add(
                AuthEvent(
                    user_id=user.id,
                    device_id=device.id if device else None,
                    event_type="user.bootstrap.created",
                    success=True,
                    reason="created by app.cli.create_user",
                    created_at=datetime.now(UTC),
                )
            )
            db.commit()
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Failed to create canonical user: {exc}", file=sys.stderr)
        return 1

    print("Canonical user created.")
    if device_label:
        print("Trusted bootstrap device created.")
    return 0


def _assert_imperium_core(db: Session) -> None:
    current_database = db.execute(text("select current_database()")).scalar_one()
    if current_database != "imperium_core":
        raise RuntimeError(f"Refusing to run on database '{current_database}'. Expected 'imperium_core'.")


def _canonical_user_exists(db: Session) -> bool:
    return db.scalar(select(User.id).where(User.single_user_mode.is_(True)).limit(1)) is not None


def _read_value(env_name: str, prompt: str) -> str:
    value = os.getenv(env_name)
    if value is None:
        value = input(f"{prompt}: ")
    value = value.strip()
    if not value:
        raise ValueError(f"{prompt} is required.")
    return value


def _read_optional_value(env_name: str, prompt: str) -> str | None:
    value = os.getenv(env_name)
    if value is None:
        value = input(f"{prompt}: ")
    value = value.strip()
    return value or None


def _read_secret(env_name: str, prompt: str) -> str:
    value = os.getenv(env_name)
    if value is None:
        value = getpass.getpass(f"{prompt}: ")
    if not value:
        raise ValueError(f"{prompt} is required.")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
