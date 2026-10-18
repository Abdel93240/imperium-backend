"""Tableau de bord Path (PAT-01, doc 59 §16.1) : lecture seule, sans nouvelle table.

Assemble ce que Path sait déjà pour un jour de Paris : les cinq prières (heure, source,
statut posé), la prochaine prière et son compte à rebours, l'état du jeûne, l'objectif
sadaqa de la semaine, le ghusl, les compteurs d'adhkar, le point de reprise du Coran,
la date hégirienne, la direction de la qibla, et des bannières courtes. Aucun texte de reproche : une
prière sans statut reste sans statut. Jours blancs : une suggestion, jamais un jeûne
automatique. Score Path (doc 41 §13) : pas encore.
"""

import math
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.auth import User
from app.schemas.path_dashboard import NextPrayerRead, PathBannerRead, PathDashboardRead, QiblaRead
from app.services.path import adhkar, fasting, ghusl, hijri, prayer_marks, quran, sadaqa
from app.services.path.prayer import DEFAULT_LOCATION, PRAYERS, _reference_mosque, prayer_times

KAABA = (21.422487, 39.826206)


def build_dashboard(db: Session, *, current_user: User, day: date, now: datetime | None = None) -> PathDashboardRead:
    now = now or datetime.now(UTC)
    today = now.astimezone(fasting.PARIS).date()
    prayers = prayer_marks.day_view(db, current_user=current_user, day=day)
    fast_state = fasting.state(db, current_user=current_user, at=now)
    week = sadaqa.week_summary(db, current_user=current_user, week_start=sadaqa.week_start_of(min(day, today)), now=now)
    ghusl_state = ghusl.current(db, current_user=current_user)
    routines = [item for item in adhkar.list_routines(db, current_user=current_user, day=day).items if item.active]
    banners = []
    if ghusl_state.ghusl_required:
        banners.append(PathBannerRead(kind="ghusl_required", level="warning", message=ghusl_state.message))
    if message := fasting.day_message(db, current_user, day, now):
        banners.append(PathBannerRead(kind="fasting", level="info", message=message))
    hijri_day = hijri.hijri_day(db, current_user=current_user, day=day)
    if hijri_day.ramadan:
        banners.append(PathBannerRead(kind="ramadan", level="info", message=f"Ramadan, jour {hijri_day.hijri_day}."))
    elif hijri_day.white_day:
        banners.append(PathBannerRead(
            kind="white_days", level="info",
            message=f"Jour blanc ({hijri_day.hijri_day} {hijri_day.month_name}) : un jeûne est possible si tu le souhaites.",
        ))
    if week.carry_message:
        banners.append(PathBannerRead(kind="sadaqa_carry", level="info", message=week.carry_message))
    if week.vault_pending:
        banners.append(PathBannerRead(
            kind="sadaqa_vault_pending", level="warning",
            message=f"{week.vault_pending} don(s) en attente d'écriture au Vault.",
        ))
    return PathDashboardRead(
        day=day, hijri=hijri_day, prayers=prayers, next_prayer=next_prayer(db, now) if day == today else None, fasting=fast_state,
        sadaqa=week, ghusl=ghusl_state, adhkar=routines, quran=quran.continuation(db, current_user=current_user, today=today),
        qibla=qibla(db), banners=banners,
    )


def next_prayer(db: Session, now: datetime) -> NextPrayerRead:
    today = now.astimezone(fasting.PARIS).date()
    for day in (today, today + timedelta(days=1)):
        adhans, _ = prayer_times(db, day)
        for name in PRAYERS:
            if adhans[name] > now:
                return NextPrayerRead(
                    prayer_name=name, adhan_at=adhans[name], countdown_seconds=int((adhans[name] - now).total_seconds())
                )
    raise RuntimeError("No prayer within two days.")  # impossible : fajr existe chaque jour


def qibla(db: Session) -> QiblaRead:
    """Cap initial (grand cercle) vers la Kaaba depuis la mosquée de référence, sinon Paris."""
    mosque = _reference_mosque(db)
    if mosque is not None and mosque.latitude is not None and mosque.longitude is not None:
        origin, source = (float(mosque.latitude), float(mosque.longitude)), "reference_mosque"
    else:
        origin, source = DEFAULT_LOCATION, "default_city"
    return QiblaRead(direction_degrees=round(bearing(origin, KAABA), 1), location_source=source)


def bearing(origin: tuple[float, float], target: tuple[float, float]) -> float:
    lat1, lng1 = map(math.radians, origin)
    lat2, lng2 = map(math.radians, target)
    delta = lng2 - lng1
    x = math.sin(delta) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(delta)
    return (math.degrees(math.atan2(x, y)) + 360) % 360
