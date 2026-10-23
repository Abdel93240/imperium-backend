"""Découpage fin de Vector (décision utilisateur 2026-10-23) : zones et créneaux de 10 minutes.

Zones (cases carrées sur une projection locale autour de Paris) :
- Paris : 1 km² (côté 1 km) ;
- villes (commune la plus proche à 1 000 habitants/km² ou plus) : 3 km² (côté ≈ 1,73 km) ;
- campagne : 10 km² (côté ≈ 3,16 km) ;
- aéroports (4 km autour de Roissy-CDG, Orly, Beauvais) : 1 km².
La densité vient de la liste officielle des communes (geo.api.gouv.fr, population ÷ surface) ; le type d'une position
est celui de la commune dont le centre est le plus proche (approximation aux limites de communes). Un identifiant de
case ressemble à « P:3:-2 » (type, colonne, ligne) et reste stable : c'est la clé des mesures et du modèle.

Créneaux : 10 minutes, 144 par jour (0 = 00:00–00:10, heure de Paris), et un type de jour : semaine, samedi,
dimanche, férié (vacances scolaires à part, variable distincte).
"""

import math
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.vector import calendar, geo

PARIS = ZoneInfo("Europe/Paris")
ORIGIN = (48.8566, 2.3522)
KM_PER_DEG_LAT = 110.574
KM_PER_DEG_LNG = 111.320 * math.cos(math.radians(ORIGIN[0]))
URBAN_DENSITY = 1000  # habitants/km²
SIDES = {"P": 1.0, "A": 1.0, "V": math.sqrt(3), "C": math.sqrt(10)}  # Paris, aéroport, ville, campagne : côté en km
AIRPORTS = ((49.0097, 2.5479), (48.7262, 2.3652), (49.4544, 2.1128))  # Roissy-CDG, Orly, Beauvais
AIRPORT_RADIUS_KM = 4.0  # zone aéroport fine (1 km²) autour des terminaux
PARIS_BOX = (48.815, 48.902, 2.224, 2.470)  # Paris intra-muros (bois compris)


@dataclass(frozen=True)
class Zone:
    code: str
    kind: str  # P | A | V | C
    lat: float  # centre de la case
    lng: float


def kind_at(lat: float, lng: float) -> str:
    for a_lat, a_lng in AIRPORTS:
        if math.hypot((lat - a_lat) * KM_PER_DEG_LAT, (lng - a_lng) * KM_PER_DEG_LNG) <= AIRPORT_RADIUS_KM:
            return "A"
    lat0, lat1, lng0, lng1 = PARIS_BOX
    k = math.cos(math.radians(lat))
    nearest = min(geo.densities(), key=lambda c: (c[0] - lat) ** 2 + ((c[1] - lng) * k) ** 2)
    if lat0 <= lat <= lat1 and lng0 <= lng <= lng1 and nearest[2] >= 20000:
        return "P"
    return "V" if nearest[2] >= URBAN_DENSITY else "C"


def zone_at(lat: float, lng: float) -> Zone:
    kind = kind_at(lat, lng)
    side = SIDES[kind]
    x = (lng - ORIGIN[1]) * KM_PER_DEG_LNG
    y = (lat - ORIGIN[0]) * KM_PER_DEG_LAT
    col, row = math.floor(x / side), math.floor(y / side)
    center_lat = ORIGIN[0] + (row + 0.5) * side / KM_PER_DEG_LAT
    center_lng = ORIGIN[1] + (col + 0.5) * side / KM_PER_DEG_LNG
    return Zone(f"{kind}:{col}:{row}", kind, round(center_lat, 5), round(center_lng, 5))


def slot_of(at: datetime) -> int:
    local = at.astimezone(PARIS)
    return local.hour * 6 + local.minute // 10


def day_type(at: datetime) -> str:
    day = at.astimezone(PARIS).date()
    if calendar.is_public_holiday(day):
        return "holiday"
    return {5: "saturday", 6: "sunday"}.get(day.weekday(), "weekday")


def slot_label(slot: int) -> str:
    return f"{slot // 6:02d}:{slot % 6 * 10:02d}"
