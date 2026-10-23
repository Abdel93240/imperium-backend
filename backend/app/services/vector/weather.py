"""Météo Vector en grille (doc 33 §3, doc 57 §5.5 et §17) : où il pleut, quartier par quartier, au quart d'heure.

Une averse couvre quelques kilomètres : un seul point au centre de Paris donne la tendance du jour, pas la zone où
la demande (et la majoration) monte. La région est découpée en cases :
- A : Paris et petite couronne, ~3 km ;
- B : reste de l'Île-de-France, ~10 km ;
- aéroports : Roissy-CDG, Orly, Beauvais.

Source : Open-Meteo (modèle Météo-France), offre gratuite, choix de l'utilisateur (2026-10-23). Toutes les cases en
une passe (requêtes de 100 points), pluie au quart d'heure (2 passés, 8 à venir). Le job `vector.weather_refresh`
(toutes les 30 min, semé éteint) n'appelle QUE pendant une session VTC ouverte : environ 3 700 appels pour 10 h.
Les relevés sont gardés (données d'apprentissage, doc 57 §17.8). Sans relevé frais, rien n'est supposé.
"""

import json
import logging
import math
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.rides import RidesSession, RidesWeatherCellReading
from app.schemas.rides import WeatherFeedRead, WeatherHour, WeatherNow

logger = logging.getLogger(__name__)

PARIS = ZoneInfo("Europe/Paris")
URL = "https://api.open-meteo.com/v1/forecast"
CURRENT = "temperature_2m,precipitation,weather_code,wind_speed_10m"
MINUTELY = "precipitation,weather_code"
BATCH = 100
STALE_AFTER = timedelta(minutes=45)
TIMEOUT_S = 20
RAIN_MM = 0.1  # par quart d'heure
SNOW_CODES = set(range(71, 78)) | {85, 86}
FOG_CODES = {45, 48}
CENTER_CELL = "AP-PARIS"


@dataclass(frozen=True)
class Cell:
    code: str
    ring: str  # A | B | airport
    lat: float
    lng: float


def _grid(ring: str, lat0: float, lat1: float, lng0: float, lng1: float, km: float) -> list[Cell]:
    step_lat = km / 111.0
    step_lng = km / (111.0 * math.cos(math.radians((lat0 + lat1) / 2)))
    rows = max(1, round((lat1 - lat0) / step_lat))
    cols = max(1, round((lng1 - lng0) / step_lng))
    return [
        Cell(f"{ring}-{r:02d}-{c:02d}", ring, round(lat0 + (r + 0.5) * (lat1 - lat0) / rows, 4),
             round(lng0 + (c + 0.5) * (lng1 - lng0) / cols, 4))
        for r in range(rows) for c in range(cols)
    ]


# Paris + petite couronne (A, ~3 km) ; Île-de-France (B, ~10 km) sans les cases déjà couvertes par A.
_A_BOX = (48.73, 48.95, 2.20, 2.56)


@lru_cache(maxsize=1)
def cells() -> tuple[Cell, ...]:
    inner = _grid("A", *_A_BOX, km=3)
    lat0, lat1, lng0, lng1 = _A_BOX
    outer = [c for c in _grid("B", 48.30, 49.20, 1.65, 3.35, km=10)
             if not (lat0 <= c.lat <= lat1 and lng0 <= c.lng <= lng1)]
    airports = [Cell("AP-CDG", "airport", 49.0097, 2.5479), Cell("AP-ORY", "airport", 48.7262, 2.3652),
                Cell("AP-BVA", "airport", 49.4544, 2.1128), Cell(CENTER_CELL, "airport", 48.8566, 2.3522)]
    return tuple(inner + outer + airports)


def cell_at(lat: float, lng: float) -> Cell:
    """Case la plus proche d'une position (le centre de Paris ne sert que de référence régionale)."""
    k = math.cos(math.radians(lat))
    return min((c for c in cells() if c.code != CENTER_CELL), key=lambda c: (c.lat - lat) ** 2 + ((c.lng - lng) * k) ** 2)


class WeatherUnavailableError(RuntimeError):
    pass


def fetch(batch: list[Cell]) -> list[dict]:
    query = urllib.parse.urlencode({
        "latitude": ",".join(str(c.lat) for c in batch), "longitude": ",".join(str(c.lng) for c in batch),
        "current": CURRENT, "minutely_15": MINUTELY, "past_minutely_15": 2, "forecast_minutely_15": 8,
        "timezone": "Europe/Paris", "models": "meteofrance_seamless",
    })
    try:
        with urllib.request.urlopen(f"{URL}?{query}", timeout=TIMEOUT_S) as response:  # nosec B310 - URL fixe
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise WeatherUnavailableError(f"Open-Meteo injoignable : {exc}") from exc
    body = body if isinstance(body, list) else [body]
    if len(body) != len(batch):
        raise WeatherUnavailableError("Réponse Open-Meteo incomplète.")
    return body


def session_open(db: Session) -> bool:
    return bool(db.scalar(select(func.count()).select_from(RidesSession).where(RidesSession.status.in_(("active", "paused")))))


def refresh(db: Session, *, now: datetime | None = None, fetcher=None) -> int:
    """Une passe sur toutes les cases ; renvoie le nombre de cases relevées."""
    now = now or datetime.now(UTC)
    fetcher = fetcher or fetch
    grid = list(cells())
    rows = []
    for start in range(0, len(grid), BATCH):
        batch = grid[start:start + BATCH]
        for cell, body in zip(batch, fetcher(batch), strict=True):
            current, minutely = body.get("current"), body.get("minutely_15")
            if not isinstance(current, dict) or not isinstance(minutely, dict):
                raise WeatherUnavailableError("Réponse Open-Meteo incomplète.")
            rows.append(RidesWeatherCellReading(id=uuid4(), fetched_at=now, cell_code=cell.code, ring=cell.ring,
                                                latitude=cell.lat, longitude=cell.lng, current=current, minutely=minutely))
    db.add_all(rows)
    db.flush()
    return len(rows)


def _latest_at(db: Session, at: datetime) -> dict[str, RidesWeatherCellReading]:
    """Dernière passe complète faite avant `at` (au plus 45 min avant), par case."""
    fetched = db.scalar(select(func.max(RidesWeatherCellReading.fetched_at))
                        .where(RidesWeatherCellReading.fetched_at <= at + timedelta(minutes=5)))
    if fetched is None or fetched < at - STALE_AFTER:
        return {}
    rows = db.scalars(select(RidesWeatherCellReading).where(RidesWeatherCellReading.fetched_at == fetched))
    return {row.cell_code: row for row in rows}


def _quarters(row: RidesWeatherCellReading, at: datetime) -> tuple[list[float], list[float]]:
    """Pluie des quarts d'heure passés (avant `at`) et à venir (à partir de `at`), en mm."""
    local = at.astimezone(PARIS).replace(tzinfo=None)
    past, future = [], []
    for time, mm in zip(row.minutely.get("time") or [], row.minutely.get("precipitation") or [], strict=False):
        if mm is None:
            continue
        start = datetime.fromisoformat(time)
        (past if start + timedelta(minutes=15) <= local else future).append(mm)
    return past, future


def _cell_features(prefix: str, row: RidesWeatherCellReading | None, at: datetime) -> dict:
    if row is None:
        return {f"{prefix}_{k}": None for k in ("cell", "precip_mm", "is_rain", "rain_last_30min", "rain_onset",
                                                "rain_next_60min_mm", "is_snow", "temp_c")}
    past, future = _quarters(row, at)
    now_mm = row.current.get("precipitation")
    code = row.current.get("weather_code")
    raining = now_mm is not None and now_mm >= RAIN_MM
    rained = any(mm >= RAIN_MM for mm in past[-2:])
    return {
        f"{prefix}_cell": row.cell_code,
        f"{prefix}_precip_mm": now_mm,
        f"{prefix}_is_rain": raining,
        f"{prefix}_rain_last_30min": rained,
        # Début d'averse : sec sur la dernière demi-heure, pluie maintenant ou au prochain quart d'heure.
        f"{prefix}_rain_onset": not rained and (raining or any(mm >= RAIN_MM for mm in future[:1])),
        f"{prefix}_rain_next_60min_mm": round(sum(future[:4]), 2) if future else None,
        f"{prefix}_is_snow": code in SNOW_CODES if isinstance(code, int) else None,
        f"{prefix}_temp_c": row.current.get("temperature_2m"),
    }


def offer_features(db: Session, at: datetime, *, lat: float | None, lng: float | None) -> dict:
    """Météo d'une offre : case de la tablette (prise en charge), Paris centre, part des cases sous la pluie."""
    readings = _latest_at(db, at)
    pickup = readings.get(cell_at(lat, lng).code) if readings and lat is not None and lng is not None else None
    center = readings.get(CENTER_CELL)
    features = {**_cell_features("weather_pickup", pickup, at), **_cell_features("weather_paris", center, at)}
    for ring, key in (("A", "weather_rain_share_paris"), ("B", "weather_rain_share_idf")):
        ring_rows = [r for r in readings.values() if r.ring == ring]
        features[key] = (round(sum(1 for r in ring_rows if (r.current.get("precipitation") or 0) >= RAIN_MM) / len(ring_rows), 3)
                         if ring_rows else None)
    features["weather_wind_kmh"] = center.current.get("wind_speed_10m") if center else None
    code = center.current.get("weather_code") if center else None
    features["weather_is_fog"] = code in FOG_CODES if isinstance(code, int) else None
    return features


def feed(db: Session, *, now: datetime | None = None) -> WeatherFeedRead:
    now = now or datetime.now(UTC)
    fetched = db.scalar(select(func.max(RidesWeatherCellReading.fetched_at)))
    if fetched is None:
        return WeatherFeedRead(status="unavailable", message="Aucun relevé : la météo est relevée pendant les sessions VTC.")
    readings = {r.cell_code: r for r in db.scalars(select(RidesWeatherCellReading)
                                                 .where(RidesWeatherCellReading.fetched_at == fetched))}
    center = readings.get(CENTER_CELL)
    stale = fetched < now - STALE_AFTER
    inner = [r for r in readings.values() if r.ring == "A"]
    raining = [r for r in inner if (r.current.get("precipitation") or 0) >= RAIN_MM]
    hours = []
    if center:
        for time, mm, code in zip(center.minutely.get("time") or [], center.minutely.get("precipitation") or [],
                                  center.minutely.get("weather_code") or [], strict=False):
            hours.append(WeatherHour(time=time, precipitation_mm=mm, weather_code=code))
    return WeatherFeedRead(
        status="stale" if stale else "ok", fetched_at=fetched,
        message="Dernier relevé de plus de 45 min (hors session, la météo n'est pas relevée)." if stale else None,
        now=WeatherNow(temperature_c=center.current.get("temperature_2m"), precipitation_mm=center.current.get("precipitation"),
                       weather_code=center.current.get("weather_code"), wind_kmh=center.current.get("wind_speed_10m"))
        if center else None,
        hours=hours, cells=len(readings), raining_cells_paris=len(raining), cells_paris=len(inner),
    )


def weather_refresh_job(ctx, window) -> None:  # noqa: ARG001 - signature du runner
    if not session_open(ctx.db):
        ctx.items_in = ctx.items_out = 0
        ctx.detail = {"skipped": "no_open_session"}  # hors session VTC : aucun appel
        return
    try:
        count = refresh(ctx.db)
        ctx.db.commit()
    except WeatherUnavailableError as exc:
        ctx.db.rollback()
        logger.warning("vector.weather_refresh: %s", exc)
        ctx.items_in = ctx.items_out = 0
        ctx.detail = {"error": str(exc)}
        return
    ctx.items_in = ctx.items_out = count
    ctx.detail = {"cells": count}
