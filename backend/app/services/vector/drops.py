"""Mesure après chaque dépose (décision utilisateur 2026-10-23) : la valeur réelle d'une zone à un créneau.

À la fin d'une course (résultat enregistré), une mesure s'ouvre à l'endroit et à l'heure de la dépose : zone fine
(position GPS de la dépose, sinon centre de la commune d'arrivée), créneau de 10 minutes, type de jour, vacances.
Elle se remplit ensuite toute seule :
- première offre reçue → attente jusqu'à la première offre ; chaque offre vue est comptée ;
- course suivante terminée → attente jusqu'à son acceptation, son gain et son temps mobilisé, et le €/h du cycle
  = gain ÷ (attente jusqu'à l'acceptation + temps mobilisé) ;
- pause ou fin de session avant la course suivante → mesure interrompue (le temps n'était plus du travail).
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rides import RidesDropObservation, RidesOffer
from app.services.vector import feeds, geo, grid, school


def _minutes(start: datetime, end: datetime) -> float:
    return round(max(0.0, (end - start).total_seconds() / 60), 1)


def _open(db: Session, session_id) -> list[RidesDropObservation]:
    # Sans vidage automatique : appelé au milieu d'un changement d'état de la session (pause, arrêt).
    with db.no_autoflush:
        return list(db.scalars(select(RidesDropObservation).where(
            RidesDropObservation.session_id == session_id, RidesDropObservation.status == "open").with_for_update()))


def on_offer(db: Session, session_id, offered_at: datetime) -> None:
    for obs in _open(db, session_id):
        if offered_at < obs.dropped_at:
            continue
        obs.offers_seen += 1
        if obs.next_offer_at is None:
            obs.next_offer_at = offered_at
            obs.wait_first_offer_min = _minutes(obs.dropped_at, offered_at)


def on_outcome(db: Session, offer: RidesOffer, *, accepted_at: datetime | None, ended_at: datetime,
               dropoff: tuple[float, float] | None) -> RidesDropObservation:
    """Ferme la mesure ouverte (cette course est « la suivante ») puis ouvre celle de sa propre dépose."""
    accepted = accepted_at or offer.decided_at or offer.offered_at
    for obs in _open(db, offer.session_id):
        if obs.offer_id == offer.id or accepted < obs.dropped_at:
            continue
        wait = _minutes(obs.dropped_at, accepted)
        obs.next_offer_id, obs.next_accepted_at, obs.wait_to_accept_min = offer.id, accepted, wait
        obs.next_earning_cents, obs.next_mobilized_min = offer.actual_earning_cents, offer.mobilized_minutes
        cycle_min = wait + (offer.mobilized_minutes or 0)
        obs.cycle_hourly_cents = round(offer.actual_earning_cents * 60 / cycle_min) if cycle_min > 0 else None
        obs.status, obs.closed_reason = "closed", "next_ride"
    if dropoff is not None:
        lat, lng, source = dropoff[0], dropoff[1], "gps"
    else:
        place = geo.resolve(offer.destination_address or offer.destination_zone)
        lat, lng, source = (place.lat, place.lng, "commune") if place else (None, None, None)
    zone = grid.zone_at(lat, lng) if lat is not None else None
    holiday, _ = school.holiday_on(db, ended_at.astimezone(grid.PARIS).date())
    obs = RidesDropObservation(
        id=uuid4(), user_id=offer.user_id, session_id=offer.session_id, offer_id=offer.id, dropped_at=ended_at,
        drop_lat=lat, drop_lng=lng, zone_code=zone.code if zone else None, zone_source=source,
        slot=grid.slot_of(ended_at), day_type=grid.day_type(ended_at), school_holiday=holiday, status="open",
        context=feeds.drop_context(db, ended_at, lat, lng),
    )
    db.add(obs)
    db.flush()
    return obs


def interrupt(db: Session, session_id, reason: str) -> None:
    """Pause ou fin de session avant la course suivante : la mesure ouverte s'arrête là."""
    for obs in _open(db, session_id):
        obs.status, obs.closed_reason = "interrupted", reason
