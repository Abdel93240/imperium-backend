from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from uuid import UUID

from argon2.exceptions import VerifyMismatchError
from argon2 import PasswordHasher
from jose import jwt

from app.core.config import get_settings

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def hash_master_key(master_key: str) -> str:
    return _password_hasher.hash(master_key)


def verify_master_key(master_key: str, master_key_hash: str) -> bool:
    try:
        return _password_hasher.verify(master_key_hash, master_key)
    except VerifyMismatchError:
        return False


def hash_refresh_token(refresh_token: str) -> str:
    return _password_hasher.hash(refresh_token)


def verify_refresh_token(refresh_token: str, refresh_token_hash: str) -> bool:
    try:
        return _password_hasher.verify(refresh_token_hash, refresh_token)
    except VerifyMismatchError:
        return False


def create_refresh_token_parts() -> tuple[str, str, str]:
    selector = token_urlsafe(18)
    secret = token_urlsafe(48)
    return f"{selector}.{secret}", selector, secret


def create_access_token(user_id: UUID, device_id: UUID) -> tuple[str, int]:
    settings = get_settings()
    expires_delta = timedelta(minutes=settings.access_token_ttl_minutes)
    expires_at = datetime.now(UTC) + expires_delta
    payload = {
        "sub": str(user_id),
        "device_id": str(device_id),
        "type": "access",
        "exp": expires_at,
        "iat": datetime.now(UTC),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
