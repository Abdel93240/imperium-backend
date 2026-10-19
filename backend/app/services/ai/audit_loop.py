"""Audit décroissant des slots IA (doc 78 F1-13 ; spec WR §3.7, §10 ; spec Pulse §13).

Pour un slot `local_default`, une part `audit_sample_pct` des sorties locales est contre-lue par
le cloud. Ce module ne fait AUCUN appel de modèle : should_audit() dit si une sortie tombe dans
l'échantillon (tirage déterministe par slot + clé, rejouable), record_sample() enregistre le
résultat d'une contre-lecture faite par l'appelant, slot_states() mesure l'agreement par semaine
de Paris et propose une décroissance quand il tient >= cible sur `ai.audit_decay_weeks` semaines
closes, toutes postérieures au dernier changement du slot.

La décroissance est une DÉCISION UTILISATEUR (update_slot, `POST /api/wr/admin/transition`),
jamais automatique ; le job `wr.audit_weekly` (semé désactivé) ne fait que notifier la proposition.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import IdempotencyStatus, PrivacyLevel, SourceApp
from app.models.idempotency import IdempotencyKey
from app.models.toolbox import AIAuditSample, AISlotTransition
from app.schemas.wr import SlotAuditStateRead, SlotAuditWeekRead, SlotTransitionUpdateRequest
from app.services.events.emitter import build_event
from app.services.notifications import notify
from app.services.params import get_parameter

PARIS = ZoneInfo("Europe/Paris")


class UnknownSlotError(LookupError):
    pass


class SlotIdempotencyConflictError(RuntimeError):
    pass


def should_audit(db: Session, *, slot_code: str, sample_key: str) -> bool:
    """La sortie `sample_key` du slot doit-elle être contre-lue ? Toujours la même réponse pour la même clé."""
    slot = _slot(db, slot_code)
    if slot.tier != "local_default" or slot.audit_sample_pct <= 0:
        return False
    bucket = int(hashlib.sha256(f"{slot_code}:{sample_key}".encode()).hexdigest()[:8], 16) % 100
    return bucket < slot.audit_sample_pct


def record_sample(
    db: Session,
    *,
    slot_code: str,
    run_ref: UUID | None,
    local_output: dict,
    cloud_output: dict,
    cloud_model: str,
    agreement: bool,
    disagreement_class: str | None = None,
    disagreement_reason: str | None = None,
    input_payload: dict | None = None,
) -> tuple[AIAuditSample, bool]:
    """Enregistre une contre-lecture ; (ligne, créée). Rejouer le même run_ref rend la ligne existante.

    `input_payload` doit déjà sortir de l'assembleur whitelisté du slot (spec Pulse §13).
    """
    _slot(db, slot_code)
    if agreement and (disagreement_class or disagreement_reason):
        raise ValueError("A disagreement label needs agreement=false.")
    if run_ref is not None:
        existing = db.scalar(
            select(AIAuditSample).where(AIAuditSample.slot_code == slot_code, AIAuditSample.run_ref == run_ref)
        )
        if existing is not None:
            return existing, False
    sample = AIAuditSample(
        slot_code=slot_code, run_ref=run_ref, input_payload=input_payload, local_output=local_output,
        cloud_output=cloud_output, cloud_model=cloud_model[:48], agreement=agreement,
        disagreement_class=disagreement_class, disagreement_reason=disagreement_reason,
    )
    db.add(sample)
    db.flush()
    return sample, True


@dataclass(frozen=True)
class _Week:
    week_start: date
    samples: int
    agreement_pct: float


def slot_states(db: Session, *, now: datetime | None = None, weeks: int = 6) -> list[SlotAuditStateRead]:
    now = now or datetime.now(UTC)
    current_week = _monday(now.astimezone(PARIS).date())
    oldest = current_week - timedelta(weeks=weeks)
    by_slot: dict[str, list[_Week]] = {}
    for row in db.execute(
        text("SELECT slot_code, week_start, samples, agreement_pct FROM v_ai_slot_agreement_weekly "
             "WHERE week_start >= :oldest AND week_start < :current ORDER BY week_start DESC"),
        {"oldest": oldest, "current": current_week},
    ):
        by_slot.setdefault(row.slot_code, []).append(_Week(row.week_start, row.samples, float(row.agreement_pct)))

    decay_weeks = int(get_parameter(db, "ai.audit_decay_weeks", default=3))
    min_samples = int(get_parameter(db, "ai.audit_min_samples_week", default=5))
    factor = float(get_parameter(db, "ai.audit_decay_factor", default=0.5))
    floor = int(get_parameter(db, "ai.audit_floor_pct", default=5))

    states = []
    for slot in db.scalars(select(AISlotTransition).order_by(AISlotTransition.slot_code)):
        history = by_slot.get(slot.slot_code, [])
        proposed = _proposal(slot, history, current_week=current_week, decay_weeks=decay_weeks,
                             min_samples=min_samples, factor=factor, floor=floor)
        states.append(SlotAuditStateRead(
            slot_code=slot.slot_code, domain=slot.domain, tier=slot.tier, audit_sample_pct=slot.audit_sample_pct,
            agreement_target_pct=slot.agreement_target_pct, version=slot.version,
            weeks=[SlotAuditWeekRead(**week.__dict__) for week in history],
            decay_proposed=proposed is not None, proposed_audit_sample_pct=proposed,
        ))
    return states


def _proposal(slot: AISlotTransition, history: list[_Week], *, current_week: date, decay_weeks: int,
              min_samples: int, factor: float, floor: int) -> int | None:
    if slot.tier != "local_default" or slot.agreement_target_pct is None or slot.audit_sample_pct <= floor:
        return None
    # Les semaines comptées sont closes, consécutives, et commencent après le dernier changement du slot.
    changed_week = _monday(slot.updated_at.astimezone(PARIS).date()) + timedelta(weeks=1)
    expected = [current_week - timedelta(weeks=offset) for offset in range(1, decay_weeks + 1)]
    if expected[-1] < changed_week:
        return None
    if not _weeks_hold(history, expected, min_samples=min_samples, target=slot.agreement_target_pct):
        return None
    return max(floor, int(round(slot.audit_sample_pct * factor)))


def _weeks_hold(history: list[_Week], expected: list[date], *, min_samples: int, target: int) -> bool:
    measured = {week.week_start: week for week in history}
    return all(
        (week := measured.get(week_start)) is not None and week.samples >= min_samples
        and week.agreement_pct >= target
        for week_start in expected
    )


def agreement_holds(db: Session, *, slot_code: str, now: datetime | None = None) -> bool:
    """L'agreement du slot tient-il sa cible sur les `ai.audit_decay_weeks` dernières semaines closes ?"""
    slot = _slot(db, slot_code)
    if slot.agreement_target_pct is None:
        return False
    now = now or datetime.now(UTC)
    current_week = _monday(now.astimezone(PARIS).date())
    decay_weeks = int(get_parameter(db, "ai.audit_decay_weeks", default=3))
    expected = [current_week - timedelta(weeks=offset) for offset in range(1, decay_weeks + 1)]
    history = [
        _Week(row.week_start, row.samples, float(row.agreement_pct))
        for row in db.execute(
            text("SELECT week_start, samples, agreement_pct FROM v_ai_slot_agreement_weekly "
                 "WHERE slot_code = :slot AND week_start >= :oldest AND week_start < :current"),
            {"slot": slot_code, "oldest": expected[-1], "current": current_week},
        )
    ]
    return _weeks_hold(history, expected, min_samples=int(get_parameter(db, "ai.audit_min_samples_week", default=5)),
                       target=slot.agreement_target_pct)


def update_slot(
    db: Session,
    *,
    current_user: User,
    request: SlotTransitionUpdateRequest,
    idempotency_key: str,
    request_path: str,
    now: datetime | None = None,
) -> SlotAuditStateRead:
    fingerprint = hashlib.sha256(
        json.dumps({"ns": "ai.slot_transition", **request.model_dump(mode="json")}, sort_keys=True).encode()
    ).hexdigest()
    previous = db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == current_user.id, IdempotencyKey.idempotency_key == idempotency_key
        )
    )
    if previous is not None:
        if previous.request_path != request_path or previous.request_hash != fingerprint or previous.response_body is None:
            raise SlotIdempotencyConflictError("Idempotency key already used with a different request.")
        return SlotAuditStateRead.model_validate(previous.response_body)

    now = now or datetime.now(UTC)
    slot = db.scalar(
        select(AISlotTransition).where(AISlotTransition.slot_code == request.slot_code).with_for_update()
    )
    if slot is None:
        raise UnknownSlotError(f"Unknown AI slot '{request.slot_code}'.")
    before = {"audit_sample_pct": slot.audit_sample_pct, "agreement_target_pct": slot.agreement_target_pct}
    if request.audit_sample_pct is not None:
        slot.audit_sample_pct = request.audit_sample_pct
    if request.agreement_target_pct is not None:
        slot.agreement_target_pct = request.agreement_target_pct
    slot.version += 1
    slot.updated_at = now
    db.flush()
    db.add(build_event(
        db, user_id=current_user.id, event_type="decision.ai_audit.updated",
        payload={"slot_code": slot.slot_code, "version": slot.version, "previous": before,
                 "audit_sample_pct": slot.audit_sample_pct, "agreement_target_pct": slot.agreement_target_pct,
                 "reason_fr": request.reason_fr},
        idempotency_key=f"decision.ai_audit.updated.{slot.slot_code}.{slot.version}",
        source_app=SourceApp.imperium, privacy_level=PrivacyLevel.low, occurred_at=now,
    ))
    state = next(state for state in slot_states(db, now=now) if state.slot_code == slot.slot_code)
    db.add(IdempotencyKey(
        user_id=current_user.id, idempotency_key=idempotency_key, request_method="POST", request_path=request_path,
        request_hash=fingerprint, status=IdempotencyStatus.completed, response_status_code=200,
        response_body=state.model_dump(mode="json"),
    ))
    db.commit()
    return state


def agreement_by_slot(db: Session, *, week_start: date) -> dict[str, float] | None:
    """Agreement de chaque slot contre-lu dans la semaine (wr_metrics_weekly.agreement_by_slot)."""
    rows = db.execute(
        text("SELECT slot_code, agreement_pct FROM v_ai_slot_agreement_weekly WHERE week_start = :week"),
        {"week": week_start},
    ).all()
    return {row.slot_code: float(row.agreement_pct) for row in rows} or None


def audit_weekly_job(ctx, window) -> None:
    """Job `wr.audit_weekly` (lundi, semé désactivé) : notifie chaque décroissance proposée, sans l'appliquer."""
    now = window.to_ts or datetime.now(UTC)
    states = slot_states(ctx.db, now=now)
    proposals = [state for state in states if state.decay_proposed]
    week = _monday(now.astimezone(PARIS).date()).isoformat()
    sent = 0
    for state in proposals:
        note = notify(
            ctx.db, severity="normal", domain="system",
            message_fr=f"Le slot « {state.slot_code} » tient sa cible d'agreement : proposer de passer son audit "
                       f"de {state.audit_sample_pct} % à {state.proposed_audit_sample_pct} % ? (décision au WR)",
            ref=("ai_audit_decay", uuid5(NAMESPACE_URL, f"imperium:ai_audit_decay:{state.slot_code}:{week}")),
        )
        sent += note is not None
    ctx.db.commit()
    ctx.items_in, ctx.items_out = len(states), sent
    ctx.detail = {"proposals": [state.slot_code for state in proposals], "notified": sent}
    ctx.cursor_ts = now


def _slot(db: Session, slot_code: str) -> AISlotTransition:
    slot = db.scalar(select(AISlotTransition).where(AISlotTransition.slot_code == slot_code))
    if slot is None:
        raise UnknownSlotError(f"Unknown AI slot '{slot_code}'.")
    return slot


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())

