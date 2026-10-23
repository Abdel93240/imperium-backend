"""Courses « Priority » (Bolt) : le client paie plus cher pour être pris plus vite ; l'étiquette s'affiche à gauche du
prix. Vector la lit sur l'offre (`is_priority`) et apprend où et quand ces courses tombent le plus souvent.

Découpage : la case de la grille météo où se trouve la tablette à l'offre (`zone_cell`, Paris et petite couronne
~3 km, reste de l'Île-de-France ~10 km) et le code postal de prise en charge, croisés avec l'heure (créneau).
Seules les offres dont l'étiquette a été lue (vrai ou faux) comptent ; une offre saisie à la main sans cette
information ne compte pas. Variables d'une offre : part des courses Priority vues dans la même case, à une heure
près, sur 90 jours, et le nombre d'offres derrière cette part (une part sur 3 offres ne vaut pas une part sur 300).
"""

from datetime import datetime, timedelta

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.rides import RidesOffer
from app.schemas.rides import PriorityStatRow, PriorityStatsRead

WINDOW = timedelta(days=90)
MIN_OFFERS = 5  # en dessous, la zone est listée sans part (trop peu d'offres)


def _flag():
    return RidesOffer.features["is_priority"].astext


def history_features(db: Session, user_id, *, cell: str | None, hour: int, at: datetime) -> dict:
    if cell is None:
        return {"priority_share_cell_hour": None, "priority_offers_seen_cell_hour": None}
    hours = [(hour + delta) % 24 for delta in (-1, 0, 1)]
    seen, priority = db.execute(
        select(func.count(), func.count().filter(_flag() == "true")).where(
            RidesOffer.user_id == user_id, RidesOffer.offered_at >= at - WINDOW, RidesOffer.offered_at < at,
            RidesOffer.features["zone_cell"].astext == cell, _flag().in_(("true", "false")),
            cast(RidesOffer.features["hour_of_day"].astext, Integer).in_(hours),
        )
    ).one()
    return {"priority_share_cell_hour": round(priority / seen, 3) if seen else None,
            "priority_offers_seen_cell_hour": seen}


def stats(db: Session, *, current_user: User, days: int = 90, now: datetime | None = None) -> PriorityStatsRead:
    """Part des courses Priority par zone et par créneau, de la plus forte à la plus faible."""
    now = now or datetime.now().astimezone()
    since = now - timedelta(days=days)
    rows = []
    for by in ("zone_cell", "pickup_zone_code"):
        key = RidesOffer.features[by].astext if by == "zone_cell" else RidesOffer.pickup_zone_code
        block = RidesOffer.features["time_block"].astext
        result = db.execute(
            select(key, block, func.count(), func.count().filter(_flag() == "true"))
            .where(RidesOffer.user_id == current_user.id, RidesOffer.offered_at >= since, key.is_not(None),
                   _flag().in_(("true", "false")))
            .group_by(key, block)
        ).all()
        rows += [PriorityStatRow(by=by, zone=zone, time_block=time_block, offers=offers, priority=priority,
                                 share=round(priority / offers, 3) if offers >= MIN_OFFERS else None)
                 for zone, time_block, offers, priority in result]
    rows.sort(key=lambda r: (r.share is None, -(r.share or 0), -r.offers))
    total = sum(r.offers for r in rows if r.by == "zone_cell")
    return PriorityStatsRead(days=days, offers=total, min_offers=MIN_OFFERS, rows=rows)
