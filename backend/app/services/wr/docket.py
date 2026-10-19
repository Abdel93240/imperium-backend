"""Docket du WR : dépôt, priorité, portage, décision forcée, rouge (spec WR §3.1, §7).

priority = severity_w × impact_estimate × freshness × confidence_factor, avec
freshness = exp(−âge_jours / wr.docket_halflife_days) et confidence_factor = 0,5 + confidence/200.
Un item sans confidence (dépôt déterministe, pas de verdict de modèle) prend le facteur 1.

Un item qui remplit une classe d'auto-acceptation activée par l'utilisateur (autoaccept.py)
est validé d'office au dépôt, jamais un rouge. Une décision ne fait qu'enregistrer le choix de
l'utilisateur : rien n'est appliqué ici
(les consommateurs — plan, croyances — liront les items validés). Le rouge notifie tout de
suite et attend la décision, il n'applique rien.
"""

import hashlib
import json
import math
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import IdempotencyStatus, PrivacyLevel, SourceApp
from app.models.idempotency import IdempotencyKey
from app.models.wr import WrDocketItem
from app.schemas.wr import DocketDecisionRequest, DocketItemRead
from app.services.events.emitter import build_event
from app.services.notifications import notify
from app.services.params import get_parameter
from app.services.wr import autoaccept

ITEM_TYPES = frozenset({
    "chain_proposal", "pattern_new", "pattern_contradiction", "anomaly", "belief_review_due",
    "user_question", "plan_delta_proposal", "autoaccept_spotcheck", "investigation_result", "red_flag_ref",
})
DOMAINS = frozenset({"pulse", "wr", "daily", "vector", "path", "vault", "imperium", "system"})
SOURCE_WORKERS = frozenset({"w1", "w2", "w3", "w4", "phase1", "phase3", "manual"})
SEVERITY_WEIGHTS = {"normal": 1, "elevated": 2, "red": 4}
OPEN_STATUSES = ("pending", "presented", "deferred")
# Mode light du walker (spec WR §9 P4) : rouges, décisions forcées, contradictions, deltas de plan.
LIGHT_ITEM_TYPES = frozenset({"pattern_contradiction", "plan_delta_proposal"})


class DocketValidationError(ValueError):
    pass


class DocketItemNotFoundError(LookupError):
    pass


class DocketStateError(RuntimeError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


class DocketIdempotencyConflictError(RuntimeError):
    pass


def compute_priority(
    *, severity: str, impact_estimate: int, age_days: float, confidence: int | None, halflife_days: float
) -> float:
    freshness = math.exp(-max(age_days, 0.0) / halflife_days)
    confidence_factor = 1.0 if confidence is None else 0.5 + confidence / 200
    return SEVERITY_WEIGHTS[severity] * impact_estimate * freshness * confidence_factor


def create_item(
    db: Session,
    *,
    current_user: User,
    item_type: str,
    domain: str,
    title_fr: str,
    payload: dict,
    evidence_refs: dict,
    impact_estimate: int,
    source_worker: str,
    severity: str = "normal",
    confidence: int | None = None,
    now: datetime | None = None,
) -> WrDocketItem:
    """Dépose un item (flush seulement : l'appelant committe avec son propre travail)."""
    if item_type not in ITEM_TYPES:
        raise DocketValidationError(f"Unknown docket item_type '{item_type}'.")
    if domain not in DOMAINS:
        raise DocketValidationError(f"Unknown docket domain '{domain}'.")
    if source_worker not in SOURCE_WORKERS:
        raise DocketValidationError(f"Unknown docket source_worker '{source_worker}'.")
    if severity not in SEVERITY_WEIGHTS:
        raise DocketValidationError(f"Unknown docket severity '{severity}'.")
    if not 1 <= impact_estimate <= 5:
        raise DocketValidationError("impact_estimate must be between 1 and 5.")
    if confidence is not None and not 0 <= confidence <= 100:
        raise DocketValidationError("confidence must be between 0 and 100.")
    if not title_fr.strip():
        raise DocketValidationError("title_fr must not be empty.")

    now = now or datetime.now(UTC)
    item = WrDocketItem(
        id=uuid4(), user_id=current_user.id, item_type=item_type, domain=domain, title_fr=title_fr,
        payload=payload, evidence_refs=evidence_refs, confidence=confidence, impact_estimate=impact_estimate,
        severity=severity, status="pending", consecutive_defers=0, force_decision=False,
        source_worker=source_worker, created_at=now,
        priority=Decimal(str(compute_priority(
            severity=severity, impact_estimate=impact_estimate, age_days=0, confidence=confidence,
            halflife_days=_halflife(db),
        ))),
    )
    db.add(item)
    db.flush()
    created = _emit(db, current_user, "planning.docket.item_created", item, occurred_at=now)
    if severity == "red":
        notify(
            db, severity="red", domain="wr", message_fr=f"Point rouge à trancher : {title_fr}",
            ref=("wr_docket_item", item.id),
        )
        db.add(build_event(
            db, user_id=current_user.id, event_type="planning.docket.red_notified",
            payload={"item_id": str(item.id), "severity": "red"},
            idempotency_key=f"planning.docket.red_notified.{item.id}", causation_id=created.event_id,
            privacy_level=PrivacyLevel.medium, occurred_at=now,
        ))
        db.flush()
    elif item_type != "autoaccept_spotcheck":
        autoaccept_class = autoaccept.matching_class(db, item, now=now)
        if autoaccept_class is not None:
            _auto_accept(db, current_user, item, autoaccept_class, created, now)
    return item


def _auto_accept(db: Session, current_user: User, item: WrDocketItem, autoaccept_class, created, now: datetime) -> None:
    """Validé d'office par une classe active ; une part tirée sur l'id revient en contrôle."""
    item.status = "validated"
    item.decided_at = now
    item.autoaccept_class_id = autoaccept_class.id
    db.flush()
    spotcheck = None
    if autoaccept.in_spotcheck(db, item.id):
        spotcheck = create_item(
            db, current_user=current_user, item_type="autoaccept_spotcheck", domain=item.domain,
            title_fr=f"Contrôle : {item.title_fr}",
            payload={"item_id": str(item.id), "item_type": item.item_type, "payload": item.payload},
            evidence_refs={"docket_item_id": str(item.id), "evidence_refs": item.evidence_refs},
            impact_estimate=item.impact_estimate, source_worker=item.source_worker, confidence=item.confidence,
            now=now,
        )
        spotcheck.autoaccept_class_id = autoaccept_class.id
        db.flush()
    _emit(db, current_user, "planning.docket.item_autoaccepted", item, causation_id=created.event_id,
          extra={"class_id": str(autoaccept_class.id),
                 "spotcheck_item_id": str(spotcheck.id) if spotcheck is not None else None},
          occurred_at=now)


def list_items(
    db: Session,
    *,
    current_user: User,
    status: str | None = None,
    item_type: str | None = None,
    red_only: bool = False,
    mode: str = "full",
    now: datetime | None = None,
) -> list[DocketItemRead]:
    """Items triés : décisions forcées d'abord, puis priorité recalculée à l'instant (lecture seule)."""
    query = select(WrDocketItem).where(WrDocketItem.user_id == current_user.id)
    if status is not None:
        query = query.where(WrDocketItem.status == status)
    if item_type is not None:
        query = query.where(WrDocketItem.item_type == item_type)
    if red_only:
        query = query.where(WrDocketItem.severity == "red", WrDocketItem.status.in_(OPEN_STATUSES))
    now = now or datetime.now(UTC)
    halflife = _halflife(db)
    reads = []
    for item in db.scalars(query):
        if mode == "light" and not (
            item.severity == "red" or item.force_decision or item.item_type in LIGHT_ITEM_TYPES
        ):
            continue  # porté sans pénalité au prochain WR complet
        read = DocketItemRead.model_validate(item)
        read.priority = _fresh_priority(item, now, halflife)
        reads.append(read)
    reads.sort(key=lambda read: (not read.force_decision, -read.priority, read.created_at))
    return reads


def reprioritize(db: Session, *, current_user: User, now: datetime | None = None) -> int:
    """Recalcul persistant des priorités des items ouverts (rôle de W5 à chaque run)."""
    now = now or datetime.now(UTC)
    halflife = _halflife(db)
    items = db.scalars(
        select(WrDocketItem).where(WrDocketItem.user_id == current_user.id, WrDocketItem.status.in_(OPEN_STATUSES))
    ).all()
    for item in items:
        item.priority = Decimal(str(_fresh_priority(item, now, halflife)))
    db.flush()
    return len(items)


def decide(
    db: Session,
    *,
    current_user: User,
    item_id: UUID,
    request: DocketDecisionRequest,
    idempotency_key: str,
    request_path: str,
    now: datetime | None = None,
) -> DocketItemRead:
    fingerprint = hashlib.sha256(
        json.dumps({"ns": "wr.docket.decision", "item_id": str(item_id), **request.model_dump(mode="json")},
                   sort_keys=True).encode()
    ).hexdigest()
    previous = db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == current_user.id, IdempotencyKey.idempotency_key == idempotency_key
        )
    )
    if previous is not None:
        if previous.request_path != request_path or previous.request_hash != fingerprint or previous.response_body is None:
            raise DocketIdempotencyConflictError("Idempotency key already used with a different request.")
        return DocketItemRead.model_validate(previous.response_body)

    item = db.get(WrDocketItem, item_id, with_for_update=True)
    if item is None or item.user_id != current_user.id:
        raise DocketItemNotFoundError("Docket item not found.")
    if item.status not in OPEN_STATUSES:
        raise DocketStateError(f"Docket item already decided ({item.status}).", "DOCKET_ALREADY_DECIDED")
    if item.force_decision and request.decision == "deferred":
        raise DocketStateError("Forced decision: decide or archive, deferring is no longer allowed.",
                               "DOCKET_DECISION_FORCED")

    now = now or datetime.now(UTC)
    item.status = request.decision
    item.decided_at = now
    if request.decision_note is not None:
        item.decision_note = request.decision_note
    if request.modified_payload is not None:
        item.payload = request.modified_payload
    forced = False
    if request.decision == "deferred":
        item.consecutive_defers += 1
        if item.consecutive_defers >= int(get_parameter(db, "wr.docket_max_defers", default=3)):
            item.force_decision = forced = True
    db.flush()
    decided = _emit(db, current_user, "planning.docket.item_decided", item, suffix=idempotency_key,
                    extra={"modified": True} if request.modified_payload is not None else None, occurred_at=now)
    if forced:
        _emit(db, current_user, "planning.docket.item_forced", item, causation_id=decided.event_id, occurred_at=now)
    read = DocketItemRead.model_validate(item)
    db.add(IdempotencyKey(
        user_id=current_user.id, idempotency_key=idempotency_key, request_method="POST", request_path=request_path,
        request_hash=fingerprint, status=IdempotencyStatus.completed, response_status_code=200,
        response_body=read.model_dump(mode="json"),
    ))
    db.commit()
    return read


def _emit(db: Session, current_user: User, event_type: str, item: WrDocketItem, *, suffix: str | None = None,
          extra: dict | None = None, causation_id: str | None = None, occurred_at: datetime | None = None):
    # Payload = références seulement (spec WR §11) : jamais le contenu de l'item.
    event = build_event(
        db, user_id=current_user.id, event_type=event_type,
        payload={"item_id": str(item.id), "item_type": item.item_type, "status": item.status,
                 "defers": item.consecutive_defers, **(extra or {})},
        idempotency_key=f"{event_type}.{item.id}" + (f".{suffix}" if suffix else ""),
        source_app=SourceApp.imperium, privacy_level=PrivacyLevel.medium, causation_id=causation_id,
        occurred_at=occurred_at,
    )
    db.add(event)
    db.flush()
    return event


def _halflife(db: Session) -> float:
    return float(get_parameter(db, "wr.docket_halflife_days", default=14))


def _fresh_priority(item: WrDocketItem, now: datetime, halflife: float) -> float:
    age_days = (now - item.created_at).total_seconds() / 86400
    return compute_priority(
        severity=item.severity, impact_estimate=item.impact_estimate, age_days=age_days,
        confidence=item.confidence, halflife_days=halflife,
    )
