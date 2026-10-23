"""Règle économique de Vector (décision utilisateur 2026-10-23) : €/h global et note de la zone d'arrivée.

1. €/h global = prix ÷ (minutes d'approche + minutes de course) × 60.
2. La zone d'arrivée est notée (0 à 10) au moment où la course se termine :
   - note posée par l'utilisateur (`rides_zone_scores` : code postal puis département, créneau puis « all ») ;
   - sinon note par défaut ci-dessous (point de départ, à corriger et à remplacer par l'historique) ;
   - + 2 si un événement finit près de l'arrivée dans l'heure de la fin de course, + 1 s'il y pleut.
3. Zone excellente (≥ 8) → vert, même sous le seuil ; zone mauvaise (< 4) → le temps de repositionnement vers la zone
   correcte (≥ 6) la plus proche s'ajoute avant de calculer le €/h.
4. Vert si le €/h obtenu atteint le seuil (25 €/h), rouge en dessous. Sans durée de course lue : aucun avis.
Paramètres : `vector.economic_rule`.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rides import RidesEventSignal, RidesZoneScore
from app.services.params import get_parameter
from app.services.vector import geo, weather

PARIS = ZoneInfo("Europe/Paris")
DEFAULT_RULE = {"min_hourly_eur": 25, "excellent_zone": 8, "bad_zone": 4, "good_zone": 6, "reposition_speed_kmh": 30,
                "reposition_extra_min": 5}
BLOCKS = ("night", "morning", "daytime", "evening", "late_evening")
# Notes par défaut (nuit, matin, journée, soirée, fin de soirée) : un point de départ, pas une vérité.
DEFAULTS = {
    "paris": (7, 7, 6, 8, 8),
    "airport": (4, 8, 7, 8, 7),
    "defense": (3, 7, 7, 7, 5),
    "92": (4, 6, 6, 6, 5),
    "93": (3, 5, 5, 5, 4),
    "94": (3, 5, 5, 5, 4),
    "far": (2, 3, 3, 3, 2),  # grande couronne
    "outside": (1, 2, 2, 2, 1),
}
AIRPORT_CODES = {"95700", "93290", "94390", "94310", "60000"}
DEFENSE_CODES = {"92800", "92400", "92060"}  # Puteaux, Courbevoie, La Défense
# Zones correctes possibles pour se repositionner : centres des arrondissements et aéroports.
REPOSITION_TARGETS = [*(f"750{n:02d}" for n in range(1, 21)), "95700", "94390"]


@dataclass
class ZoneScore:
    score: float
    source: str  # user | default
    reasons: list[str] = field(default_factory=list)


@dataclass
class Verdict:
    signal: str | None
    reason: str
    features: dict


def rule(db: Session) -> dict:
    return {**DEFAULT_RULE, **(get_parameter(db, "vector.economic_rule", default={}) or {})}


def time_block(at: datetime) -> str:
    hour = at.astimezone(PARIS).hour
    return "night" if hour < 6 else "morning" if hour < 10 else "daytime" if hour < 16 else "evening" if hour < 20 \
        else "late_evening"


def _area(postal_code: str | None, department: str | None) -> str:
    if postal_code in AIRPORT_CODES:
        return "airport"
    if postal_code in DEFENSE_CODES:
        return "defense"
    dep = (postal_code or "")[:2] or (department or "")
    if dep == "75":
        return "paris"
    if dep in ("92", "93", "94"):
        return dep
    if dep in ("77", "78", "91", "95"):
        return "far"
    return "outside"


def base_score(db: Session, place: geo.Place, block: str) -> ZoneScore:
    keys = [k for k in (place.postal_code, place.department) if k]
    rows = {(row.zone_key, row.time_block): row for row in db.scalars(
        select(RidesZoneScore).where(RidesZoneScore.zone_key.in_(keys), RidesZoneScore.time_block.in_((block, "all"))))}
    for key in keys:
        for when in (block, "all"):
            if (row := rows.get((key, when))) is not None:
                return ZoneScore(float(row.score), "user", [f"note posée {float(row.score):g}/10"])
    score = DEFAULTS[_area(place.postal_code, place.department)][BLOCKS.index(block)]
    return ZoneScore(float(score), "default", [f"note par défaut {score}/10"])


def zone_score(db: Session, place: geo.Place, end_at: datetime, now_at: datetime) -> ZoneScore:
    block = time_block(end_at)
    scored = base_score(db, place, block)
    if place.postal_code and db.scalar(select(RidesEventSignal.id).where(
        RidesEventSignal.kind == "event", RidesEventSignal.postal_code == place.postal_code,
        RidesEventSignal.ends_at.between(end_at - timedelta(minutes=30), end_at + timedelta(minutes=60)),
    ).limit(1)) is not None:
        scored.score += 2
        scored.reasons.append("événement qui finit près de l'arrivée")
    # Pluie relevée au moment de l'offre (maintenant et dans l'heure) sur la case d'arrivée.
    rain = weather.offer_features(db, now_at, lat=None, lng=None, dest=(place.lat, place.lng))
    if rain.get("weather_dest_is_rain") or (rain.get("weather_dest_rain_next_60min_mm") or 0) >= 0.5:
        scored.score += 1
        scored.reasons.append("pluie à l'arrivée")
    scored.score = min(10.0, scored.score)
    return scored


def reposition_minutes(db: Session, place: geo.Place, end_at: datetime, params: dict) -> int:
    """Temps pour rejoindre la zone correcte la plus proche (vol d'oiseau à la vitesse du paramètre, plus une marge)."""
    block = time_block(end_at)
    best = None
    for code in REPOSITION_TARGETS:
        target = geo.resolve(code)
        if target is None or base_score(db, target, block).score < params["good_zone"]:
            continue
        km = _km(place.lat, place.lng, target.lat, target.lng)
        best = km if best is None else min(best, km)
    if best is None:
        return 0
    return round(best / params["reposition_speed_kmh"] * 60 + params["reposition_extra_min"])


def verdict(db: Session, *, price_cents: int, approach_min: int | None, trip_min: int | None,
            destination: geo.Place | None, offered_at: datetime) -> Verdict:
    params = rule(db)
    if not trip_min:
        return Verdict(None, "Durée de course non lue : à toi de juger.", {"economic_signal": None})
    approach = approach_min or 0
    end_at = offered_at + timedelta(minutes=approach + trip_min)
    base = price_cents / 100 / ((approach + trip_min) / 60)
    features = {"hourly_global_eur": round(base, 1), "ride_end_block": time_block(end_at)}
    threshold = params["min_hourly_eur"]
    if destination is None:
        signal = "green" if base >= threshold else "red"
        features.update({"dest_zone_score": None, "reposition_min": None, "hourly_effective_eur": round(base, 1),
                         "economic_signal": signal})
        return Verdict(signal, f"{base:.0f} €/h global (zone d'arrivée inconnue).", features)
    scored = zone_score(db, destination, end_at, offered_at)
    features.update({"dest_zone_score": scored.score, "dest_zone_score_source": scored.source,
                     "dest_zone_reasons": scored.reasons})
    if scored.score >= params["excellent_zone"]:
        features.update({"reposition_min": 0, "hourly_effective_eur": round(base, 1), "economic_signal": "green"})
        return Verdict("green", f"{base:.0f} €/h global, arrivée en zone excellente ({scored.score:g}/10 : "
                                f"{', '.join(scored.reasons)}).", features)
    reposition = reposition_minutes(db, destination, end_at, params) if scored.score < params["bad_zone"] else 0
    effective = price_cents / 100 / ((approach + trip_min + reposition) / 60)
    signal = "green" if effective >= threshold else "red"
    features.update({"reposition_min": reposition, "hourly_effective_eur": round(effective, 1), "economic_signal": signal})
    detail = (f"{effective:.0f} €/h avec {reposition} min pour se repositionner (zone {scored.score:g}/10)"
              if reposition else f"{effective:.0f} €/h global, zone d'arrivée {scored.score:g}/10")
    return Verdict(signal, detail + ".", features)


def _km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    dlat, dlng = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))
