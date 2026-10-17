"""Réglages Imperium (doc 43 §15, doc 65 §8.5).

Une ligne par utilisateur, créée à la première lecture avec les valeurs par défaut
des docs. Les réglages côté appareil (permissions, overlay) restent Android.
"""

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.imperium import ImperiumUserSettings
from app.schemas.settings import UserSettingsRead, UserSettingsUpdate

DEFAULT_REPLAN_DEBOUNCE_MINUTES = 5


def get_settings(db: Session, *, current_user: User) -> UserSettingsRead:
    return UserSettingsRead.model_validate(_get_or_create(db, current_user=current_user))


def update_settings(db: Session, *, current_user: User, payload: UserSettingsUpdate) -> UserSettingsRead:
    row = _get_or_create(db, current_user=current_user)
    for field in payload.model_fields_set:
        value = getattr(payload, field)
        if value is not None:
            setattr(row, field, value)
    db.commit()
    return UserSettingsRead.model_validate(row)


def replan_debounce_minutes(db: Session, *, current_user: User) -> int:
    """Lecture sans création : sans réglage enregistré, la valeur par défaut du doc 43 §15."""
    value = db.scalar(
        select(ImperiumUserSettings.replan_debounce_minutes).where(ImperiumUserSettings.user_id == current_user.id)
    )
    return value or DEFAULT_REPLAN_DEBOUNCE_MINUTES


def _get_or_create(db: Session, *, current_user: User) -> ImperiumUserSettings:
    row = db.scalar(select(ImperiumUserSettings).where(ImperiumUserSettings.user_id == current_user.id))
    if row is not None:
        return row
    row = ImperiumUserSettings(
        id=uuid4(),
        user_id=current_user.id,
        bubble_enabled=True,
        notifications_enabled=True,
        notify_weekly_review=True,
        notify_mission_reminders=True,
        notify_red_alerts=True,
        morning_popup_enabled=True,
        ai_mode="equilibre",
        replan_on_failure_urgent="replan",
        replan_on_failure_other="ask",
        replan_debounce_minutes=DEFAULT_REPLAN_DEBOUNCE_MINUTES,
        chat_retention_days=90,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # Création concurrente : relire la ligne gagnante.
        db.rollback()
        row = db.scalar(select(ImperiumUserSettings).where(ImperiumUserSettings.user_id == current_user.id))
    return row
