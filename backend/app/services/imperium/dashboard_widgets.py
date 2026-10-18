"""Widgets du tableau de bord Imperium (doc 59 §12.2) : prochaine prière et score de pression.

Lecture seule : les horaires viennent du service des prières de Path (cache MAWAQIT de la
mosquée par défaut, sinon calcul local selon les réglages Path), la pression du moteur Vault
(doc 11) calculé en mémoire. Rien n'est écrit : ni instantané de pression, ni événement, ni
signal (`GET /api/vault/pressure` reste l'écriture de référence).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.auth import User
from app.schemas.dashboard import (
    DashboardNextPrayerWidget,
    DashboardPressureWidget,
    ImperiumDashboardWidgetsResponse,
)
from app.schemas.vault import VaultDailyTargets
from app.services.path.fasting import PARIS
from app.services.path.prayer import PRAYERS, prayer_times
from app.services.vault.pressure import compute_pressure, load_pressure_inputs


def dashboard_widgets(db: Session, *, current_user: User, now: datetime | None = None) -> ImperiumDashboardWidgetsResponse:
    now = now or datetime.now(UTC)
    return ImperiumDashboardWidgetsResponse(
        next_prayer=_next_prayer(db, current_user, now), pressure=_pressure(db, current_user, now), generated_at=now,
    )


def _next_prayer(db: Session, user: User, now: datetime) -> DashboardNextPrayerWidget:
    today = now.astimezone(PARIS).date()
    for day in (today, today + timedelta(days=1)):
        adhans, source = prayer_times(db, day, user_id=user.id)
        for name in PRAYERS:
            if adhans[name] > now:
                return DashboardNextPrayerWidget(prayer_name=name, adhan_at=adhans[name], source=source,
                                                 countdown_seconds=int((adhans[name] - now).total_seconds()))
    raise RuntimeError("No prayer within two days.")  # impossible : fajr existe chaque jour


def _pressure(db: Session, user: User, now: datetime) -> DashboardPressureWidget:
    # Même jour de référence que GET /api/vault/pressure, pour afficher le même score.
    result = compute_pressure(load_pressure_inputs(db, current_user=user, today=now.date(), now=now))
    return DashboardPressureWidget(score=result.score, label=result.label, computed_at=now,
                                   daily_targets=VaultDailyTargets(**result.daily_targets))
