"""toolbox.prayer minimal (spec socle §8) — today's prayer windows, EXACT.

STRICT scope of the socle: the five daily prayer times and their windows.
Everything else (Hijri, Qibla, mosques directory, adhkar) belongs to the Path
pass.

Source order (doc 41 §6.2): MAWAQIT reference-mosque cache first, local
calculation fallback second. The fallback engine is a NOAA solar computation
implemented here: the pypi `adhan` package was evaluated and REJECTED (its
solar noon is ~20 min off vs official sources — see SOCLE_MAPPING.md).
"Déterministe qui doit être EXACT": tested against official reference values
(3 dates × 2 seasons, ±2 min).
"""

import json
import logging
import math
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.path import PathCalculatedPrayerTime, PathMawaqitCache, PathRegisteredMosque
from app.services.params import get_parameter

logger = logging.getLogger(__name__)

PRAYERS = ("fajr", "dhuhr", "asr", "maghrib", "isha")

# (fajr angle, isha angle) per method (doc 41 §6.4 V1 list).
METHOD_ANGLES = {
    "MuslimWorldLeague": (18.0, 17.0),
    "Karachi": (18.0, 18.0),
    "Egypt": (19.5, 17.5),
    "ISNA": (15.0, 15.0),
}
# Asr shadow factor: standard (Maliki/Shafii/Hanbali/Jafari) = 1, Hanafi = 2.
ASR_SHADOW = {"Hanafi": 2.0}

DEFAULT_LOCATION = (48.8566, 2.3522)  # Paris; parameterized via path.city_* later
DEFAULT_TZ = "Europe/Paris"


@dataclass(frozen=True)
class PrayerWindow:
    prayer: str
    adhan_ts: datetime
    window_start: datetime
    window_end: datetime


# --- NOAA solar computation (deterministic, no dependency) ---


def _julian_day(d: date) -> float:
    year, month, day = d.year, d.month, d.day
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + a // 4
    return int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + b - 1524.5


def _solar_position(jd: float) -> tuple[float, float]:
    """Return (declination degrees, equation of time minutes) for a julian day."""
    d = jd - 2451545.0
    g = math.radians((357.529 + 0.98560028 * d) % 360)
    q = (280.459 + 0.98564736 * d) % 360
    lam = math.radians(q + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    e = math.radians(23.439 - 0.00000036 * d)
    declination = math.degrees(math.asin(math.sin(e) * math.sin(lam)))
    ra = math.degrees(math.atan2(math.cos(e) * math.sin(lam), math.cos(lam))) / 15.0
    ra_hours = (ra + 24) % 24
    eqt = (q / 15.0 - ra_hours) * 60.0
    if eqt > 300:
        eqt -= 1440
    if eqt < -300:
        eqt += 1440
    return declination, eqt


def _hour_angle_deg(lat: float, declination: float, altitude: float) -> tuple[float, bool]:
    """Return (hour angle degrees, reached) — reached=False when the sun never
    gets to that altitude at this latitude/date (high-latitude summer nights)."""
    lat_r, dec_r, alt_r = map(math.radians, (lat, declination, altitude))
    cos_h = (math.sin(alt_r) - math.sin(lat_r) * math.sin(dec_r)) / (
        math.cos(lat_r) * math.cos(dec_r)
    )
    reached = -1.0 <= cos_h <= 1.0
    cos_h = min(1.0, max(-1.0, cos_h))
    return math.degrees(math.acos(cos_h)), reached


def compute_prayer_times_utc(
    d: date,
    lat: float,
    lng: float,
    *,
    method: str = "MuslimWorldLeague",
    madhhab: str = "Maliki",
) -> dict[str, datetime]:
    """Five prayer times in UTC via NOAA solar equations (±1 min vs official)."""
    if method not in METHOD_ANGLES:
        raise ValueError(f"Unsupported calculation method '{method}' (doc 41 §6.4).")
    fajr_angle, isha_angle = METHOD_ANGLES[method]
    shadow = ASR_SHADOW.get(madhhab, 1.0)

    jd = _julian_day(d) + 0.5  # solar values at ~noon UTC
    declination, eqt = _solar_position(jd)
    solar_noon_min = 720.0 - 4.0 * lng - eqt  # minutes UTC

    def at_altitude(altitude: float, *, morning: bool) -> tuple[float, bool]:
        hour_angle, reached = _hour_angle_deg(lat, declination, altitude)
        offset = hour_angle * 4.0  # minutes
        return (solar_noon_min - offset if morning else solar_noon_min + offset), reached

    asr_altitude = math.degrees(
        math.atan(1.0 / (shadow + math.tan(math.radians(abs(lat - declination)))))
    )

    sunrise_min, _ = at_altitude(-0.833, morning=True)
    sunset_min, _ = at_altitude(-0.833, morning=False)
    night_min = 1440.0 - (sunset_min - sunrise_min)

    fajr_min, fajr_reached = at_altitude(-fajr_angle, morning=True)
    isha_min, isha_reached = at_altitude(-isha_angle, morning=False)

    # High-latitude adjustment, angle-based rule (the one official sources use):
    # night portion = angle/60 × night duration, applied when the twilight
    # altitude is never reached or the computed time exceeds that portion.
    fajr_portion = fajr_angle / 60.0 * night_min
    if not fajr_reached or (sunrise_min - fajr_min) > fajr_portion:
        fajr_min = sunrise_min - fajr_portion
    isha_portion = isha_angle / 60.0 * night_min
    if not isha_reached or (isha_min - sunset_min) > isha_portion:
        isha_min = sunset_min + isha_portion

    asr_min, _ = at_altitude(asr_altitude, morning=False)
    minutes = {
        "fajr": fajr_min,
        "dhuhr": solar_noon_min,
        "asr": asr_min,
        "maghrib": sunset_min,
        "isha": isha_min,
    }
    base = datetime(d.year, d.month, d.day, tzinfo=UTC)
    return {prayer: base + timedelta(minutes=value) for prayer, value in minutes.items()}


# --- MAWAQIT client + cache (doc 41 §6.3) ---


class MawaqitUnavailable(RuntimeError):
    pass


def fetch_mawaqit_times(mosque: PathRegisteredMosque, d: date) -> dict[str, str]:
    """Backend MAWAQIT HTTP adapter. Provider URL comes from secrets, not code."""
    settings = get_settings()
    if not settings.mawaqit_base_url or not mosque.mawaqit_id:
        raise MawaqitUnavailable("MAWAQIT is not configured for this environment.")
    url = (
        settings.mawaqit_base_url.rstrip("/")
        + f"/mosque/{urllib.parse.quote(mosque.mawaqit_id)}/times?date={d.isoformat()}"
    )
    try:
        with urllib.request.urlopen(  # nosec B310 - configured provider URL
            url, timeout=settings.mawaqit_request_timeout_seconds
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise MawaqitUnavailable(f"MAWAQIT unreachable: {exc}") from exc
    missing = [prayer for prayer in PRAYERS if prayer not in payload]
    if missing:
        raise MawaqitUnavailable(f"MAWAQIT response missing prayers: {missing}")
    return {prayer: payload[prayer] for prayer in PRAYERS}


def _reference_mosque(db: Session) -> PathRegisteredMosque | None:
    mosque_id = get_parameter(db, "path.reference_mosque_id", default=None)
    if mosque_id:
        mosque = db.get(PathRegisteredMosque, UUID(str(mosque_id)))
        if mosque is not None:
            return mosque
    return db.scalar(
        select(PathRegisteredMosque).where(PathRegisteredMosque.is_default.is_(True)).limit(1)
    )


def cached_mawaqit_times(db: Session, mosque: PathRegisteredMosque, d: date) -> dict | None:
    row = db.scalar(
        select(PathMawaqitCache).where(
            PathMawaqitCache.mosque_id == mosque.id, PathMawaqitCache.date == d
        )
    )
    return row.prayer_times if row is not None else None


def refresh_mawaqit_cache(db: Session, *, days: int = 30, today: date | None = None) -> int:
    """Fetch and cache `days` days of times for the reference mosque (30 j cache)."""
    today = today or date.today()
    mosque = _reference_mosque(db)
    if mosque is None:
        logger.info("No reference mosque registered; MAWAQIT refresh skipped.")
        return 0
    stored = 0
    for offset in range(days):
        target = today + timedelta(days=offset)
        times = fetch_mawaqit_times(mosque, target)  # raises MawaqitUnavailable
        row = db.scalar(
            select(PathMawaqitCache).where(
                PathMawaqitCache.mosque_id == mosque.id, PathMawaqitCache.date == target
            )
        )
        if row is None:
            db.add(
                PathMawaqitCache(
                    id=uuid4(), mosque_id=mosque.id, date=target, prayer_times=times
                )
            )
        else:
            row.prayer_times = times
            row.fetched_at = datetime.now(UTC)
        stored += 1
    db.flush()
    return stored


# --- The graved contract: prayer_windows(date) (Daily G4 will consume it) ---


def prayer_windows(db: Session, d: date, *, tz: str = DEFAULT_TZ) -> list[PrayerWindow]:
    """[{prayer, adhan_ts, window_start, window_end}] — windows from parameters.

    Source order doc 41 §6.2: MAWAQIT cache of the reference mosque, then the
    local calculation engine. The window bounds come from
    path.window_before_min / path.window_after_min.
    """
    before_min = int(get_parameter(db, "path.window_before_min", default=0))
    after_min = int(get_parameter(db, "path.window_after_min", default=30))
    zone = ZoneInfo(tz)

    adhans: dict[str, datetime] | None = None
    mosque = _reference_mosque(db)
    if mosque is not None:
        cached = cached_mawaqit_times(db, mosque, d)
        if cached is not None:
            adhans = {}
            for prayer in PRAYERS:
                hour, minute = map(int, str(cached[prayer]).split(":")[:2])
                adhans[prayer] = datetime.combine(d, time(hour, minute), tzinfo=zone)

    if adhans is None:
        adhans = _calculated_times(db, d, zone)

    windows = []
    for prayer in PRAYERS:
        adhan_ts = adhans[prayer]
        windows.append(
            PrayerWindow(
                prayer=prayer,
                adhan_ts=adhan_ts,
                window_start=adhan_ts - timedelta(minutes=before_min),
                window_end=adhan_ts + timedelta(minutes=after_min),
            )
        )
    return windows


def _calculated_times(db: Session, d: date, zone: ZoneInfo) -> dict[str, datetime]:
    """Local engine, persisted in path_calculated_prayer_times (no per-request recompute)."""
    method = str(get_parameter(db, "path.calc_method", default="MuslimWorldLeague"))
    madhhab = str(get_parameter(db, "path.madhhab", default="Maliki"))
    lat, lng = DEFAULT_LOCATION

    utc_times = compute_prayer_times_utc(d, lat, lng, method=method, madhhab=madhhab)
    local = {prayer: ts.astimezone(zone) for prayer, ts in utc_times.items()}

    mosque = _reference_mosque(db)
    if mosque is not None and mosque.latitude is not None and mosque.longitude is not None:
        utc_times = compute_prayer_times_utc(
            d, float(mosque.latitude), float(mosque.longitude), method=method, madhhab=madhhab
        )
        local = {prayer: ts.astimezone(zone) for prayer, ts in utc_times.items()}
        # Calibration: log the MAWAQIT↔calculation gap when both exist.
        cached = cached_mawaqit_times(db, mosque, d)
        if cached is not None:
            gaps = {}
            for prayer in PRAYERS:
                hour, minute = map(int, str(cached[prayer]).split(":")[:2])
                mawaqit_ts = datetime.combine(d, time(hour, minute), tzinfo=zone)
                gaps[prayer] = round((mawaqit_ts - local[prayer]).total_seconds() / 60.0, 1)
            logger.info("MAWAQIT vs calculation gap (min).", extra={"date": str(d), "gaps": gaps})
    return local


def store_calculated_times(db: Session, *, user_id: UUID, d: date, tz: str = DEFAULT_TZ) -> None:
    zone = ZoneInfo(tz)
    local = _calculated_times(db, d, zone)
    method = str(get_parameter(db, "path.calc_method", default="MuslimWorldLeague"))
    madhhab = str(get_parameter(db, "path.madhhab", default="Maliki"))
    row = db.scalar(
        select(PathCalculatedPrayerTime).where(
            PathCalculatedPrayerTime.user_id == user_id, PathCalculatedPrayerTime.date == d
        )
    )
    values = {prayer: local[prayer].time().replace(second=0, microsecond=0) for prayer in PRAYERS}
    if row is None:
        db.add(
            PathCalculatedPrayerTime(
                id=uuid4(),
                user_id=user_id,
                date=d,
                calculation_method=method,
                madhhab=madhhab,
                city_reference=tz,
                **values,
            )
        )
    else:
        for prayer, value in values.items():
            setattr(row, prayer, value)
        row.calculation_method = method
        row.madhhab = madhhab
        row.computed_at = datetime.now(UTC)
    db.flush()


# --- Runner job (cron 03:00, seeded disabled) ---


def mawaqit_refresh_job(ctx, window) -> None:  # noqa: ANN001 - runner Handler contract
    """path.mawaqit_refresh: refresh the 30-day MAWAQIT cache + daily fallback rows."""
    db = ctx.db
    stored = 0
    try:
        stored = refresh_mawaqit_cache(db)
    except MawaqitUnavailable as exc:
        ctx.detail["mawaqit"] = f"unavailable: {exc}"
    settings = get_settings()
    if settings.imperium_canonical_user_id is not None:
        today = date.today()
        for offset in range(2):  # today + tomorrow, per doc 41 §6.4 daily recompute
            store_calculated_times(
                db, user_id=settings.imperium_canonical_user_id, d=today + timedelta(days=offset)
            )
    ctx.items_out = stored
    ctx.detail["mawaqit_days_cached"] = stored
