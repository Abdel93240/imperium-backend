"""Météo Vector (doc 33 §3, doc 57 §5.5) : relevés Open-Meteo, modèle Météo-France, centre de Paris.

Appel sortant autorisé par l'utilisateur pour les flux Vector (2026-10-22), sans clé. Le job
`vector.weather_refresh` (toutes les 15 min, semé éteint) garde un relevé : conditions actuelles et
12 prochaines heures. Aucun appel réseau pendant le scoring d'une course : la course lit le dernier
relevé. Un relevé de plus de 90 min est périmé : les variables météo restent vides (donnée manquante,
jamais une météo inventée).
"""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.rides import RidesWeatherReading
from app.schemas.rides import WeatherFeedRead, WeatherHour, WeatherNow

logger = logging.getLogger(__name__)

PARIS_CENTER = (48.8566, 2.3522)
URL = "https://api.open-meteo.com/v1/forecast"
CURRENT = "temperature_2m,precipitation,rain,snowfall,weather_code,wind_speed_10m,visibility"
HOURLY = "temperature_2m,precipitation_probability,precipitation,weather_code"
STALE_AFTER = timedelta(minutes=90)
KEEP = timedelta(days=7)
TIMEOUT_S = 10
# Codes WMO : neige 71-77 et 85-86 ; brouillard 45-48.
SNOW_CODES = set(range(71, 78)) | {85, 86}
FOG_CODES = {45, 48}


class WeatherUnavailableError(RuntimeError):
    pass


def fetch(latitude: float, longitude: float) -> dict:
    query = urllib.parse.urlencode({
        "latitude": latitude, "longitude": longitude, "current": CURRENT, "hourly": HOURLY, "forecast_hours": 12,
        "timezone": "Europe/Paris", "models": "meteofrance_seamless",
    })
    try:
        with urllib.request.urlopen(f"{URL}?{query}", timeout=TIMEOUT_S) as response:  # nosec B310 - URL fixe
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise WeatherUnavailableError(f"Open-Meteo injoignable : {exc}") from exc


def refresh(db: Session, *, now: datetime | None = None, fetcher=fetch) -> RidesWeatherReading:
    now = now or datetime.now(UTC)
    latitude, longitude = PARIS_CENTER
    body = fetcher(latitude, longitude)
    current, hourly = body.get("current"), body.get("hourly")
    if not isinstance(current, dict) or not isinstance(hourly, dict):
        raise WeatherUnavailableError("Réponse Open-Meteo incomplète.")
    reading = RidesWeatherReading(id=uuid4(), fetched_at=now, latitude=latitude, longitude=longitude, current=current,
                                  hourly=hourly, source="open-meteo")
    db.add(reading)
    db.execute(delete(RidesWeatherReading).where(RidesWeatherReading.fetched_at < now - KEEP))
    db.flush()
    return reading


def latest(db: Session) -> RidesWeatherReading | None:
    return db.scalar(select(RidesWeatherReading).order_by(RidesWeatherReading.fetched_at.desc()).limit(1))


def offer_features(db: Session, at: datetime) -> dict:
    """Variables météo d'une course (doc 57 §5.5) ; vides si aucun relevé frais à l'heure de l'offre."""
    empty = {"weather_temp_c": None, "weather_precip_mm": None, "weather_code": None, "weather_wind_kmh": None,
             "weather_visibility_km": None, "weather_is_rain": None, "weather_is_snow": None, "weather_is_fog": None,
             "weather_rain_next_hour_pct": None}
    reading = db.scalar(
        select(RidesWeatherReading).where(RidesWeatherReading.fetched_at <= at + timedelta(minutes=5))
        .order_by(RidesWeatherReading.fetched_at.desc()).limit(1)
    )
    if reading is None or reading.fetched_at < at - STALE_AFTER:
        return empty
    now = reading.current
    precip, code, visibility = now.get("precipitation"), now.get("weather_code"), now.get("visibility")
    probabilities = reading.hourly.get("precipitation_probability") or []
    return {
        "weather_temp_c": now.get("temperature_2m"),
        "weather_precip_mm": precip,
        "weather_code": code,
        "weather_wind_kmh": now.get("wind_speed_10m"),
        "weather_visibility_km": round(visibility / 1000, 1) if isinstance(visibility, (int, float)) else None,
        "weather_is_rain": precip > 0.1 and code not in SNOW_CODES if isinstance(precip, (int, float)) else None,
        "weather_is_snow": code in SNOW_CODES if isinstance(code, int) else None,
        "weather_is_fog": code in FOG_CODES if isinstance(code, int) else None,
        "weather_rain_next_hour_pct": probabilities[0] if probabilities else None,
    }


def feed(db: Session, *, now: datetime | None = None) -> WeatherFeedRead:
    now = now or datetime.now(UTC)
    reading = latest(db)
    if reading is None:
        return WeatherFeedRead(status="unavailable", message="Aucun relevé : le flux météo n'est pas encore activé.")
    stale = reading.fetched_at < now - STALE_AFTER
    cur, hourly = reading.current, reading.hourly
    hours = [
        WeatherHour(time=time, temperature_c=_at(hourly, "temperature_2m", i), precipitation_mm=_at(hourly, "precipitation", i),
                    precipitation_probability=_at(hourly, "precipitation_probability", i),
                    weather_code=_at(hourly, "weather_code", i))
        for i, time in enumerate(hourly.get("time") or [])
    ]
    return WeatherFeedRead(
        status="stale" if stale else "ok", fetched_at=reading.fetched_at,
        message="Dernier relevé de plus de 90 min : à prendre avec prudence." if stale else None,
        now=WeatherNow(temperature_c=cur.get("temperature_2m"), precipitation_mm=cur.get("precipitation"),
                       weather_code=cur.get("weather_code"), wind_kmh=cur.get("wind_speed_10m")),
        hours=hours,
    )


def _at(hourly: dict, key: str, index: int):
    values = hourly.get(key) or []
    return values[index] if index < len(values) else None


def weather_refresh_job(ctx, window) -> None:  # noqa: ARG001 - signature du runner
    try:
        reading = refresh(ctx.db)
        ctx.db.commit()
    except WeatherUnavailableError as exc:
        ctx.db.rollback()
        logger.warning("vector.weather_refresh: %s", exc)
        ctx.items_in = ctx.items_out = 0
        ctx.detail = {"error": str(exc)}
        return
    ctx.items_in = ctx.items_out = 1
    ctx.detail = {"fetched_at": reading.fetched_at.isoformat()}
