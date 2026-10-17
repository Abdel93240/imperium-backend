"""Replanification de la journée (doc 43 §3.2–§3.4, doc 59 §12.6, décisions 2026-10-16/17).

Circuit : demande (catégorie + détails, délai serveur) → tâche IA imperium.rolling_replan
→ proposition déposée par le runner → corrections via le chatbot (sans nouveau délai)
→ accepter (applique au plan du jour, version +1) ou annuler (plan inchangé).
Le backend ne génère aucune proposition lui-même : il orchestre et valide.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.ai import AITask
from app.models.auth import User
from app.models.imperium import ImperiumDailyPlan, PlanningReplanEvent
from app.schemas.imperium import (
    ReplanProposalAttachRequest,
    ReplanRead,
    ReplanRequestCreate,
    ReplanReviseRequest,
    ReplanStateResponse,
)
from app.services.events.emitter import build_event
from app.services.imperium.daily_plans import get_daily_plan_for_date
from app.services.imperium.planning_days import get_current_planning_day
from app.services.imperium.settings import replan_debounce_minutes

# doc 43 §3.3 / §15 : une replanification au plus toutes les N min (réglage, 5 par défaut),
# manuelles comprises.
REPLAN_DEBOUNCE_MINUTES = 5  # valeur par défaut, voir services/imperium/settings.py
# doc 43 §3.3 : déclencheurs toujours immédiats.
DEBOUNCE_EXEMPT_HOOKS = frozenset({"ghusl_required", "fasting_break"})
OPEN_STATUSES = ("requested", "proposed", "revising")
REPLAN_TASK_TYPE = "imperium.rolling_replan"


class ReplanCooldownError(ValueError):
    def __init__(self, eligible_at: datetime) -> None:
        super().__init__(f"Replanification disponible à partir de {eligible_at.isoformat()}.")
        self.eligible_at = eligible_at


class ReplanStateConflictError(ValueError):
    pass


class ReplanNotFoundError(ValueError):
    pass


class ReplanIdempotencyConflictError(ValueError):
    pass


def get_replan_state(db: Session, *, current_user: User, now: datetime | None = None) -> ReplanStateResponse:
    now = now or datetime.now(UTC)
    eligible_at = _eligible_at(db, current_user=current_user)
    open_request = _open_request(db, current_user=current_user)
    return ReplanStateResponse(
        eligible_at=eligible_at,
        can_request=open_request is None and (eligible_at is None or now >= eligible_at),
        debounce_minutes=replan_debounce_minutes(db, current_user=current_user),
        open_request=ReplanRead.model_validate(open_request) if open_request else None,
    )


def request_replan(
    db: Session,
    *,
    current_user: User,
    payload: ReplanRequestCreate,
    idempotency_key: str,
    request_method: str,
    request_path: str,
    now: datetime | None = None,
) -> tuple[ReplanRead, bool]:
    """Demande manuelle (bouton « Replanifier »)."""
    existing = db.scalar(
        select(PlanningReplanEvent).where(
            PlanningReplanEvent.user_id == current_user.id,
            PlanningReplanEvent.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        same = (
            existing.trigger == "manual"
            and existing.reason_category == payload.reason_category.value
            and existing.reason_detail == payload.reason_detail
            and existing.other_reason == payload.other_reason
        )
        if not same:
            raise ReplanIdempotencyConflictError("Idempotency key already used with different payload.")
        return ReplanRead.model_validate(existing), True

    row = _create_request(
        db,
        current_user=current_user,
        trigger="manual",
        hook_type=None,
        reason_category=payload.reason_category.value,
        other_reason=payload.other_reason,
        reason_detail=payload.reason_detail,
        idempotency_key=idempotency_key,
        now=now or datetime.now(UTC),
        bypass_debounce=False,
    )
    return ReplanRead.model_validate(row), False


def request_hook_replan(
    db: Session,
    *,
    current_user: User,
    hook_type: str,
    now: datetime | None = None,
) -> ReplanRead:
    """Replanification déclenchée par un hook (doc 43 §3) ; seules les exceptions passent le délai."""
    now = now or datetime.now(UTC)
    row = _create_request(
        db,
        current_user=current_user,
        trigger="hook",
        hook_type=hook_type,
        reason_category=None,
        other_reason=None,
        reason_detail=None,
        idempotency_key=f"hook:{hook_type}:{now.isoformat()}",
        now=now,
        bypass_debounce=hook_type in DEBOUNCE_EXEMPT_HOOKS,
    )
    return ReplanRead.model_validate(row)


def attach_replan_proposal(
    db: Session,
    *,
    request_id: UUID,
    payload: ReplanProposalAttachRequest,
    idempotency_key: str,
) -> ReplanRead:
    """Le runner IA dépose la proposition (route interne)."""
    row = db.get(PlanningReplanEvent, request_id)
    if row is None:
        raise ReplanNotFoundError("Replan request not found.")
    if row.status == "proposed" and row.proposal == payload.blocks:
        return ReplanRead.model_validate(row)  # rejeu du même dépôt
    if row.status not in ("requested", "revising"):
        raise ReplanStateConflictError("Replan request is not waiting for a proposal.")
    if payload.ai_task_id is not None and payload.ai_task_id != row.ai_task_id:
        raise ReplanStateConflictError("Proposal does not match the pending AI task.")
    row.proposal = payload.blocks
    row.rationale = payload.rationale
    row.proposal_version += 1
    row.status = "proposed"
    db.commit()
    db.refresh(row)
    return ReplanRead.model_validate(row)


def revise_replan(
    db: Session,
    *,
    current_user: User,
    replan_id: UUID,
    payload: ReplanReviseRequest,
    idempotency_key: str,
    now: datetime | None = None,
) -> ReplanRead:
    """Correction demandée dans le chatbot de l'écran de résultat : pas soumise au délai."""
    row = _get_user_request(db, current_user=current_user, replan_id=replan_id)
    existing_task = db.scalar(
        select(AITask).where(AITask.user_id == current_user.id, AITask.idempotency_key == idempotency_key)
    )
    if existing_task is not None and existing_task.id == row.ai_task_id:
        return ReplanRead.model_validate(row)
    if row.status != "proposed":
        raise ReplanStateConflictError("Only a displayed proposal can be revised.")
    task = AITask(
        user_id=current_user.id,
        task_type=REPLAN_TASK_TYPE,
        status="queued",
        source_module="imperium",
        input_payload={
            **_task_input(row),
            "correction": payload.message,
            "current_proposal": row.proposal,
            "proposal_version": row.proposal_version,
        },
        privacy_level="medium",
        idempotency_key=idempotency_key,
    )
    db.add(task)
    db.flush()
    row.ai_task_id = task.id
    row.status = "revising"
    # Réveille le job runner imperium.rolling_replan (doc 43 §3.2).
    db.add(
        build_event(
            db,
            user_id=current_user.id,
            event_type="planning.replan.revision_requested",
            payload={"replan_event_id": str(row.id), "ai_task_id": str(task.id), "proposal_version": row.proposal_version},
            idempotency_key=f"replan-revise:{task.id}",
        )
    )
    db.commit()
    db.refresh(row)
    return ReplanRead.model_validate(row)


def accept_replan(db: Session, *, current_user: User, replan_id: UUID, now: datetime | None = None) -> ReplanRead:
    """Applique la proposition au plan du jour ; seule l'acceptation modifie le plan."""
    now = now or datetime.now(UTC)
    row = _get_user_request(db, current_user=current_user, replan_id=replan_id)
    if row.status == "accepted":
        return ReplanRead.model_validate(row)
    if row.status != "proposed" or row.proposal is None:
        raise ReplanStateConflictError("No proposal to accept.")
    plan = db.get(ImperiumDailyPlan, row.daily_plan_id) if row.daily_plan_id else None
    if plan is None or plan.user_id != current_user.id:
        raise ReplanStateConflictError("No daily plan to replan.")

    version = int((plan.generated_from or {}).get("replan_version", 0)) + 1
    plan.plan_blocks = [
        {key: value for key, value in block.items() if key != "change"}
        for block in row.proposal
        if block.get("change") != "removed"
    ]
    plan.generated_from = {**(plan.generated_from or {}), "replan_version": version, "last_replan_event_id": str(row.id)}
    db.add(
        build_event(
            db,
            user_id=current_user.id,
            event_type="planning.daily_plan.replanned",
            payload={
                "plan_id": str(plan.id),
                "version": version,
                "reason": row.reason_category or row.hook_type,
                "trigger": row.trigger,
                "replan_event_id": str(row.id),
                "proposal_version": row.proposal_version,
            },
            idempotency_key=f"replan-accept:{row.id}",
        )
    )
    row.status = "accepted"
    row.resolved_at = now
    db.commit()
    db.refresh(row)
    return ReplanRead.model_validate(row)


def cancel_replan(db: Session, *, current_user: User, replan_id: UUID, now: datetime | None = None) -> ReplanRead:
    """Annuler conserve le plan précédent (doc 59 §12.6)."""
    row = _get_user_request(db, current_user=current_user, replan_id=replan_id)
    if row.status == "cancelled":
        return ReplanRead.model_validate(row)
    if row.status not in OPEN_STATUSES:
        raise ReplanStateConflictError("Replan request is already closed.")
    row.status = "cancelled"
    row.resolved_at = now or datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return ReplanRead.model_validate(row)


# ---------- internes ----------

def _create_request(
    db: Session,
    *,
    current_user: User,
    trigger: str,
    hook_type: str | None,
    reason_category: str | None,
    other_reason: str | None,
    reason_detail: str | None,
    idempotency_key: str,
    now: datetime,
    bypass_debounce: bool,
) -> PlanningReplanEvent:
    day = get_current_planning_day(db, current_user=current_user)
    if day is None:
        raise ReplanStateConflictError("No operational day is open.")
    if _open_request(db, current_user=current_user) is not None:
        raise ReplanStateConflictError("A replan request is already in progress.")
    if not bypass_debounce:
        eligible_at = _eligible_at(db, current_user=current_user)
        if eligible_at is not None and now < eligible_at:
            raise ReplanCooldownError(eligible_at)

    plan = get_daily_plan_for_date(db, current_user=current_user, local_date=day.start_local_date)
    row = PlanningReplanEvent(
        id=uuid4(),
        user_id=current_user.id,
        planning_day_id=day.id,
        daily_plan_id=plan.id if plan else None,
        trigger=trigger,
        hook_type=hook_type,
        reason_category=reason_category,
        other_reason=other_reason,
        reason_detail=reason_detail,
        status="requested",
        requested_at=now,
        idempotency_key=idempotency_key,
    )
    db.add(row)
    db.flush()
    task = AITask(
        user_id=current_user.id,
        task_type=REPLAN_TASK_TYPE,
        status="queued",
        source_module="imperium",
        input_payload={**_task_input(row), "current_plan_blocks": plan.plan_blocks if plan else []},
        privacy_level="medium",
        idempotency_key=f"replan:{row.id}",
    )
    db.add(task)
    db.flush()
    row.ai_task_id = task.id
    db.add(
        build_event(
            db,
            user_id=current_user.id,
            event_type="planning.replan.requested",
            payload={
                "replan_event_id": str(row.id),
                "trigger": trigger,
                "hook_type": hook_type,
                "reason_category": reason_category,
                "ai_task_id": str(task.id),
            },
            idempotency_key=f"replan-request:{row.id}",
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ReplanStateConflictError("A replan request is already in progress.") from exc
    db.refresh(row)
    return row


def _task_input(row: PlanningReplanEvent) -> dict:
    return {
        "replan_event_id": str(row.id),
        "trigger": row.trigger,
        "hook_type": row.hook_type,
        "reason_category": row.reason_category,
        "other_reason": row.other_reason,
        "reason_detail": row.reason_detail,
        "daily_plan_id": str(row.daily_plan_id) if row.daily_plan_id else None,
    }


def _eligible_at(db: Session, *, current_user: User) -> datetime | None:
    last = db.scalar(
        select(func.max(PlanningReplanEvent.requested_at)).where(
            PlanningReplanEvent.user_id == current_user.id,
            PlanningReplanEvent.status != "failed",
        )
    )
    return last + timedelta(minutes=replan_debounce_minutes(db, current_user=current_user)) if last else None


def _open_request(db: Session, *, current_user: User) -> PlanningReplanEvent | None:
    return db.scalar(
        select(PlanningReplanEvent).where(
            PlanningReplanEvent.user_id == current_user.id,
            PlanningReplanEvent.status.in_(OPEN_STATUSES),
        )
    )


def _get_user_request(db: Session, *, current_user: User, replan_id: UUID) -> PlanningReplanEvent:
    row = db.get(PlanningReplanEvent, replan_id)
    if row is None or row.user_id != current_user.id:
        raise ReplanNotFoundError("Replan request not found.")
    return row
