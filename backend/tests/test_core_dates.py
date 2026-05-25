from datetime import date
from zoneinfo import ZoneInfo

from app.core import dates


def test_get_default_local_date_uses_europe_paris_timezone(monkeypatch) -> None:
    seen = {}

    class FixedDateTime:
        @classmethod
        def now(cls, tz: ZoneInfo):
            seen["timezone"] = tz
            return type("FixedNow", (), {"date": lambda self: date(2026, 5, 26)})()

    monkeypatch.setattr(dates, "datetime", FixedDateTime)

    assert dates.get_default_local_date() == date(2026, 5, 26)
    assert seen["timezone"].key == "Europe/Paris"
