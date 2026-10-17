"""Alertes de date limite du stock Pulse (doc 40 §11.3) — déterministe, sans IA.

  DLC dépassée          → error   (à jeter ou vérifier)
  DLC dans 0 à 2 jours  → warning (à consommer vite)
  DDM dans 0 à 7 jours  → info    (à consommer bientôt ; une DDM dépassée reste info)
La bannière Pulse lit `compute_alerts` en direct ; le job de 9 h (heure de Paris)
envoie une seule notification par jour quand il y a quelque chose à signaler.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.imperium import FoodStockItem
from app.services.notifications import notify

PARIS = ZoneInfo("Europe/Paris")
DLC_SOON_DAYS = 2
DDM_SOON_DAYS = 7
JOB_LOCAL_HOUR = 9
_LEVEL_ORDER = {"none": 0, "info": 1, "warning": 2, "error": 3}
_SEVERITY = {"info": "info", "warning": "normal", "error": "red"}


@dataclass
class ExpiryAlert:
    item_id: str
    name: str
    expiry_type: str
    expiry_date: date
    days_left: int
    level: str  # info | warning | error


@dataclass
class ExpiryReport:
    today: date
    level: str = "none"
    alerts: list[ExpiryAlert] = field(default_factory=list)

    @property
    def to_consume(self) -> int:
        return sum(alert.level in ("warning", "error") for alert in self.alerts)

    @property
    def message_fr(self) -> str | None:
        if not self.alerts:
            return None
        expired = sum(alert.level == "error" for alert in self.alerts)
        soon = sum(alert.level == "warning" for alert in self.alerts)
        bientot = sum(alert.level == "info" for alert in self.alerts)
        parts = []
        if expired:
            parts.append(f"{expired} produit{'s' if expired > 1 else ''} dépassé{'s' if expired > 1 else ''}")
        if soon:
            parts.append(f"{soon} à consommer rapidement")
        if bientot:
            parts.append(f"{bientot} à consommer cette semaine")
        return "Stock : " + ", ".join(parts) + "."


def paris_today(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(PARIS).date()


def classify(expiry_type: str, expiry_date: date | None, today: date) -> tuple[str | None, int | None]:
    if expiry_date is None or expiry_type not in ("DLC", "DDM"):
        return None, None
    days_left = (expiry_date - today).days
    if expiry_type == "DLC":
        if days_left < 0:
            return "error", days_left
        if days_left <= DLC_SOON_DAYS:
            return "warning", days_left
        return None, days_left
    if days_left <= DDM_SOON_DAYS:
        return "info", days_left
    return None, days_left


def compute_alerts(db: Session, *, current_user: User, today: date | None = None) -> ExpiryReport:
    today = today or paris_today()
    report = ExpiryReport(today=today)
    rows = db.scalars(
        select(FoodStockItem).where(
            FoodStockItem.user_id == current_user.id,
            FoodStockItem.status == "active",
            FoodStockItem.expiry_date.is_not(None),
        )
    )
    for item in rows:
        level, days_left = classify(item.expiry_type, item.expiry_date, today)
        if level is None:
            continue
        report.alerts.append(ExpiryAlert(str(item.id), item.name, item.expiry_type, item.expiry_date, days_left, level))
    report.alerts.sort(key=lambda alert: (-_LEVEL_ORDER[alert.level], alert.days_left, alert.name))
    report.level = max((alert.level for alert in report.alerts), key=_LEVEL_ORDER.get, default="none")
    return report


def food_stock_expiry_job(ctx, window) -> None:
    """Planifié à 7 h et 8 h UTC : n'agit qu'à 9 h à Paris (heure d'été comme d'hiver)."""
    now = window.to_ts or datetime.now(UTC)
    if now.astimezone(PARIS).hour != JOB_LOCAL_HOUR:
        ctx.items_in, ctx.items_out, ctx.detail = 0, 0, {"skip": "not_9h_paris"}
        return
    user = _job_user(ctx.db)
    if user is None:
        ctx.items_in, ctx.items_out, ctx.detail = 0, 0, {"skip": "no_user"}
        return
    report = compute_alerts(ctx.db, current_user=user, today=paris_today(now))
    sent = 0
    if report.alerts:
        notification = notify(
            ctx.db,
            severity=_SEVERITY[report.level],
            domain="pulse",
            message_fr=report.message_fr,
            # Une référence par jour : le dédoublonnage évite deux envois le même jour.
            ref=("food_stock_expiry_day", uuid5(NAMESPACE_URL, f"imperium:food_stock_expiry:{user.id}:{report.today}")),
        )
        sent = int(notification is not None)
    ctx.items_in = len(report.alerts)
    ctx.items_out = sent
    ctx.detail = {"level": report.level, "alerts": len(report.alerts), "notified": sent}


def _job_user(db: Session) -> User | None:
    from app.core.config import get_settings

    settings = get_settings()
    if settings.imperium_canonical_user_id is not None:
        user = db.get(User, settings.imperium_canonical_user_id)
        if user is not None:
            return user
    return db.scalar(select(User).order_by(User.created_at).limit(1))
