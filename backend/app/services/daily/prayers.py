"""Prières en engagements fixes de la porte G4 (Q6 tranchée ; carte ACT-DLY-10 ; doc 41 §7-bis).

Daily ne construit rien de religieux : il LIT les horaires de Path (`mosque_times`) et décide seulement
quand il faut partir. Pour une prière, depuis un lieu de départ et une heure à laquelle on est libre :
1. candidates = les mosquées enregistrées dont le trajet estimé, marge comprise
   (`path.mosque_travel_margin_pct`), tient dans `path.mosque_search_travel_min` ;
2. joignables = celles où l'on arrive au plus tard à l'ADHAN de CETTE mosquée (temps des ablutions) ;
3. retenue = celle qui prie le plus tôt (puis le trajet le plus court) : la journée reprend au plus vite.
Départ = adhan − trajet avec marge ; bloc jusqu'à iqama + `path.prayer_after_iqama_min`, ou adhan +
`path.prayer_solo_block_min` sans iqama connue. Aucune mosquée joignable (ou lieu inconnu) : prière seul,
bloc de `path.prayer_solo_block_min` à l'adhan de référence. Le trajet est toujours estimé en local
(`privacy_tier=very_high` : un lieu de culte ne part jamais vers un fournisseur externe ni dans le cache).

La porte G4 s'arrête au départ (ou à l'adhan, seul) de la prochaine prière encore devant soi quand
`daily.prayer_commitments_enabled` est vrai.
"""

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.imperium import ImperiumMission
from app.models.path import PathRegisteredMosque
from app.services.params import get_parameter
from app.services.path import mosque_times, prayer
from app.services.travel.estimate import estimate
from app.services.travel.geo import LatLng

PARIS = ZoneInfo("Europe/Paris")
DEFAULT_MISSION_MIN = 60


@dataclass(frozen=True)
class PrayerPlan:
    prayer: str
    reference_adhan: datetime
    mosque_id: UUID | None
    mosque_name: str | None
    travel_min: int | None  # marge comprise
    depart_at: datetime | None
    adhan: datetime
    iqama: datetime | None
    block_end: datetime
    times_source: str
    solo_reason: str | None  # no_origin | no_mosque_in_range | none_reachable_in_time
    origin_source: str  # previous_mission | current_position | none

    @property
    def bound(self) -> datetime:
        """Heure à laquelle la mission en cours doit être finie."""
        return self.depart_at or self.adhan


def enabled(db: Session) -> bool:
    return bool(get_parameter(db, "daily.prayer_commitments_enabled", default=False))


def commitment_ref(user: User, day: date, name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"imperium:prayer:{user.id}:{day.isoformat()}:{name}")


def plan_prayer(db: Session, *, user: User, name: str, day: date, origin: LatLng | None,
                ready_at: datetime | None, origin_source: str) -> PrayerPlan:
    reference, _ = prayer.prayer_times(db, day, user_id=user.id)
    reference_adhan = reference[name]
    search_min = int(get_parameter(db, "path.mosque_search_travel_min", default=20))
    margin = float(get_parameter(db, "path.mosque_travel_margin_pct", default=20)) / 100
    after_iqama = int(get_parameter(db, "path.prayer_after_iqama_min", default=15))
    solo_block = int(get_parameter(db, "path.prayer_solo_block_min", default=20))

    def solo(reason: str) -> PrayerPlan:
        return PrayerPlan(prayer=name, reference_adhan=reference_adhan, mosque_id=None, mosque_name=None,
                          travel_min=None, depart_at=None, adhan=reference_adhan, iqama=None,
                          block_end=reference_adhan + timedelta(minutes=solo_block), times_source="reference",
                          solo_reason=reason, origin_source=origin_source)

    if origin is None:
        return solo("no_origin")
    candidates = []
    for mosque in db.scalars(select(PathRegisteredMosque).where(
            PathRegisteredMosque.user_id == user.id, PathRegisteredMosque.latitude.is_not(None))
            .order_by(PathRegisteredMosque.added_at)):
        times = mosque_times.mosque_times(db, mosque, day, user_id=user.id)
        if times is None:
            continue
        adhan = times.adhans[name]
        trip = estimate(origin, LatLng(float(mosque.latitude), float(mosque.longitude)), adhan.astimezone(UTC),
                        privacy_tier="very_high", db=db)
        travel = math.ceil(trip.duration_s / 60 * (1 + margin))
        if travel > search_min:
            continue
        candidates.append((mosque, times, adhan, travel))
    if not candidates:
        return solo("no_mosque_in_range")
    reachable = [c for c in candidates if ready_at is None or ready_at + timedelta(minutes=c[3]) <= c[2]]
    if not reachable:
        return solo("none_reachable_in_time")
    mosque, times, adhan, travel = min(reachable, key=lambda c: (c[2], c[3], str(c[0].id)))
    iqama = times.iqamas[name]
    block_end = iqama + timedelta(minutes=after_iqama) if iqama else adhan + timedelta(minutes=solo_block)
    return PrayerPlan(prayer=name, reference_adhan=reference_adhan, mosque_id=mosque.id, mosque_name=mosque.name,
                      travel_min=travel, depart_at=adhan - timedelta(minutes=travel), adhan=adhan, iqama=iqama,
                      block_end=block_end, times_source=times.source, solo_reason=None, origin_source=origin_source)


def next_prayer(db: Session, *, user: User, now: datetime, origin: LatLng | None) -> PrayerPlan | None:
    """Prochaine prière du jour de Paris dont on n'a pas encore passé l'heure de départ (G4)."""
    day = now.astimezone(PARIS).date()
    for name in prayer.PRAYERS:
        plan = plan_prayer(db, user=user, name=name, day=day, origin=origin, ready_at=now,
                           origin_source="current_position" if origin else "none")
        if plan.bound > now:
            return plan
    return None


def day_plan(db: Session, *, user: User, day: date, origin: LatLng | None, now: datetime | None = None
             ) -> list[PrayerPlan]:
    """Plan du jour : pour chaque prière, départ depuis le lieu où finit la mission précédente (sinon la
    position donnée, libre dès maintenant pour aujourd'hui)."""
    now = now or datetime.now(UTC)
    reference, _ = prayer.prayer_times(db, day, user_id=user.id)
    missions = _located_missions(db, user, day)
    plans = []
    for name in prayer.PRAYERS:
        before = [(end, point) for end, point in missions if end <= reference[name]]
        if before:
            ready_at, start, source = before[-1][0], before[-1][1], "previous_mission"
        else:
            start, source = origin, "current_position" if origin else "none"
            ready_at = now if day == now.astimezone(PARIS).date() and origin else None
        plans.append(plan_prayer(db, user=user, name=name, day=day, origin=start, ready_at=ready_at,
                                 origin_source=source))
    return plans


def _located_missions(db: Session, user: User, day: date) -> list[tuple[datetime, LatLng]]:
    start = datetime.combine(day, time.min, tzinfo=PARIS)
    rows = db.execute(select(ImperiumMission.planned_start_at, ImperiumMission.fixed_at, ImperiumMission.is_fixed_commitment,
                             ImperiumMission.estimated_minutes, ImperiumMission.location_lat,
                             ImperiumMission.location_lng).where(
        ImperiumMission.user_id == user.id, ImperiumMission.status.in_(("backlog", "active")),
        ImperiumMission.location_lat.is_not(None))).all()
    ends = []
    for row in rows:
        begin = row.fixed_at if row.is_fixed_commitment and row.fixed_at else row.planned_start_at
        if begin is None or not start <= begin < start + timedelta(days=1):
            continue
        end = begin + timedelta(minutes=row.estimated_minutes or DEFAULT_MISSION_MIN)
        ends.append((end, LatLng(float(row.location_lat), float(row.location_lng))))
    return sorted(ends, key=lambda item: item[0])
