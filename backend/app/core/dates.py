from datetime import date, datetime
from zoneinfo import ZoneInfo


DEFAULT_LOCAL_TIMEZONE = "Europe/Paris"


def get_default_local_date() -> date:
    return datetime.now(ZoneInfo(DEFAULT_LOCAL_TIMEZONE)).date()
