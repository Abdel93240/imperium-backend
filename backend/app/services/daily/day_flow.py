"""La journée vue par l'utilisateur, au-dessus de la sélection Niveau 1 (spec Daily §1.7 ; doc 43 §3.2-§3.4).

- Démarrer la mission proposée (ou choisie) : elle passe active et reçoit ses heures prévues (maintenant,
  maintenant + durée estimée), qui donnent « Temps restant » sur le Dashboard.
- Programme du jour : ce qui est fait (ou raté) aujourd'hui, la mission en cours, puis la proposition
  suivante ; jamais la file de candidates (décision UX : la file reste invisible).
- Replanifier (décision utilisateur 2026-10-21 : la journée est menée par le moteur de sélection, pas par un
  plan horaire) : une raison claire, puis selon la raison
    * imprévu (`new_event`) : la sélection repart de la fin de l'imprévu ;
    * mauvaise estimation : la mission en cours est prolongée ;
    * fatigue : les missions courtes (`daily.fatigue_max_minutes`) passent d'abord ;
    * autre priorité : la mission choisie par l'utilisateur devient la proposition ;
    * autre : nouvelle proposition.
  Chaque replanification est journalisée (`planning_replan_events`, statut `accepted`) et respecte le délai
  minimum entre deux replanifications (réglage). Rien ne démarre : l'utilisateur démarre la proposition.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.imperium import ImperiumMission, PlanningReplanEvent
from app.schemas.daily import DayReplanRead, DayReplanRequest, ProgrammeItemRead, ProgrammeRead
from app.services.daily import selection
from app.services.events.emitter import build_event
from app.services.imperium import missions
from app.services.imperium.planning_days import get_current_planning_day
from app.services.imperium.replan import _eligible_at
from app.services.params import get_parameter

PARIS = selection.PARIS
ENDED_STATES = {"completed": "done", "failed": "failed", "abandoned": "failed"}


class DayFlowError(ValueError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def start_mission(db: Session, *, current_user: User, mission_id: UUID, idempotency_key: str,
                  now: datetime | None = None) -> ImperiumMission:
    """Démarre une mission en attente (la proposée ou une autre) ; heures prévues = maintenant + durée."""
    now = now or datetime.now(UTC)
    try:
        missions.promote_backlog_mission(db, current_user=current_user, mission_id=mission_id,
                                         idempotency_key=idempotency_key, request_method="POST",
                                         request_path=f"/api/daily/start/{mission_id}")
    except missions.MissionNotFoundError as exc:
        raise DayFlowError(str(exc), "MISSION_NOT_FOUND") from exc
    except (missions.ActiveMissionExistsError, missions.MissionStateConflictError,
            missions.IdempotencyConflictError) as exc:
        raise DayFlowError(str(exc), "MISSION_STATE") from exc
    mission = db.get(ImperiumMission, mission_id)
    if mission.status == "active" and (mission.planned_end_at is None or mission.planned_end_at <= now):
        duration = mission.estimated_minutes or int(get_parameter(db, "daily.default_mission_duration", default=30))
        mission.planned_start_at, mission.planned_end_at = now, now + timedelta(minutes=duration)
    db.commit()
    return mission


def programme(db: Session, *, current_user: User, now: datetime | None = None) -> ProgrammeRead:
    now = now or datetime.now(UTC)
    start_of_day = datetime.combine(now.astimezone(PARIS).date(), datetime.min.time(), tzinfo=PARIS)
    ended = db.scalars(select(ImperiumMission).where(
        ImperiumMission.user_id == current_user.id, ImperiumMission.status.in_(tuple(ENDED_STATES)),
        ImperiumMission.ended_at >= start_of_day, ImperiumMission.annex_of_mission_id.is_(None))
        .order_by(ImperiumMission.ended_at))
    items = [ProgrammeItemRead(mission_id=m.id, title=m.title, state=ENDED_STATES[m.status], at=m.ended_at,
                               estimated_minutes=m.estimated_minutes) for m in ended]
    active = db.scalar(select(ImperiumMission).where(ImperiumMission.user_id == current_user.id,
                                                     ImperiumMission.status == "active"))
    if active is not None:
        items.append(ProgrammeItemRead(mission_id=active.id, title=active.title, state="active",
                                       at=active.planned_start_at or active.started_at,
                                       estimated_minutes=active.estimated_minutes))
    last = selection.current(db, current_user=current_user, now=now).last_selection
    outcome = None
    if active is None and last is not None:
        outcome = last.outcome
        proposed = last.next_mission
        if proposed is not None and db.scalar(select(ImperiumMission.status).where(
                ImperiumMission.id == proposed.id)) == "backlog":
            items.append(ProgrammeItemRead(mission_id=proposed.id, title=proposed.title, state="next", at=None,
                                           estimated_minutes=proposed.estimated_minutes))
    return ProgrammeRead(items=items, outcome=outcome)


def replan(db: Session, *, current_user: User, payload: DayReplanRequest, idempotency_key: str,
           now: datetime | None = None) -> DayReplanRead:
    now = now or datetime.now(UTC)
    existing = db.scalar(select(PlanningReplanEvent).where(PlanningReplanEvent.user_id == current_user.id,
                                                           PlanningReplanEvent.idempotency_key == idempotency_key))
    if existing is not None:
        return DayReplanRead(rationale=existing.rationale or "", selection=_last(db, current_user, now),
                             eligible_at=_eligible_at(db, current_user=current_user))
    day = get_current_planning_day(db, current_user=current_user)
    if day is None or day.finished_at is not None:
        raise DayFlowError("Start the day before replanning it.", "DAY_NOT_STARTED")
    eligible_at = _eligible_at(db, current_user=current_user)
    if eligible_at is not None and now < eligible_at:
        raise DayFlowError(f"Replanification disponible à partir de {eligible_at.isoformat()}.", "REPLAN_COOLDOWN")
    active = db.scalar(select(ImperiumMission).where(ImperiumMission.user_id == current_user.id,
                                                     ImperiumMission.status == "active"))
    category = payload.reason_category
    row = None
    if category == "wrong_estimation":
        if active is None:
            raise DayFlowError("No mission in progress to extend.", "NO_ACTIVE_MISSION")
        base = active.planned_end_at if active.planned_end_at and active.planned_end_at > now else now
        active.planned_end_at = base + timedelta(minutes=payload.extend_minutes)
        rationale = (f"J'ai prolongé « {active.title} » de {payload.extend_minutes} min : fin prévue à "
                     f"{active.planned_end_at.astimezone(PARIS):%H:%M}.")
    else:
        if active is not None:
            raise DayFlowError("A mission is in progress: finish it or mark it not done before changing what "
                               "comes next.", "MISSION_ACTIVE")
        at, max_duration, forced = now, None, None
        if category == "new_event":
            at = payload.busy_until.astimezone(UTC)
            if at <= now or at.astimezone(PARIS).date() != now.astimezone(PARIS).date():
                raise DayFlowError("busy_until must be later today.", "BAD_BUSY_UNTIL")
        elif category == "fatigue":
            max_duration = int(get_parameter(db, "daily.fatigue_max_minutes", default=30))
        elif category == "priority_shift":
            forced = db.get(ImperiumMission, payload.mission_id)
            if forced is None or forced.user_id != current_user.id or forced.status != "backlog":
                raise DayFlowError("Choose a mission that is still waiting.", "MISSION_NOT_AVAILABLE")
        row = selection.select_next(db, current_user=current_user, trigger="replan", now=at,
                                    max_duration=max_duration, forced_mission=forced)
        chosen = db.get(ImperiumMission, row.chosen_mission_id) if row.chosen_mission_id else None
        rationale = _rationale(category, chosen, row.outcome, at, max_duration)
    event = PlanningReplanEvent(
        id=uuid4(), user_id=current_user.id, planning_day_id=day.id, trigger="manual", reason_category=category,
        other_reason=(payload.other_reason or "").strip() or None, reason_detail=payload.reason_detail,
        status="accepted", rationale=rationale, requested_at=now, resolved_at=now, idempotency_key=idempotency_key,
        proposal=[{"selection_log_id": str(row.id)}] if row is not None else [],
    )
    db.add(event)
    db.add(build_event(db, user_id=current_user.id, event_type="planning.replan.requested",
                       payload={"replan_event_id": str(event.id), "trigger": "manual", "hook_type": None,
                                "reason_category": category, "engine": "daily_selection"},
                       idempotency_key=f"replan-request:{event.id}"))
    db.commit()
    return DayReplanRead(rationale=rationale, selection=selection.to_read(db, row) if row is not None else None,
                         eligible_at=_eligible_at(db, current_user=current_user))


def _last(db: Session, current_user: User, now: datetime):
    return selection.current(db, current_user=current_user, now=now).last_selection


def _rationale(category: str, chosen: ImperiumMission | None, outcome: str, at: datetime,
               max_duration: int | None) -> str:
    if chosen is None:
        return ("Je n'ai rien d'autre à te proposer aujourd'hui : choisis une mission ou ajoute-en une."
                if outcome == "day_done" else
                "Je n'arrive pas à trancher entre tes obligations du jour : choisis la mission à faire maintenant.")
    if category == "new_event":
        return f"Après ton imprévu (fin vers {at.astimezone(PARIS):%H:%M}), je te propose « {chosen.title} »."
    if category == "fatigue":
        if (chosen.estimated_minutes or 0) <= (max_duration or 0):
            return f"Fais une pause, puis « {chosen.title} », une mission courte."
        return f"Fais une pause, puis « {chosen.title} ». Il ne reste rien de plus court aujourd'hui."
    if category == "priority_shift":
        return f"C'est noté : « {chosen.title} » passe maintenant."
    return f"Je te propose maintenant « {chosen.title} »."
