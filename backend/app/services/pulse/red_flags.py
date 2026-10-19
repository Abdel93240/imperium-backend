"""Règles rouges médicales RF1-RF5 (spec Pulse §3.5, §11 ; carte ACT-PLS-09). Code déterministe.

Évaluation à chaque écriture d'une douleur ou d'un relevé corporel (seules sources codées) ; seules les
règles `active` (bascule SQL en bloc, aucune route) sont lues. Une règle levée crée un
`pulse_red_flag_events` avec sa preuve (identifiants et valeurs, jamais le texte libre), émet
`pulse.red_flag.raised` et notifie avec `message_fr` TEL QUEL. Rien n'est transformé en ajustement de
plan : l'action `advise_doctor_and_pause_training` est exposée à Daily par `v_pulse_active_blocks`
jusqu'à la résolution par l'utilisateur.

Sources absentes du code (bilans structurés, FC de repos montre) : RF_lab_out_of_range et
RF_rhr_sustained ne se lèvent jamais tant que leurs entrées n'existent pas (`unavailable`).
"""

import unicodedata
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.imperium import PulseBodySnapshot, PulsePainLog
from app.models.pulse import PulseRedFlagEvent, PulseRedFlagRule
from app.schemas.pulse_health import RedFlagListResponse, RedFlagRead, RedFlagResolveRequest
from app.services import notifications
from app.services.events.emitter import build_event

NOTIFY_SEVERITY = {"advise": "normal", "advise_strong": "red", "urgent": "red"}
UNAVAILABLE_SOURCES = frozenset({"lab", "signal"})


class RedFlagNotFoundError(ValueError):
    pass


class RedFlagStateError(ValueError):
    pass


def normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return " ".join("".join(char for char in decomposed if not unicodedata.combining(char)).split())


def matched_keywords(text: str, keywords: list[str]) -> list[str]:
    haystack = normalize(text)
    return [keyword for keyword in keywords if normalize(keyword) in haystack]


def weight_trend(points: list[tuple[datetime, float]]) -> tuple[float, float] | None:
    """(écart en jours, variation en % par mois de 30 j) entre le premier et le dernier relevé ; None si < 2."""
    if len(points) < 2:
        return None
    (first_at, first_kg), (last_at, last_kg) = points[0], points[-1]
    span_days = (last_at - first_at).total_seconds() / 86400
    if span_days <= 0 or first_kg <= 0:
        return None
    return span_days, (last_kg - first_kg) / first_kg * 100 * 30 / span_days


def evaluate(db: Session, *, current_user: User, now: datetime | None = None) -> list[PulseRedFlagEvent]:
    """Évalue les règles actives (flush seulement) ; renvoie les événements nouvellement levés."""
    now = now or datetime.now(UTC)
    rules = db.scalars(select(PulseRedFlagRule).where(PulseRedFlagRule.active.is_(True))
                       .order_by(PulseRedFlagRule.code)).all()
    raised = []
    for rule in rules:
        source = rule.condition.get("source")
        if source in UNAVAILABLE_SOURCES:
            continue
        for subject_ref, evidence in _findings(db, current_user, rule, now):
            event = _raise(db, current_user, rule, subject_ref, evidence, now)
            if event is not None:
                raised.append(event)
    return raised


def _findings(db: Session, current_user: User, rule: PulseRedFlagRule, now: datetime) -> list[tuple[str, dict]]:
    condition = rule.condition
    if condition["source"] == "pain":
        logs = db.scalars(select(PulsePainLog).where(PulsePainLog.user_id == current_user.id,
                                                     PulsePainLog.resolved_at.is_(None))
                          .order_by(PulsePainLog.noted_at)).all()
        found = []
        for log in logs:
            if condition["field"] == "severity" and log.severity >= int(condition["value"]):
                found.append((f"pain:{log.id}", {"pain_log_id": str(log.id), "severity": log.severity,
                                                 "body_zone": log.body_zone}))
            elif condition["field"] == "text":
                hits = matched_keywords(" ".join(filter(None, (log.pain_type, log.limitation_notes))),
                                        list(condition["keywords"]))
                if hits:
                    found.append((f"pain:{log.id}", {"pain_log_id": str(log.id), "keywords": hits}))
        return found
    if condition["source"] == "body":
        rows = db.execute(
            select(PulseBodySnapshot.id, PulseBodySnapshot.measured_at, PulseBodySnapshot.weight_kg)
            .where(PulseBodySnapshot.user_id == current_user.id, PulseBodySnapshot.weight_kg.is_not(None),
                   PulseBodySnapshot.measured_at > now - timedelta(days=int(condition["window_days"])),
                   PulseBodySnapshot.measured_at <= now)
            .order_by(PulseBodySnapshot.measured_at)
        ).all()
        trend = weight_trend([(row.measured_at, float(row.weight_kg)) for row in rows])
        if trend is None or trend[0] < float(condition["min_span_days"]) or trend[1] >= float(condition["value"]):
            return []
        first, last = rows[0], rows[-1]
        # Sujet = dernier relevé : une nouvelle pesée après résolution peut relever la règle.
        return [(f"weight:{last.id}", {"first_snapshot_id": str(first.id), "last_snapshot_id": str(last.id),
                                       "first_kg": float(first.weight_kg), "last_kg": float(last.weight_kg),
                                       "span_days": round(trend[0], 1), "pct_per_month": round(trend[1], 2)})]
    return []


def _raise(db: Session, current_user: User, rule: PulseRedFlagRule, subject_ref: str, evidence: dict,
           now: datetime) -> PulseRedFlagEvent | None:
    seen = select(PulseRedFlagEvent.id).where(PulseRedFlagEvent.user_id == current_user.id,
                                              PulseRedFlagEvent.rule_id == rule.id)
    # Un sujet n'est levé qu'une fois ; une tendance n'a qu'un événement ouvert à la fois.
    if db.scalar(seen.where(PulseRedFlagEvent.subject_ref == subject_ref).limit(1)) is not None:
        return None
    if rule.condition["source"] == "body" and db.scalar(
            seen.where(PulseRedFlagEvent.resolved_at.is_(None)).limit(1)) is not None:
        return None
    severity = rule.severity
    event = PulseRedFlagEvent(id=uuid4(), user_id=current_user.id, rule_id=rule.id, subject_ref=subject_ref,
                              severity=severity, raised_at=now, evidence={**evidence, "rule_version": rule.version})
    db.add(event)
    db.flush()
    _emit(db, current_user, "pulse.red_flag.raised", event, rule)
    notifications.notify(db, severity=NOTIFY_SEVERITY[severity], domain="pulse", message_fr=rule.message_fr,
                         ref=("pulse_red_flag", event.id))
    return event


def list_flags(db: Session, *, current_user: User, include_resolved: bool = False) -> RedFlagListResponse:
    query = (select(PulseRedFlagEvent, PulseRedFlagRule)
             .join(PulseRedFlagRule, PulseRedFlagRule.id == PulseRedFlagEvent.rule_id)
             .where(PulseRedFlagEvent.user_id == current_user.id))
    if not include_resolved:
        query = query.where(PulseRedFlagEvent.resolved_at.is_(None))
    rows = db.execute(query.order_by(PulseRedFlagEvent.raised_at.desc())).all()
    return RedFlagListResponse(items=[_read(event, rule) for event, rule in rows])


def acknowledge(db: Session, *, current_user: User, flag_id: UUID, now: datetime | None = None) -> RedFlagRead:
    """Acquittement : l'utilisateur a lu le message. Ne lève PAS le blocage (seule la résolution le fait)."""
    event, rule = _get(db, current_user, flag_id)
    if event.acknowledged_by_user_at is None:
        event.acknowledged_by_user_at = now or datetime.now(UTC)
        _emit(db, current_user, "pulse.red_flag.acknowledged", event, rule)
    read = _read(event, rule)
    db.commit()
    return read


def resolve(db: Session, *, current_user: User, flag_id: UUID, payload: RedFlagResolveRequest,
            now: datetime | None = None) -> RedFlagRead:
    event, rule = _get(db, current_user, flag_id)
    if event.resolved_at is not None:
        raise RedFlagStateError("Red flag already resolved.")
    reason = (payload.reason or "").strip() or None
    if payload.resolution == "dismissed_with_reason" and reason is None:
        raise RedFlagStateError("A reason is required to dismiss a red flag.")
    now = now or datetime.now(UTC)
    event.acknowledged_by_user_at = event.acknowledged_by_user_at or now
    event.resolution, event.resolution_reason, event.resolved_at = payload.resolution, reason, now
    _emit(db, current_user, "pulse.red_flag.resolved", event, rule, resolution=payload.resolution)
    read = _read(event, rule)
    db.commit()
    return read


def _get(db: Session, current_user: User, flag_id: UUID) -> tuple[PulseRedFlagEvent, PulseRedFlagRule]:
    event = db.get(PulseRedFlagEvent, flag_id, with_for_update=True)
    if event is None or event.user_id != current_user.id:
        raise RedFlagNotFoundError("Red flag not found.")
    return event, db.get(PulseRedFlagRule, event.rule_id)


def _read(event: PulseRedFlagEvent, rule: PulseRedFlagRule) -> RedFlagRead:
    return RedFlagRead(
        id=event.id, rule_code=rule.code, severity=event.severity, action=rule.action, message_fr=rule.message_fr,
        raised_at=event.raised_at, evidence=event.evidence, acknowledged_at=event.acknowledged_by_user_at,
        resolution=event.resolution, resolution_reason=event.resolution_reason, resolved_at=event.resolved_at,
        blocks_training=rule.action == "advise_doctor_and_pause_training" and event.resolved_at is None,
    )


def _emit(db: Session, current_user: User, event_type: str, event: PulseRedFlagEvent, rule: PulseRedFlagRule,
          **extra) -> None:
    db.add(build_event(
        db, user_id=current_user.id, event_type=event_type,
        payload={"red_flag_id": str(event.id), "rule_code": rule.code, "severity": event.severity,
                 "action": rule.action, **extra},
        idempotency_key=f"{event_type}.{event.id}", source_app=SourceApp.pulse, privacy_level=PrivacyLevel.high,
    ))
