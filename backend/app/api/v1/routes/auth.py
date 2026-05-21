from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import SessionDep
from app.schemas.auth import (
    AuthLoginRequest,
    AuthLogoutRequest,
    AuthLogoutResponse,
    AuthRefreshRequest,
    AuthTokenResponse,
)
from app.services.auth.v1 import login_user, logout_user, refresh_user_token

router = APIRouter()


@router.post("/login", response_model=AuthTokenResponse)
def login(payload: AuthLoginRequest, request: Request, db: SessionDep) -> AuthTokenResponse:
    try:
        return login_user(
            db,
            payload,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post("/refresh", response_model=AuthTokenResponse)
def refresh_token(
    payload: AuthRefreshRequest,
    request: Request,
    db: SessionDep,
) -> AuthTokenResponse:
    try:
        return refresh_user_token(
            db,
            payload,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post("/logout", response_model=AuthLogoutResponse)
def logout(payload: AuthLogoutRequest, request: Request, db: SessionDep) -> AuthLogoutResponse:
    try:
        return logout_user(
            db,
            payload,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
