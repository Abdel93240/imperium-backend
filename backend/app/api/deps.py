from collections.abc import Generator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models.auth import Device, User
from app.models.enums import DeviceStatus


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


SessionDep = Annotated[Session, Depends(get_db)]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(db: SessionDep, token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        if payload.get("type") != "access":
            raise credentials_error
        user_id = UUID(str(payload["sub"]))
        device_id = UUID(str(payload["device_id"]))
    except (KeyError, ValueError, JWTError):
        raise credentials_error from None

    user = db.get(User, user_id)
    if user is None:
        raise credentials_error

    device = db.scalar(
        select(Device).where(
            Device.id == device_id,
            Device.user_id == user.id,
            Device.status == DeviceStatus.trusted,
        )
    )
    if device is None:
        raise credentials_error

    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
