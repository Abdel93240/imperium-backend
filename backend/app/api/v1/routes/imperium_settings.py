"""Routes des réglages Imperium (doc 43 §15, doc 65 §8.5)."""

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.settings import UserSettingsRead, UserSettingsUpdate
from app.services.imperium import settings as user_settings

router = APIRouter()


@router.get("/settings", response_model=UserSettingsRead)
def get_settings_route(current_user: CurrentUserDep, db: SessionDep) -> UserSettingsRead:
    return user_settings.get_settings(db, current_user=current_user)


@router.patch("/settings", response_model=UserSettingsRead)
def update_settings_route(payload: UserSettingsUpdate, current_user: CurrentUserDep, db: SessionDep) -> UserSettingsRead:
    return user_settings.update_settings(db, current_user=current_user, payload=payload)
