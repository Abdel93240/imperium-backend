"""Réglages Imperium (doc 43 §15, doc 65 §8.5 ; décisions 2026-10-15/16/17)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AiMode = Literal["strict", "equilibre", "souple"]
FailureAction = Literal["replan", "ask"]
RetentionDays = Literal[30, 60, 90, 180, 365]


class UserSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bubble_enabled: bool
    notifications_enabled: bool
    notify_weekly_review: bool
    notify_mission_reminders: bool
    notify_red_alerts: bool
    morning_popup_enabled: bool
    ai_mode: AiMode
    replan_on_failure_urgent: FailureAction
    replan_on_failure_other: FailureAction
    replan_debounce_minutes: int
    chat_retention_days: int


class UserSettingsUpdate(BaseModel):
    """Mise à jour partielle. Pas d'heure de popup ni de notification de check-in (2026-10-17)."""

    model_config = ConfigDict(extra="forbid")

    bubble_enabled: bool | None = None
    notifications_enabled: bool | None = None
    notify_weekly_review: bool | None = None
    notify_mission_reminders: bool | None = None
    notify_red_alerts: bool | None = None
    morning_popup_enabled: bool | None = None
    ai_mode: AiMode | None = None
    replan_on_failure_urgent: FailureAction | None = None
    replan_on_failure_other: FailureAction | None = None
    replan_debounce_minutes: int | None = Field(default=None, ge=1, le=120)
    chat_retention_days: RetentionDays | None = None
