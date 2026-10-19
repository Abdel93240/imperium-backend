"""Seuils d'alerte du journal des appels IA (doc 43 §17.6).

evaluate() lit `ai_call_logs` sans rien écrire ; le job horaire `ai.call_alerts` (semé
désactivé) notifie chaque seuil franchi au plus une fois par jour (référence = seuil + jour
de Paris, dédoublonnée par notify()). Les seuils sont des paramètres versionnés `ai.alert_*`.
Rien n'est coupé ni rerouté automatiquement : l'alerte informe, l'utilisateur décide.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.notifications import notify
from app.services.params import get_parameter

PARIS = ZoneInfo("Europe/Paris")


@dataclass(frozen=True)
class CallAlert:
    code: str
    message_fr: str
    value: float
    threshold: float


def evaluate(db: Session, *, now: datetime | None = None) -> list[CallAlert]:
    now = now or datetime.now(UTC)
    day_start = datetime.combine(now.astimezone(PARIS).date(), time.min, tzinfo=PARIS)
    alerts: list[CallAlert] = []

    def param(code: str, default: float) -> float:
        return float(get_parameter(db, f"ai.alert_{code}", default=default))

    def scalar(sql: str, **params) -> float:
        return float(db.execute(text(sql), params).scalar() or 0)

    daily = scalar("SELECT SUM(cost_eur) FROM ai_call_logs WHERE called_at >= :start AND called_at <= :now",
                   start=day_start, now=now)
    if daily > (limit := param("daily_spend_eur", 1.5)):
        alerts.append(CallAlert("daily_spend", f"Dépense IA du jour : {daily:.2f} € (seuil {limit:.2f} €). "
                                "Un appel tourne peut-être en boucle.", daily, limit))

    weekly = scalar("SELECT SUM(cost_eur) FROM ai_call_logs WHERE called_at > :since AND called_at <= :now",
                    since=now - timedelta(days=7), now=now)
    if weekly > (limit := param("weekly_spend_eur", 7)):
        alerts.append(CallAlert("weekly_spend", f"Dépense IA sur 7 jours : {weekly:.2f} € (seuil {limit:.2f} €).",
                                weekly, limit))

    total, failed = db.execute(
        text("SELECT COUNT(*), COUNT(*) FILTER (WHERE success = FALSE) FROM ai_call_logs "
             "WHERE called_at > :since AND called_at <= :now"),
        {"since": now - timedelta(hours=24), "now": now},
    ).one()
    if total >= param("error_min_calls", 20) and total:
        rate = 100.0 * failed / total
        if rate > (limit := param("error_rate_pct", 5)):
            alerts.append(CallAlert("error_rate", f"Erreurs des appels IA sur 24 h : {rate:.1f} % "
                                    f"({failed}/{total}, seuil {limit:g} %).", rate, limit))

    min_checked = param("hallucination_min_checked", 10)
    limit = param("hallucination_pct", 15)
    worst = db.execute(
        text("SELECT task_type, 100.0 * COUNT(*) FILTER (WHERE was_validated = FALSE) / COUNT(*) AS rate "
             "FROM ai_call_logs WHERE model_tier = 'local' AND was_validated IS NOT NULL "
             "AND called_at > :since AND called_at <= :now GROUP BY task_type HAVING COUNT(*) > :min_checked "
             "ORDER BY rate DESC LIMIT 1"),
        {"since": now - timedelta(days=30), "now": now, "min_checked": min_checked},
    ).first()
    if worst is not None and float(worst.rate) > limit:
        alerts.append(CallAlert("hallucination_rate", f"Le modèle local se trompe sur « {worst.task_type} » : "
                                f"{float(worst.rate):.1f} % des réponses vérifiées (seuil {limit:g} %).",
                                float(worst.rate), limit))

    expensive = db.execute(
        text("SELECT COUNT(*), MAX(cost_eur) FROM ai_call_logs WHERE cost_eur > :limit "
             "AND called_at > :since AND called_at <= :now"),
        {"limit": (limit := param("single_call_eur", 0.5)), "since": now - timedelta(hours=24), "now": now},
    ).one()
    if expensive[0]:
        alerts.append(CallAlert("single_call_cost", f"{expensive[0]} appel(s) IA à plus de {limit:.2f} € sur 24 h "
                                f"(max {float(expensive[1]):.2f} €) : contexte trop long ?", float(expensive[1]), limit))

    slow = db.execute(
        text("SELECT task_type, PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY duration_ms) AS p90 "
             "FROM ai_call_logs WHERE duration_ms IS NOT NULL AND called_at > :since AND called_at <= :now "
             "GROUP BY task_type ORDER BY p90 DESC LIMIT 1"),
        {"since": now - timedelta(days=30), "now": now},
    ).first()
    if slow is not None and float(slow.p90) > (limit := param("p90_latency_ms", 30000)):
        alerts.append(CallAlert("p90_latency", f"« {slow.task_type} » est lent : p90 {float(slow.p90) / 1000:.0f} s "
                                f"(seuil {limit / 1000:g} s).", float(slow.p90), limit))

    fallbacks = scalar("SELECT COUNT(*) FROM ai_call_logs WHERE fallback_used AND called_at > :since "
                       "AND called_at <= :now", since=now - timedelta(hours=1), now=now)
    if fallbacks > (limit := param("fallbacks_per_hour", 3)):
        alerts.append(CallAlert("fallbacks_last_hour", f"{fallbacks:g} replis sur un autre modèle en une heure "
                                f"(seuil {limit:g}) : le modèle principal échoue.", fallbacks, limit))
    return alerts


def ai_call_alerts_job(ctx, window) -> None:
    """Job `ai.call_alerts` (horaire, semé désactivé) : une notification par seuil et par jour."""
    now = window.to_ts or datetime.now(UTC)
    alerts = evaluate(ctx.db, now=now)
    day = now.astimezone(PARIS).date().isoformat()
    sent = 0
    for alert in alerts:
        note = notify(
            ctx.db, severity="normal", domain="system", message_fr=alert.message_fr,
            ref=("ai_call_alert", uuid5(NAMESPACE_URL, f"imperium:ai_call_alert:{alert.code}:{day}")),
        )
        sent += note is not None
    ctx.db.commit()
    ctx.items_in, ctx.items_out = len(alerts), sent
    ctx.detail = {"alerts": [alert.code for alert in alerts], "notified": sent}
    ctx.cursor_ts = now
