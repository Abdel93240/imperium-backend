"""Plan stratégique glissant (spec WR §3.5, §8 ; carte V20 ACT-WR-18). Code pur, aucun appel modèle.

Le plan initial est SAISI par l'utilisateur (POST plan/initial → status proposed), puis validé par
lui (activate → active ; l'éventuelle version active passe superseded). Retour arrière : supersede,
jamais de DELETE. Une seule version active par utilisateur (index partiel).

Plan courant = `v_plan_current` (version active + deltas appliqués, dans l'ordre) passé par
l'applicateur : move (params.to_week), add (params : title_fr, week, params), remove, modify
(params : title_fr et/ou params ; la semaine ne change que par move). Un delta s'applique en entier
ou pas du tout : ref absente (ou déjà présente pour add), semaine hors horizon, champ interdit →
rejet motivé. La génération des deltas hebdo arrive en V23.

Régénération choc (§8.1, carte ACT-WR-20) : déclenchée À LA MAIN (POST plan/shock) avec une raison
de la taxonomie éditable `wr.shock_taxonomy`, servie seulement si `wr.plan_enabled` et
`wr.plan_shock_enabled`. Aucun abonnement aux replans ordinaires, qui restent inchangés. Tant que
`real_ai_enabled` est faux, c'est un essai à blanc : la version proposée est la copie du plan courant
(deltas appliqués) recalée sur aujourd'hui, `model_used=dry_run`. Toujours `proposed` : elle ne
devient active que par activate ; une seule régénération proposée en attente à la fois.

Régénération mensuelle (§8.3, carte ACT-WR-21) : job `wr.monthly_regen` (semé désactivé), même
contrat que le choc avec origin=monthly_regen et sans origin_ref ; une seule par mois (Paris), rien
si le plan est éteint, sans version active ou si une régénération attend déjà.
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.auth import User
from app.models.enums import IdempotencyStatus, PrivacyLevel, SourceApp
from app.models.idempotency import IdempotencyKey
from app.models.wr import PlanVersion
from app.schemas.wr import PlanCurrentRead, PlanInitialRequest, PlanItem, PlanShockRequest, PlanVersionRead
from app.services.events.emitter import build_event
from app.services.params import get_parameter

MODIFIABLE_FIELDS = frozenset({"title_fr", "params"})
PARIS = ZoneInfo("Europe/Paris")
DRY_RUN = "dry_run"


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


class PlanShockReasonError(ValueError):
    pass


def plan_enabled(db: Session) -> bool:
    return bool(get_parameter(db, "wr.plan_enabled", default=False))


def shock_enabled(db: Session) -> bool:
    return bool(get_parameter(db, "wr.plan_shock_enabled", default=False))


def shock_taxonomy(db: Session) -> dict[str, str]:
    return {entry["code"]: entry["label_fr"] for entry in get_parameter(db, "wr.shock_taxonomy", default=[]) or []}


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
    fingerprint = _fingerprint("wr.plan.initial", request.model_dump(mode="json"))
    replay = _replay(db, current_user, idempotency_key, request_path, fingerprint)
    if replay is not None:
        return replay

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
    return _remember(db, current_user, row, idempotency_key, request_path, fingerprint)


def request_shock(
    db: Session,
    *,
    current_user: User,
    request: PlanShockRequest,
    idempotency_key: str,
    request_path: str,
    now: datetime | None = None,
) -> PlanVersionRead:
    """Choc exogène déclaré par l'utilisateur → régénération complète PROPOSÉE (jamais activée ici)."""
    fingerprint = _fingerprint("wr.plan.shock", request.model_dump(mode="json"))
    replay = _replay(db, current_user, idempotency_key, request_path, fingerprint)
    if replay is not None:
        return replay

    taxonomy = shock_taxonomy(db)
    if request.reason_code not in taxonomy:
        raise PlanShockReasonError(f"Unknown shock reason '{request.reason_code}' (wr.shock_taxonomy).")
    if get_settings().real_ai_enabled:
        raise PlanStateError("Real shock regeneration (wr.plan_regen) is not coded yet: card V24.",
                             "PLAN_REGEN_NOT_CODED")
    active = _active(db, current_user)
    if active is None:
        raise PlanStateError("No active plan to regenerate.", "PLAN_NOT_ACTIVE")
    pending = _pending_regeneration(db, current_user)
    if pending is not None:
        raise PlanStateError(f"A regenerated plan is already waiting for validation ({pending}).",
                             "PLAN_REGEN_PENDING")

    now = now or datetime.now(UTC)
    shock = build_event(
        db, user_id=current_user.id, event_type="planning.plan.shock_requested",
        payload={"reason_code": request.reason_code, "active_plan_version_id": str(active.id)},
        idempotency_key=f"planning.plan.shock_requested.{idempotency_key}", source_app=SourceApp.imperium,
        privacy_level=PrivacyLevel.medium, occurred_at=now,
    )
    db.add(shock)
    db.flush()
    row = _propose_regeneration(
        db, current_user, origin="shock_regen", origin_ref=shock.id, now=now, extra={"reason_code": request.reason_code},
        causation_id=shock.event_id,
        rationale_fr=f"[essai] Régénération choc ({taxonomy[request.reason_code]}) : copie du plan courant, "
                     "aucun modèle appelé.",
    )
    return _remember(db, current_user, row, idempotency_key, request_path, fingerprint)


def monthly_regen_job(ctx, window) -> None:
    """Job `wr.monthly_regen` (semé désactivé) : régénération complète PROPOSÉE, jamais activée seule."""
    from app.services.wr.metrics import _job_user

    now = window.to_ts or datetime.now(UTC)
    ctx.cursor_ts = now
    ctx.items_in = ctx.items_out = 0
    user = _job_user(ctx.db)
    skip = None
    if user is None:
        skip = "no_user"
    elif not plan_enabled(ctx.db):
        skip = "plan_disabled"
    if skip is None:
        if get_settings().real_ai_enabled:
            raise PlanStateError("Real monthly regeneration (wr.plan_regen) is not coded yet: card V24.",
                                 "PLAN_REGEN_NOT_CODED")
        skip = _monthly_skip(ctx.db, user, now)
    if skip is not None:
        ctx.detail = {"skip": skip}
        ctx.db.rollback()
        return
    ctx.items_in = 1
    row = _propose_regeneration(
        ctx.db, user, origin="monthly_regen", origin_ref=None, now=now, extra={},
        rationale_fr="[essai] Régénération mensuelle : copie du plan courant, aucun modèle appelé.",
    )
    ctx.db.commit()
    ctx.items_out = 1
    ctx.detail = {"plan_version_id": str(row.id), "dry_run": True}


def _monthly_skip(db: Session, user: User, now: datetime) -> str | None:
    if _active(db, user) is None:
        return "no_active_plan"
    if _pending_regeneration(db, user) is not None:
        return "regeneration_pending"
    local = now.astimezone(PARIS)
    month_start = datetime(local.year, local.month, 1, tzinfo=PARIS)
    already = db.scalar(select(PlanVersion.id).where(
        PlanVersion.user_id == user.id, PlanVersion.origin == "monthly_regen", PlanVersion.created_at >= month_start))
    return "already_this_month" if already is not None else None


def _pending_regeneration(db: Session, current_user: User) -> UUID | None:
    return db.scalar(select(PlanVersion.id).where(
        PlanVersion.user_id == current_user.id, PlanVersion.status == "proposed",
        PlanVersion.origin.in_(("shock_regen", "monthly_regen"))))


def _propose_regeneration(db: Session, current_user: User, *, origin: str, origin_ref: UUID | None, now: datetime,
                          extra: dict, rationale_fr: str, causation_id: str | None = None) -> PlanVersion:
    """Essai à blanc : copie du plan courant (deltas appliqués) recalée sur aujourd'hui, statut proposed."""
    current = current_plan(db, current_user=current_user)
    start = now.astimezone(PARIS).date()
    row = PlanVersion(
        user_id=current_user.id, horizon_start=start,
        horizon_end=start + timedelta(days=(current.horizon_end - current.horizon_start).days),
        plan=current.plan, origin=origin, origin_ref=origin_ref, model_used=DRY_RUN, rationale_fr=rationale_fr,
        status="proposed", created_at=now,
    )
    db.add(row)
    db.flush()
    _emit(db, current_user, "planning.plan.regenerated", row, {**extra, "dry_run": True}, now,
          causation_id=causation_id)
    return row


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


def _fingerprint(namespace: str, body: dict) -> str:
    return hashlib.sha256(json.dumps({"ns": namespace, **body}, sort_keys=True).encode()).hexdigest()


def _replay(db: Session, current_user: User, idempotency_key: str, request_path: str,
            fingerprint: str) -> PlanVersionRead | None:
    previous = db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == current_user.id, IdempotencyKey.idempotency_key == idempotency_key
        )
    )
    if previous is None:
        return None
    if previous.request_path != request_path or previous.request_hash != fingerprint or previous.response_body is None:
        raise PlanStateError("Idempotency key already used with a different request.", "IDEMPOTENCY_CONFLICT")
    return PlanVersionRead.model_validate(previous.response_body)


def _remember(db: Session, current_user: User, row: PlanVersion, idempotency_key: str, request_path: str,
              fingerprint: str) -> PlanVersionRead:
    read = PlanVersionRead.model_validate(row)
    db.add(IdempotencyKey(
        user_id=current_user.id, idempotency_key=idempotency_key, request_method="POST", request_path=request_path,
        request_hash=fingerprint, status=IdempotencyStatus.completed, response_status_code=201,
        response_body=read.model_dump(mode="json"),
    ))
    db.commit()
    return read


def _active(db: Session, current_user: User) -> PlanVersion | None:
    return db.scalar(select(PlanVersion).where(PlanVersion.user_id == current_user.id,
                                               PlanVersion.status == "active").with_for_update())


def _owned(db: Session, current_user: User, version_id: UUID) -> PlanVersion:
    row = db.get(PlanVersion, version_id, with_for_update=True)
    if row is None or row.user_id != current_user.id:
        raise PlanVersionNotFoundError("Plan version not found.")
    return row


def _emit(db: Session, current_user: User, event_type: str, row: PlanVersion, extra: dict, now: datetime,
          causation_id: str | None = None) -> None:
    db.add(build_event(
        db, user_id=current_user.id, event_type=event_type,
        payload={"plan_version_id": str(row.id), "origin": row.origin,
                 "origin_ref": str(row.origin_ref) if row.origin_ref else None,
                 "horizon_start": row.horizon_start.isoformat(), "horizon_end": row.horizon_end.isoformat(),
                 "items": len(row.plan.get("items", [])), **extra},
        idempotency_key=f"{event_type}.{row.id}", source_app=SourceApp.imperium,
        privacy_level=PrivacyLevel.medium, causation_id=causation_id, occurred_at=now,
    ))
    db.flush()
