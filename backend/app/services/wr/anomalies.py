"""W4 — anomalies sur les rollups (spec WR §4 W4, carte V18 ACT-WR-04). Code pur.

Pour chaque signal `wr.*` ACTIF de `signal_definitions` (table partagée, semés inactifs) et chaque
jour dont le rollup a été (re)calculé dans la fenêtre : baseline = médiane des
`baseline_window_days` jours précédents, échelle = MAD × 1,4826 (jamais sous `min_scale`),
z = écart / échelle compté dans le sens qui inquiète (`direction`). Bande green|yellow|orange|red
selon les seuils de `bands`. Sans `min_history_days` jours d'historique : pas de valeur.

Une valeur par signal et par jour dans `signal_values` (measured_at = fin du jour de Paris,
réécrite si le jour est recalculé ; `detail.user_id` : la table n'a pas de colonne utilisateur).
Marqueur `unexplained` : toute bande hors green, tant qu'aucun lien causal (W2) ni catalogue de
raisons déclarées n'existe pour l'en retirer.
"""

import statistics
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.toolbox import SignalDefinition, SignalValue
from app.models.wr import WrRollupDaily

PARIS = ZoneInfo("Europe/Paris")
BAND_ORDER = ("green", "yellow", "orange", "red")
MAD_TO_SIGMA = 1.4826


@dataclass(frozen=True)
class Verdict:
    band: str
    baseline: float
    scale: float
    z: float


def judge(value: float, history: list[float], bands: dict) -> Verdict | None:
    if len(history) < int(bands.get("min_history_days", 14)):
        return None
    baseline = statistics.median(history)
    mad = statistics.median(abs(point - baseline) for point in history)
    scale = max(mad * MAD_TO_SIGMA, float(bands.get("min_scale", 1)))
    deviation = (value - baseline) / scale
    direction = bands.get("direction", "both")
    worrying = {"high": deviation, "low": -deviation}.get(direction, abs(deviation))
    band = "green"
    for name in ("yellow", "orange", "red"):
        if worrying >= float(bands[name]):
            band = name
    return Verdict(band=band, baseline=baseline, scale=scale, z=round(deviation, 2))


def measured_at(day: date) -> datetime:
    return datetime.combine(day, time(23, 59, 59), tzinfo=PARIS)


def touched_days(db: Session, *, user: User, window_from: datetime, window_to: datetime) -> list[date]:
    return sorted(set(db.scalars(
        select(WrRollupDaily.local_date).where(
            WrRollupDaily.user_id == user.id, WrRollupDaily.computed_at > window_from,
            WrRollupDaily.computed_at <= window_to)
    )))


def evaluate_days(db: Session, *, user: User, days: list[date]) -> list[SignalValue]:
    definitions = db.scalars(
        select(SignalDefinition).where(SignalDefinition.domain == "wr", SignalDefinition.active.is_(True))
    ).all()
    written: list[SignalValue] = []
    for definition in definitions:
        domain, metric = definition.source.removeprefix("wr_rollups_daily:").split(".", 1)
        window = int(definition.baseline_window_days or 28)
        bands = definition.bands or {}
        skip_zero = bool(bands.get("skip_zero"))
        for day in days:
            series = _series(db, user, domain, metric, day - timedelta(days=window), day)
            db.execute(delete(SignalValue).where(SignalValue.signal_code == definition.code,
                                                 SignalValue.measured_at == measured_at(day)))
            value = series.pop(day, None)
            if value is None or (skip_zero and value == 0):
                continue
            history = [point for point in series.values() if not (skip_zero and point == 0)]
            verdict = judge(value, history, bands)
            if verdict is None:
                continue
            row = SignalValue(
                signal_code=definition.code, measured_at=measured_at(day), value=value, band=verdict.band,
                flags={"flag": verdict.band != "green", "unexplained": verdict.band != "green"}, stale=False,
                detail={"user_id": str(user.id), "local_date": day.isoformat(), "baseline": verdict.baseline,
                        "scale": verdict.scale, "z": verdict.z, "history_days": len(history),
                        "direction": bands.get("direction", "both")},
            )
            db.add(row)
            written.append(row)
    db.flush()
    return written


def band_at_least(band: str | None, minimum: str) -> bool:
    return band in BAND_ORDER and BAND_ORDER.index(band) >= BAND_ORDER.index(minimum)


def _series(db: Session, user: User, domain: str, metric: str, first: date, last: date) -> dict[date, float]:
    rows = db.execute(
        select(WrRollupDaily.local_date, WrRollupDaily.metrics).where(
            WrRollupDaily.user_id == user.id, WrRollupDaily.domain == domain,
            WrRollupDaily.local_date >= first, WrRollupDaily.local_date <= last)
    ).all()
    return {day: float(metrics[metric]) for day, metrics in rows if metrics.get(metric) is not None}
