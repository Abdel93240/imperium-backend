"""Plan stratégique glissant (spec WR §3.5, §8 ; carte V20 ACT-WR-18). Code pur, aucun appel modèle.

Le plan initial est SAISI par l'utilisateur (POST plan/initial → status proposed), puis validé par
lui (activate → active ; l'éventuelle version active passe superseded). Retour arrière : supersede,
jamais de DELETE. Une seule version active par utilisateur (index partiel).

Plan courant = `v_plan_current` (version active + deltas appliqués, dans l'ordre) passé par
l'applicateur : move (params.to_week), add (params : title_fr, week, params), remove, modify
(params : title_fr et/ou params ; la semaine ne change que par move). Un delta s'applique en entier
ou pas du tout : ref absente (ou déjà présente pour add), semaine hors horizon, champ interdit →
rejet motivé. La génération (régénérations, deltas hebdo) arrive en V23/V24.
"""

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import IdempotencyStatus, PrivacyLevel, SourceApp
from app.models.idempotency import IdempotencyKey
from app.models.wr import PlanVersion
from app.schemas.wr import PlanCurrentRead, PlanInitialRequest, PlanItem, PlanVersionRead
from app.services.events.emitter import build_event
from app.services.params import get_parameter

MODIFIABLE_FIELDS = frozenset({"title_fr", "params"})


class PlanVersionNotFoundError(LookupError):
    pass


class PlanStateError(RuntimeError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


class PlanDeltaRejectedError(ValueError):
    def __init__(self, reasons: list[str]) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = reasons


def plan_enabled(db: Session) -> bool:
    return bool(get_parameter(db, "wr.plan_enabled", default=False))


def horizon_weeks(horizon_start, horizon_end) -> int:
    return -(-((horizon_end - horizon_start).days + 1) // 7)


def apply_operations(plan: dict, operations: list[dict], *, weeks: int) -> dict:
    """Applique un delta en entier sur une copie du plan ; un seul refus rejette tout le delta."""
    items = {item["ref"]: dict(item) for item in plan.get("items", [])}
    reasons: list[str] = []
    for index, operation in enumerate(operations, start=1):
        kind, ref = operation.get("op"), operation.get("target_ref")
        params = operation.get("params") or {}
        if kind == "add":
            if ref in items:
                reasons.append(f"op {index} add : {ref} existe déjà")
                continue
            try:
                item = PlanItem.model_validate({"ref": ref, **params})
            except ValidationError:
                reasons.append(f"op {index} add : élément invalide (ref, title_fr, week)")
                continue
            if item.week > weeks:
                reasons.append(f"op {index} add : semaine {item.week} hors horizon ({weeks})")
                continue
            items[ref] = item.model_dump()
        elif kind not in ("move", "remove", "modify"):
            reasons.append(f"op {index} : opération inconnue {kind!r}")
        elif ref not in items:
            reasons.append(f"op {index} {kind} : {ref} absent du plan")
        elif kind == "remove":
            del items[ref]
        elif kind == "move":
            to_week = params.get("to_week")
            if not isinstance(to_week, int) or isinstance(to_week, bool) or not 1 <= to_week <= weeks:
                reasons.append(f"op {index} move : semaine {to_week!r} hors horizon ({weeks})")
                continue
            items[ref]["week"] = to_week
        else:
            forbidden = sorted(set(params) - MODIFIABLE_FIELDS)
            if forbidden or not params:
                reasons.append(f"op {index} modify : champs non modifiables {forbidden or '(aucun champ)'}")
                continue
            candidate = {**items[ref], **params}
            try:
                items[ref] = PlanItem.model_validate(candidate).model_dump()
            except ValidationError:
                reasons.append(f"op {index} modify : élément invalide après modification")
    if reasons:
        raise PlanDeltaRejectedError(reasons)
    return {**plan, "items": list(items.values())}


def current_plan(db: Session, *, current_user: User) -> PlanCurrentRead | None:
    row = db.execute(
        text("SELECT plan_version_id, horizon_start, horizon_end, plan, origin, activated_at, applied_deltas "
             "FROM v_plan_current WHERE user_id = :user_id"),
        {"user_id": current_user.id},
    ).mappings().first()
    if row is None:
        return None
    weeks = horizon_weeks(row["horizon_start"], row["horizon_end"])
    plan = row["plan"]
    for delta in row["applied_deltas"]:
        plan = apply_operations(plan, delta["operations"], weeks=weeks)
    return PlanCurrentRead(
        plan_version_id=row["plan_version_id"], horizon_start=row["horizon_start"], horizon_end=row["horizon_end"],
        origin=row["origin"], activated_at=row["activated_at"], plan=plan,
        applied_delta_ids=[delta["delta_id"] for delta in row["applied_deltas"]],
    )


def list_versions(db: Session, *, current_user: User) -> list[PlanVersionRead]:
    rows = db.scalars(
        select(PlanVersion).where(PlanVersion.user_id == current_user.id).order_by(PlanVersion.created_at.desc())
    ).all()
    return [PlanVersionRead.model_validate(row) for row in rows]


def create_initial(
    db: Session,
    *,
    current_user: User,
    request: PlanInitialRequest,
    idempotency_key: str,
    request_path: str,
    now: datetime | None = None,
) -> PlanVersionRead:
    fingerprint = hashlib.sha256(
        json.dumps({"ns": "wr.plan.initial", **request.model_dump(mode="json")}, sort_keys=True).encode()
    ).hexdigest()
    previous = db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == current_user.id, IdempotencyKey.idempotency_key == idempotency_key
        )
    )
    if previous is not None:
        if previous.request_path != request_path or previous.request_hash != fingerprint or previous.response_body is None:
            raise PlanStateError("Idempotency key already used with a different request.", "IDEMPOTENCY_CONFLICT")
        return PlanVersionRead.model_validate(previous.response_body)

    if _active(db, current_user) is not None:
        raise PlanStateError("A plan is already active: the next versions come from regenerations.",
                             "PLAN_ALREADY_ACTIVE")
    now = now or datetime.now(UTC)
    row = PlanVersion(
        user_id=current_user.id, horizon_start=request.horizon_start, horizon_end=request.horizon_end,
        plan=request.plan.model_dump(mode="json"), origin="initial", rationale_fr=request.rationale_fr,
        status="proposed", created_at=now,
    )
    db.add(row)
    db.flush()
    _emit(db, current_user, "planning.plan.proposed", row, {}, now)
    read = PlanVersionRead.model_validate(row)
    db.add(IdempotencyKey(
        user_id=current_user.id, idempotency_key=idempotency_key, request_method="POST", request_path=request_path,
        request_hash=fingerprint, status=IdempotencyStatus.completed, response_status_code=201,
        response_body=read.model_dump(mode="json"),
    ))
    db.commit()
    return read


def activate(db: Session, *, current_user: User, version_id: UUID, now: datetime | None = None) -> PlanVersionRead:
    """Validation par l'utilisateur : la version devient active, l'ancienne active passe superseded."""
    row = _owned(db, current_user, version_id)
    if row.status == "active":
        return PlanVersionRead.model_validate(row)
    if row.status == "superseded":
        raise PlanStateError("A superseded plan version cannot be reactivated.", "PLAN_SUPERSEDED")
    now = now or datetime.now(UTC)
    previous = _active(db, current_user)
    if previous is not None:
        previous.status, previous.superseded_at = "superseded", now
        previous.superseded_reason_fr = f"Remplacée par la version {row.id}."
        db.flush()
    row.status, row.activated_at = "active", now
    db.flush()
    _emit(db, current_user, "planning.plan.activated", row,
          {"superseded_id": str(previous.id) if previous is not None else None}, now)
    db.commit()
    return PlanVersionRead.model_validate(row)


def supersede(
    db: Session, *, current_user: User, version_id: UUID, reason_fr: str, now: datetime | None = None
) -> PlanVersionRead:
    """Retour arrière : la version (proposée ou active) passe superseded ; déjà superseded, rendue telle quelle."""
    row = _owned(db, current_user, version_id)
    if row.status != "superseded":
        now = now or datetime.now(UTC)
        was_active = row.status == "active"
        row.status, row.superseded_at, row.superseded_reason_fr = "superseded", now, reason_fr
        db.flush()
        _emit(db, current_user, "planning.plan.superseded", row, {"was_active": was_active}, now)
        db.commit()
    return PlanVersionRead.model_validate(row)


def _active(db: Session, current_user: User) -> PlanVersion | None:
    return db.scalar(select(PlanVersion).where(PlanVersion.user_id == current_user.id,
                                               PlanVersion.status == "active").with_for_update())


def _owned(db: Session, current_user: User, version_id: UUID) -> PlanVersion:
    row = db.get(PlanVersion, version_id, with_for_update=True)
    if row is None or row.user_id != current_user.id:
        raise PlanVersionNotFoundError("Plan version not found.")
    return row


def _emit(db: Session, current_user: User, event_type: str, row: PlanVersion, extra: dict, now: datetime) -> None:
    db.add(build_event(
        db, user_id=current_user.id, event_type=event_type,
        payload={"plan_version_id": str(row.id), "origin": row.origin,
                 "origin_ref": str(row.origin_ref) if row.origin_ref else None,
                 "horizon_start": row.horizon_start.isoformat(), "horizon_end": row.horizon_end.isoformat(),
                 "items": len(row.plan.get("items", [])), **extra},
        idempotency_key=f"{event_type}.{row.id}", source_app=SourceApp.imperium,
        privacy_level=PrivacyLevel.medium, occurred_at=now,
    ))
    db.flush()
