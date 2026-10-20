"""Moteur des signaux Pulse hors montre, signalements subjectifs et board (spec Pulse §3.1, §4, §14 ;
cartes ACT-PLS-08, ACT-PLS-05 et familles partielles de V8). Code pur, aucun modèle.

Signaux `pulse.*` de la table PARTAGÉE `signal_definitions` (semés inactifs, bascule SQL par code).
Une valeur par signal et par utilisateur dans `signal_values` (`detail.user_id` : la table n'a pas de
colonne utilisateur) ; un refresh qui retrouve la même valeur et la même bande rafraîchit seulement
`measured_at`, l'historique ne garde donc que les changements. Pas de donnée (aucun repas, aucune
séance prévue, aucun signalement du jour) : rien n'est écrit, le board affiche `no_data`.

Bandes (`bands.kind`) : `high` (plus c'est haut, plus ça inquiète), `low` (ratio sous la cible),
`info` (aucune bande, jamais de flag). Fraîcheur `bands.freshness_minutes` : au-delà, le board marque
la valeur `stale`. Pulse lit le planning (charge du jour) sans jamais l'écrire.

Familles non codées : montre (sommeil, cardio, pas), hydratation et nutrition à cible personnalisée,
dette de volume et récupération (pas de programme), médical structuré.
"""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.imperium import ImperiumMission, PulseMeal, PulsePainLog, PulseWorkout
from app.models.pulse import PulseSubjectiveReport
from app.models.toolbox import SignalDefinition, SignalValue
from app.schemas.pulse_signals import (
    BoardRead,
    BoardSignalRead,
    SubjectiveReportCreate,
    SubjectiveReportListResponse,
    SubjectiveReportRead,
)
from app.services.events.emitter import build_event
from app.services.params import get_parameter
from app.services.path import fasting
from app.services.pulse import food_stock, red_flags

PARIS = ZoneInfo("Europe/Paris")
BAND_ORDER = ("green", "yellow", "orange", "red")
SUBJECTIVE = ("pulse.pain_active", "pulse.fatigue_reported", "pulse.mood_reported", "pulse.stress_reported")


class ReportNotFoundError(ValueError):
    pass


class ReportIdempotencyConflictError(ValueError):
    pass


class ReportInFutureError(ValueError):
    pass


@dataclass
class RefreshStats:
    computed: int = 0
    written: int = 0
    unchanged: int = 0
    no_data: int = 0


def board_enabled(db: Session) -> bool:
    return bool(get_parameter(db, "pulse.board_enabled", default=False))


def reports_enabled(db: Session) -> bool:
    return bool(get_parameter(db, "pulse.reports_enabled", default=False))


def band_for(value: float, bands: dict) -> str | None:
    """Bande d'une valeur selon `bands.kind` (fonction pure)."""
    kind = bands.get("kind", "info")
    if kind == "high":
        band = "green"
        for name in ("yellow", "orange", "red"):
            if name in bands and value >= float(bands[name]):
                band = name
        return band
    if kind == "low":
        if value >= float(bands["green"]):
            return "green"
        if "yellow" in bands and value >= float(bands["yellow"]):
            return "yellow"
        return bands.get("floor", "red")
    return None


# --- Calculs par signal : (valeur, détail) ou None sans donnée --------------------------------------

def _pain_active(db: Session, user: User, now: datetime):
    rows = db.execute(select(PulsePainLog.id, PulsePainLog.severity).where(
        PulsePainLog.user_id == user.id, PulsePainLog.resolved_at.is_(None), PulsePainLog.noted_at <= now)).all()
    return (max((row.severity for row in rows), default=0),
            {"open_count": len(rows), "pain_log_ids": sorted(str(row.id) for row in rows)})


def _reported(kind: str):
    def compute(db: Session, user: User, now: datetime):
        start = datetime.combine(now.astimezone(PARIS).date(), time.min, tzinfo=PARIS)
        row = db.execute(select(PulseSubjectiveReport.id, PulseSubjectiveReport.level).where(
            PulseSubjectiveReport.user_id == user.id, PulseSubjectiveReport.kind == kind,
            PulseSubjectiveReport.reported_at >= start, PulseSubjectiveReport.reported_at <= now,
        ).order_by(PulseSubjectiveReport.reported_at.desc(), PulseSubjectiveReport.created_at.desc()).limit(1)).first()
        return None if row is None else (row.level, {"report_id": str(row.id)})
    return compute


def _last_meal_hours(db: Session, user: User, now: datetime):
    row = db.execute(select(PulseMeal.id, PulseMeal.eaten_at).where(
        PulseMeal.user_id == user.id, PulseMeal.status == "confirmed", PulseMeal.eaten_at <= now,
    ).order_by(PulseMeal.eaten_at.desc()).limit(1)).first()
    if row is None:
        return None
    return round((now - row.eaten_at).total_seconds() / 3600, 1), {
        "meal_id": str(row.id), "fasting": fasting.window_fast(db, user, now) is not None}


def _training_adherence_7d(db: Session, user: User, now: datetime):
    rows = db.execute(select(PulseWorkout.status, func.count()).where(
        PulseWorkout.user_id == user.id, PulseWorkout.planned_at > now - timedelta(days=7),
        PulseWorkout.planned_at <= now, PulseWorkout.status != "in_progress",
    ).group_by(PulseWorkout.status)).all()
    counts = {status: count for status, count in rows}
    planned = sum(counts.values())
    if planned == 0:
        return None
    return round(counts.get("completed", 0) / planned, 2), {"completed": counts.get("completed", 0),
                                                            "planned": planned}


def _workload_today_h(db: Session, user: User, now: datetime):
    start = datetime.combine(now.astimezone(PARIS).date(), time.min, tzinfo=PARIS)
    rows = db.execute(select(ImperiumMission.estimated_minutes).where(
        ImperiumMission.user_id == user.id, ImperiumMission.status.in_(("backlog", "active")),
        ImperiumMission.planned_start_at >= start, ImperiumMission.planned_start_at < start + timedelta(days=1),
    )).all()
    minutes = sum(row.estimated_minutes or 0 for row in rows)
    return round(minutes / 60, 2), {"missions": len(rows),
                                    "without_estimate": sum(1 for row in rows if row.estimated_minutes is None)}


COMPUTE = {
    "pulse.pain_active": _pain_active,
    "pulse.fatigue_reported": _reported("fatigue"),
    "pulse.mood_reported": _reported("mood"),
    "pulse.stress_reported": _reported("stress"),
    "pulse.last_meal_hours": _last_meal_hours,
    "pulse.training_adherence_7d": _training_adherence_7d,
    "pulse.workload_today_h": _workload_today_h,
}


def refresh(db: Session, *, current_user: User, now: datetime | None = None,
            codes: tuple[str, ...] | None = None) -> RefreshStats:
    """Recalcule les signaux `pulse.*` actifs (flush seulement)."""
    now = now or datetime.now(UTC)
    query = select(SignalDefinition).where(SignalDefinition.domain == "pulse", SignalDefinition.active.is_(True))
    if codes is not None:
        query = query.where(SignalDefinition.code.in_(codes))
    stats = RefreshStats()
    for definition in db.scalars(query.order_by(SignalDefinition.code)):
        compute = COMPUTE.get(definition.code)
        if compute is None:
            continue
        stats.computed += 1
        result = compute(db, current_user, now)
        if result is None:
            stats.no_data += 1
            continue
        value, detail = result
        bands = definition.bands or {}
        band = band_for(value, bands)
        if bands.get("fasting_neutral") and detail.get("fasting"):
            band = "green"  # jeûne en cours : un long délai depuis le repas est attendu
        last = _latest(db, current_user, definition.code)
        if last is not None and last.value is not None and float(last.value) == float(value) and last.band == band:
            last.measured_at = now
            stats.unchanged += 1
            continue
        db.add(SignalValue(signal_code=definition.code, measured_at=now, value=value, band=band,
                           flags={"flag": band is not None and band != "green"}, stale=False,
                           detail={"user_id": str(current_user.id), **detail}))
        stats.written += 1
    db.flush()
    return stats


def _latest(db: Session, user: User, code: str) -> SignalValue | None:
    return db.scalar(select(SignalValue).where(
        SignalValue.signal_code == code, SignalValue.detail["user_id"].astext == str(user.id),
    ).order_by(SignalValue.measured_at.desc(), SignalValue.created_at.desc()).limit(1))


def board(db: Session, *, current_user: User, now: datetime | None = None) -> BoardRead:
    """Dernière valeur de chaque signal actif, âge et fraîcheur ; red flags ouverts en tête."""
    now = now or datetime.now(UTC)
    signals = []
    for definition in db.scalars(select(SignalDefinition).where(
            SignalDefinition.domain == "pulse", SignalDefinition.active.is_(True)).order_by(SignalDefinition.code)):
        bands = definition.bands or {}
        last = _latest(db, current_user, definition.code)
        if last is None:
            signals.append(BoardSignalRead(code=definition.code, label_fr=definition.label_fr, unit=definition.unit,
                                           state="no_data"))
            continue
        age_min = int((now - last.measured_at).total_seconds() // 60)
        stale = age_min > int(bands.get("freshness_minutes", 60))
        signals.append(BoardSignalRead(
            code=definition.code, label_fr=definition.label_fr, unit=definition.unit,
            state="stale" if stale else "fresh", value=float(last.value) if last.value is not None else None,
            band=last.band, flag=bool((last.flags or {}).get("flag")) and not stale, measured_at=last.measured_at,
            age_min=age_min, detail={k: v for k, v in (last.detail or {}).items() if k != "user_id"},
        ))
    flags = [flag for flag in signals if flag.flag]
    worst = max((BAND_ORDER.index(s.band) for s in flags if s.band in BAND_ORDER), default=0)
    return BoardRead(generated_at=now, red_flags=red_flags.list_flags(db, current_user=current_user).items,
                     signals=signals, flags_count=len(flags), max_band=BAND_ORDER[worst])


# --- Signalements subjectifs ----------------------------------------------------------------------

def create_report(db: Session, *, current_user: User, payload: SubjectiveReportCreate,
                  idempotency_key: str) -> tuple[SubjectiveReportRead, bool]:
    fingerprint = food_stock.request_hash("pulse.report.create", payload.model_dump(mode="json"))
    existing = db.scalar(select(PulseSubjectiveReport).where(
        PulseSubjectiveReport.user_id == current_user.id, PulseSubjectiveReport.idempotency_key == idempotency_key))
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise ReportIdempotencyConflictError("Idempotency key already used with a different report.")
        return SubjectiveReportRead.model_validate(existing), True
    now = datetime.now(UTC)
    if payload.reported_at is not None and payload.reported_at > now + timedelta(minutes=5):
        raise ReportInFutureError("A report cannot be dated in the future.")
    report = PulseSubjectiveReport(id=uuid4(), user_id=current_user.id, kind=payload.kind, level=payload.level,
                                   reported_at=payload.reported_at or now, idempotency_key=idempotency_key,
                                   request_hash=fingerprint)
    db.add(report)
    db.flush()
    db.refresh(report)
    event = build_event(
        db, user_id=current_user.id, event_type="pulse.report.logged",
        payload={"report_id": str(report.id), "kind": report.kind},
        idempotency_key=f"pulse.report.logged.{report.id}", source_app=SourceApp.pulse,
        privacy_level=PrivacyLevel.high,
    )
    db.add(event)
    refresh(db, current_user=current_user, now=now, codes=SUBJECTIVE)
    from app.services.pulse import sentinel  # import tardif : la sentinelle lit ce module

    sentinel.on_user_report(db, current_user=current_user, signal_code=f"pulse.{report.kind}_reported",
                            subject_ref=f"report:{report.id}", now=now, causation_id=event.event_id)
    read = SubjectiveReportRead.model_validate(report)
    db.commit()
    return read, False


def list_reports(db: Session, *, current_user: User, day) -> SubjectiveReportListResponse:
    start = datetime.combine(day, time.min, tzinfo=PARIS)
    rows = db.scalars(select(PulseSubjectiveReport).where(
        PulseSubjectiveReport.user_id == current_user.id, PulseSubjectiveReport.reported_at >= start,
        PulseSubjectiveReport.reported_at < start + timedelta(days=1)).order_by(PulseSubjectiveReport.reported_at))
    return SubjectiveReportListResponse(items=[SubjectiveReportRead.model_validate(row) for row in rows])


def delete_report(db: Session, *, current_user: User, report_id) -> None:
    report = db.get(PulseSubjectiveReport, report_id)
    if report is None or report.user_id != current_user.id:
        raise ReportNotFoundError("Report not found.")
    db.delete(report)
    _forget_values(db, current_user, [str(report.id)])
    db.commit()


def delete_all_reports(db: Session, *, current_user: User) -> int:
    ids = [str(i) for i in db.scalars(select(PulseSubjectiveReport.id).where(
        PulseSubjectiveReport.user_id == current_user.id))]
    db.execute(delete(PulseSubjectiveReport).where(PulseSubjectiveReport.user_id == current_user.id))
    _forget_values(db, current_user, ids)
    db.commit()
    return len(ids)


def _forget_values(db: Session, user: User, report_ids: list[str]) -> None:
    """Suppression réelle : les valeurs de signal tirées d'un signalement supprimé partent avec lui."""
    if report_ids:
        db.execute(delete(SignalValue).where(
            SignalValue.signal_code.in_(SUBJECTIVE[1:]), SignalValue.detail["user_id"].astext == str(user.id),
            SignalValue.detail["report_id"].astext.in_(report_ids)))


def forget_pain(db: Session, *, current_user: User, pain_log_id=None) -> None:
    """Suppression réelle d'une douleur (ou de toutes) : ses valeurs `pulse.pain_active` partent aussi,
    puis le signal est recalculé sur ce qui reste."""
    query = delete(SignalValue).where(SignalValue.signal_code == "pulse.pain_active",
                                      SignalValue.detail["user_id"].astext == str(current_user.id))
    if pain_log_id is not None:
        query = query.where(SignalValue.detail["pain_log_ids"].contains([str(pain_log_id)]))
    db.execute(query)
    refresh(db, current_user=current_user, codes=("pulse.pain_active",))


def refresh_job(ctx, window) -> None:
    """Job `pulse.signals_refresh` (semé désactivé) : recalcule les signaux actifs de l'utilisateur."""
    from app.services.wr.metrics import _job_user

    now = window.to_ts or datetime.now(UTC)
    ctx.cursor_ts = now
    user = _job_user(ctx.db)
    if user is None:
        ctx.items_in = ctx.items_out = 0
        ctx.detail = {"skip": "no_user"}
        return
    stats = refresh(ctx.db, current_user=user, now=now)
    ctx.db.commit()
    ctx.items_in, ctx.items_out = stats.computed, stats.written
    ctx.detail = asdict(stats)
