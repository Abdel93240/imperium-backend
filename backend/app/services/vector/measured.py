"""Valeur mesurée d'une zone à un créneau (décision utilisateur 2026-10-23) : les mesures après dépose, lissées.

Une mesure = le €/h du cycle qui a suivi une dépose (attente jusqu'à la course suivante + cette course), avec sa
position, son heure et son type de jour (`rides_drop_observations`). Pour un lieu et un instant, chaque mesure des
180 derniers jours pèse :
- dans le temps : même créneau de 10 min = 1 ; ±10 min ≈ 0,78 ; ±20 min ≈ 0,37 ; au-delà d'une heure, rien ;
- dans l'espace : selon la distance, à l'échelle de la case (1 km à Paris, 1,7 km en ville, 3,2 km en campagne) ;
- par type de jour : même type = 1, samedi ↔ dimanche ou férié = 0,6, semaine ↔ week-end = 0,3 ;
- par ancienneté : demi-vie de 60 jours.
Le résultat est (somme des poids, moyenne pondérée en €/h). C'est un premier lissage, simple et explicable ; le
modèle prendra le relais quand il y aura assez de courses (doc 57 §3).
"""

import math
from datetime import datetime, timedelta
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rides import RidesDropObservation
from app.services.vector import grid

WINDOW = timedelta(days=180)
HALF_LIFE_DAYS = 60
MAX_SLOT_GAP = 6
MIN_FOR_REFERENCE = 10
WEEKEND = {"saturday", "sunday", "holiday"}


def _day_weight(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if a in WEEKEND and b in WEEKEND:
        return 0.6
    return 0.3


def _measures(db: Session, lat: float, lng: float, at: datetime, radius_km: float):
    dlat = radius_km / grid.KM_PER_DEG_LAT
    dlng = radius_km / grid.KM_PER_DEG_LNG
    return db.execute(select(
        RidesDropObservation.drop_lat, RidesDropObservation.drop_lng, RidesDropObservation.slot,
        RidesDropObservation.day_type, RidesDropObservation.dropped_at, RidesDropObservation.cycle_hourly_cents,
    ).where(
        RidesDropObservation.status == "closed", RidesDropObservation.cycle_hourly_cents.is_not(None),
        RidesDropObservation.drop_lat.between(lat - dlat, lat + dlat),
        RidesDropObservation.drop_lng.between(lng - dlng, lng + dlng),
        RidesDropObservation.dropped_at.between(at - WINDOW, at),
    )).all()


def estimate(db: Session, lat: float, lng: float, at: datetime) -> tuple[float, float]:
    """(poids total, €/h moyen pondéré) des mesures proches de ce lieu et de ce créneau ; (0, 0) sans mesure."""
    side = grid.SIDES[grid.kind_at(lat, lng)]
    slot, day = grid.slot_of(at), grid.day_type(at)
    total = weighted = 0.0
    for m_lat, m_lng, m_slot, m_day, m_at, cents in _measures(db, lat, lng, at, radius_km=3 * side):
        gap = min(abs(m_slot - slot), 144 - abs(m_slot - slot))
        if gap > MAX_SLOT_GAP:
            continue
        km = math.hypot((float(m_lat) - lat) * grid.KM_PER_DEG_LAT, (float(m_lng) - lng) * grid.KM_PER_DEG_LNG)
        weight = (math.exp(-((gap / 2) ** 2)) * math.exp(-((km / side) ** 2)) * _day_weight(m_day, day)
                  * 0.5 ** ((at - m_at).total_seconds() / 86400 / HALF_LIFE_DAYS))
        total += weight
        weighted += weight * cents / 100
    return (total, weighted / total) if total else (0.0, 0.0)


def reference_eur(db: Session) -> float | None:
    """€/h médian des cycles mesurés (180 jours) : la note 50 ; None tant qu'il y a moins de 10 mesures."""
    values = list(db.scalars(select(RidesDropObservation.cycle_hourly_cents).where(
        RidesDropObservation.status == "closed", RidesDropObservation.cycle_hourly_cents.is_not(None))))
    return median(values) / 100 if len(values) >= MIN_FOR_REFERENCE else None
