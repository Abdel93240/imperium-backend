"""Validation des réglages (doc 43 §15) — tests unitaires."""
import pytest
from pydantic import ValidationError

from app.schemas.settings import UserSettingsUpdate


@pytest.mark.parametrize("mode", ["strict", "equilibre", "souple"])
def test_three_ai_modes(mode) -> None:
    assert UserSettingsUpdate(ai_mode=mode).ai_mode == mode


@pytest.mark.parametrize(
    "kwargs",
    [
        {"ai_mode": "turbo"},
        {"chat_retention_days": 45},
        {"replan_debounce_minutes": 0},
        {"replan_debounce_minutes": 121},
        {"replan_on_failure_urgent": "always"},
        {"morning_popup_time": "06:30"},  # supprimé le 2026-10-17
        {"notify_morning_checkin": True},  # supprimé le 2026-10-17
    ],
)
def test_invalid_or_removed_settings_are_rejected(kwargs) -> None:
    with pytest.raises(ValidationError):
        UserSettingsUpdate(**kwargs)


@pytest.mark.parametrize("days", [30, 60, 90, 180, 365])
def test_retention_choices(days) -> None:
    assert UserSettingsUpdate(chat_retention_days=days).chat_retention_days == days


def test_settings_routes_are_registered() -> None:
    from app.api.v1.router import api_router

    paths = {(route.path, method) for route in api_router.routes for method in getattr(route, "methods", set())}
    assert ("/imperium/settings", "GET") in paths and ("/imperium/settings", "PATCH") in paths
