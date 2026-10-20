"""Horaires d'une mosquée précise pour un jour (doc 41 §6 ; Q6 : chaque mosquée a SES horaires).

Source, dans l'ordre : le cache MAWAQIT de la mosquée s'il n'est pas expiré, sinon le calcul local à ses
coordonnées décalé de `adhan_offsets` (saisis par l'utilisateur). L'iqama = adhan + `iqama_offsets` de la
prière, inconnue sinon. Aucun appel réseau ici : le cache se remplit par son propre job.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.path import PathRegisteredMosque
from app.services.path import prayer

PARIS = ZoneInfo("Europe/Paris")


@dataclass(frozen=True)
class MosqueTimes:
    adhans: dict[str, datetime]
    iqamas: dict[str, datetime | None]
    source: str  # mawaqit | calculated


def mosque_times(db: Session, mosque: PathRegisteredMosque, day: date, *, user_id: UUID) -> MosqueTimes | None:
    """None si la mosquée n'a ni cache MAWAQIT valable ni coordonnées."""
    row = prayer.cached_mawaqit_row(db, mosque, day)
    if row is not None and prayer.mawaqit_quality(row.fetched_at) != "expired":
        adhans, source = prayer.parse_mawaqit_times(row.prayer_times, day, PARIS), "mawaqit"
    elif mosque.latitude is not None and mosque.longitude is not None:
        config = prayer.calculation_config(db, user_id)
        computed = prayer.compute_prayer_times_utc(day, float(mosque.latitude), float(mosque.longitude),
                                                   method=config.method, madhhab=config.madhhab)
        offsets = mosque.adhan_offsets or {}
        adhans = {name: ts.astimezone(PARIS) + timedelta(minutes=int(offsets.get(name, 0)))
                  for name, ts in computed.items()}
        source = "calculated"
    else:
        return None
    waits = mosque.iqama_offsets or {}
    iqamas = {name: adhans[name] + timedelta(minutes=int(waits[name])) if name in waits else None
              for name in prayer.PRAYERS}
    return MosqueTimes(adhans=adhans, iqamas=iqamas, source=source)
