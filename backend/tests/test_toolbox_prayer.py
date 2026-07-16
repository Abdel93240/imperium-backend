"""§13.8 prayer: MAWAQIT cache, ±2 min fallback vs official references
(3 dates × 2 seasons), correct windows. « Déterministe qui doit être EXACT »."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, text

from _postgres import require_test_database_url

pytest.importorskip("psycopg")

from sqlalchemy.orm import Session  # noqa: E402

from app.models import ai, auth, event, idempotency, imperium, path, toolbox, vault  # noqa: E402,F401
from app.models.path import PathMawaqitCache, PathRegisteredMosque  # noqa: E402
from app.services.path.prayer import (  # noqa: E402
    PRAYERS,
    compute_prayer_times_utc,
    prayer_windows,
)

PARIS = (48.8566, 2.3522)
TZ = ZoneInfo("Europe/Paris")

# Official reference values (AlAdhan, method=MuslimWorldLeague, school=standard,
# Paris) — 3 dates × 2 seasons (winter, high-latitude summer, autumn).
OFFICIAL_REFERENCES = {
    date(2026, 1, 15): {
        "fajr": "06:46",
        "dhuhr": "13:00",
        "asr": "15:01",
        "maghrib": "17:22",
        "isha": "19:08",
    },
    date(2026, 7, 15): {
        "fajr": "03:35",
        "dhuhr": "13:57",
        "asr": "18:10",
        "maghrib": "21:50",
        "isha": "00:09",
    },
    date(2026, 10, 1): {
        "fajr": "06:04",
        "dhuhr": "13:40",
        "asr": "16:51",
        "maghrib": "19:30",
        "isha": "21:09",
    },
}


@pytest.fixture(scope="module")
def engine():
    engine = create_engine(require_test_database_url("toolbox prayer tests"), future=True)
    yield engine
    engine.dispose()


@pytest.mark.parametrize("target_date", sorted(OFFICIAL_REFERENCES))
def test_fallback_engine_within_2_minutes_of_official_source(target_date) -> None:
    computed = compute_prayer_times_utc(target_date, *PARIS)
    for prayer, expected in OFFICIAL_REFERENCES[target_date].items():
        local = computed[prayer].astimezone(TZ)
        expected_hour, expected_minute = map(int, expected.split(":"))
        got_minutes = local.hour * 60 + local.minute
        expected_minutes = expected_hour * 60 + expected_minute
        diff = abs(got_minutes - expected_minutes)
        diff = min(diff, 1440 - diff)  # isha may cross midnight
        assert diff <= 2, f"{target_date} {prayer}: {local:%H:%M} vs {expected} ({diff} min)"


def test_hanafi_asr_is_later_than_standard() -> None:
    standard = compute_prayer_times_utc(date(2026, 7, 15), *PARIS, madhhab="Maliki")
    hanafi = compute_prayer_times_utc(date(2026, 7, 15), *PARIS, madhhab="Hanafi")
    assert hanafi["asr"] > standard["asr"]
    assert standard["dhuhr"] == hanafi["dhuhr"]


def test_unsupported_method_is_rejected() -> None:
    with pytest.raises(ValueError, match="doc 41"):
        compute_prayer_times_utc(date(2026, 7, 15), *PARIS, method="Invented")


def test_prayer_windows_uses_mawaqit_cache_first_then_parameters(engine) -> None:
    target = date(2026, 7, 16)
    user_id = uuid4()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                "VALUES (:id, :email, FALSE, now(), now())"
            ),
            {"id": str(user_id), "email": f"prayer-{user_id}@example.test"},
        )
    with Session(engine) as db:
        mosque = PathRegisteredMosque(
            id=uuid4(),
            user_id=user_id,
            mawaqit_id="mosquee-de-test",
            name="Mosquée de test",
            is_default=True,
        )
        db.add(mosque)
        db.flush()
        # MAWAQIT gives 18:18 while the local engine would say otherwise (doc 41
        # §6.1 use case: the mosque's real time wins).
        db.add(
            PathMawaqitCache(
                id=uuid4(),
                mosque_id=mosque.id,
                date=target,
                prayer_times={
                    "fajr": "03:36",
                    "dhuhr": "13:57",
                    "asr": "18:18",
                    "maghrib": "21:50",
                    "isha": "23:15",
                },
            )
        )
        db.flush()

        windows = prayer_windows(db, target)
        by_prayer = {window.prayer: window for window in windows}
        assert [window.prayer for window in windows] == list(PRAYERS)
        assert by_prayer["asr"].adhan_ts.astimezone(TZ).strftime("%H:%M") == "18:18"
        # Windows come from path.window_before_min (0) / after_min (30).
        for window in windows:
            assert window.window_start == window.adhan_ts
            assert window.window_end == window.adhan_ts + timedelta(minutes=30)
        db.rollback()


def test_prayer_windows_falls_back_to_calculation_without_mawaqit(engine) -> None:
    target = date(2026, 10, 1)
    with Session(engine) as db:
        windows = prayer_windows(db, target)
        by_prayer = {window.prayer: window for window in windows}
        # Fallback = local engine (±2 min vs official 19:30 maghrib).
        maghrib_local = by_prayer["maghrib"].adhan_ts.astimezone(TZ)
        assert maghrib_local.strftime("%H:%M") in {"19:28", "19:29", "19:30", "19:31", "19:32"}
        db.rollback()
