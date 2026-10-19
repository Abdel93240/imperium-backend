"""Journal des douleurs Pulse (PUL-09, doc 40 §16) sous consentement « pain ».

La douleur est une donnée d'entrée pour l'adaptation des séances (§13.3), jamais
un diagnostic. Une douleur forte (8 à 10) fait proposer à l'écran de replanifier
la journée ; rien n'est déclenché seul. Si l'utilisateur accepte (pour toute douleur
en cours, DECISION_demarrage_journee), POST /{id}/replan demande le replan (hook « pain »). Interprétation par le modèle local et
escalade : pas encore.

Même cadre que le relevé corporel (doc 08 PULSE-004) : écriture sous consentement,
événements sans détail (identifiants seulement), suppression réelle.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.imperium import PlanningReplanEvent, PulsePainLog, PulseWorkout
from app.schemas.imperium import ReplanRead
from app.schemas.pulse_health import PainLogCreate, PainLogListResponse, PainLogRead, PainReplanResponse
from app.services.events.emitter import build_event
from app.services.pulse import food_stock, health_consent, red_flags

STRONG = 8
REPLAN_MESSAGE = "Douleur forte : veux-tu replanifier ta journée ?"
MAX_ITEMS = 500


class PainLogNotFoundError(ValueError):
    pass


class PainIdempotencyConflictError(ValueError):
    pass


class PainResolvedError(ValueError):
    pass


def create_log(db: Session, *, current_user: User, payload: PainLogCreate, idempotency_key: str) -> tuple[PainLogRead, bool]:
    fingerprint = food_stock.request_hash("pulse.pain.create", payload.model_dump(mode="json"))
    existing = db.scalar(
        select(PulsePainLog).where(PulsePainLog.user_id == current_user.id, PulsePainLog.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise PainIdempotencyConflictError("Idempotency key already used with a different pain log.")
        return _read(existing), True
    health_consent.require(db, current_user, "pain")
    if payload.workout_id is not None:
        workout = db.get(PulseWorkout, payload.workout_id)
        if workout is None or workout.user_id != current_user.id:
            raise PainLogNotFoundError("Workout not found.")
    log = PulsePainLog(
        user_id=current_user.id, body_zone=payload.body_zone, side=payload.side, severity=payload.severity,
        pain_type=(payload.pain_type or "").strip() or None, limitation_notes=(payload.limitation_notes or "").strip() or None,
        workout_impact=payload.workout_impact, workout_id=payload.workout_id, noted_at=payload.noted_at or datetime.now(UTC),
        idempotency_key=idempotency_key, request_hash=fingerprint,
    )
    db.add(log)
    db.flush()
    db.refresh(log)
    _emit(db, current_user, "pulse.pain.logged", {"pain_log_id": str(log.id)}, str(log.id))
    red_flags.evaluate(db, current_user=current_user)
    read = _read(log)
    db.commit()
    return read, False


def list_logs(db: Session, *, current_user: User, include_resolved: bool = False) -> PainLogListResponse:
    query = select(PulsePainLog).where(PulsePainLog.user_id == current_user.id)
    if not include_resolved:
        query = query.where(PulsePainLog.resolved_at.is_(None))
    rows = db.scalars(query.order_by(PulsePainLog.noted_at.desc()).limit(MAX_ITEMS))
    return PainLogListResponse(items=[_read(row) for row in rows])


def open_summary(db: Session, *, current_user: User) -> tuple[int, int]:
    """(douleurs en cours, dont fortes) pour la bannière du tableau de bord."""
    severities = list(
        db.scalars(select(PulsePainLog.severity).where(PulsePainLog.user_id == current_user.id, PulsePainLog.resolved_at.is_(None)))
    )
    return len(severities), sum(1 for severity in severities if severity >= STRONG)


def resolve_log(db: Session, *, current_user: User, pain_log_id: UUID) -> PainLogRead:
    log = _get(db, current_user, pain_log_id)
    if log.resolved_at is None:
        health_consent.require(db, current_user, "pain")
        log.resolved_at = datetime.now(UTC)
        _emit(db, current_user, "pulse.pain.resolved", {"pain_log_id": str(log.id)}, str(log.id))
        db.flush()
    read = _read(log)
    db.commit()
    return read


def request_replan(
    db: Session, *, current_user: User, pain_log_id: UUID, now: datetime | None = None
) -> tuple[PainReplanResponse, bool]:
    """Replan accepté par l'utilisateur depuis une douleur en cours ; (réponse, créé).

    Relancer pendant que la demande est ouverte renvoie la même. Délai entre deux replans,
    demande déjà ouverte ou journée non démarrée : erreurs du service de replan.
    """
    from app.services.imperium import replan as replan_service

    log = _get(db, current_user, pain_log_id)
    health_consent.require(db, current_user, "pain")
    if log.resolved_at is not None:
        raise PainResolvedError("Cette douleur est résolue.")
    if log.replan_event_id is not None:
        previous = db.get(PlanningReplanEvent, log.replan_event_id)
        if previous is not None and previous.status in replan_service.OPEN_STATUSES:
            return PainReplanResponse(pain_log=_read(log), replan=ReplanRead.model_validate(previous)), False
    replan = replan_service.request_hook_replan(db, current_user=current_user, hook_type="pain", now=now)
    log = _get(db, current_user, pain_log_id)
    log.replan_event_id = replan.id
    db.flush()
    response = PainReplanResponse(pain_log=_read(log), replan=replan)
    db.commit()
    return response, True


def delete_log(db: Session, *, current_user: User, pain_log_id: UUID) -> None:
    db.delete(_get(db, current_user, pain_log_id))
    _emit(db, current_user, "pulse.pain.deleted", {"deleted": 1, "scope": "one"}, str(pain_log_id))
    db.commit()


def delete_all(db: Session, *, current_user: User) -> int:
    deleted = db.execute(delete(PulsePainLog).where(PulsePainLog.user_id == current_user.id)).rowcount or 0
    if deleted:
        _emit(db, current_user, "pulse.pain.deleted", {"deleted": deleted, "scope": "all"}, None)
    db.commit()
    return deleted


def _get(db: Session, current_user: User, pain_log_id: UUID) -> PulsePainLog:
    log = db.get(PulsePainLog, pain_log_id)
    if log is None or log.user_id != current_user.id:
        raise PainLogNotFoundError("Pain log not found.")
    return log


def _read(log: PulsePainLog) -> PainLogRead:
    strong = log.severity >= STRONG and log.resolved_at is None and log.replan_event_id is None
    return PainLogRead.model_validate(log).model_copy(
        update={"suggest_replan": strong, "replan_message": REPLAN_MESSAGE if strong else None}
    )


def _emit(db: Session, current_user: User, event_type: str, payload: dict, ref: str | None) -> None:
    db.add(
        build_event(
            db, user_id=current_user.id, event_type=event_type, payload=payload,
            idempotency_key=f"{event_type}.{ref or uuid4()}", source_app=SourceApp.pulse, privacy_level=PrivacyLevel.high,
        )
    )
