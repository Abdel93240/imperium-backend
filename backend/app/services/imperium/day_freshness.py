"""Vérification de fraîcheur déterministe au démarrage de journée.

Contrat canonique : gap_analysis_v1/DECISION_demarrage_journee.md (étape 3), doc 52 §9.1,
doc 28. Après le clic « Démarrer la journée », le backend vérifie sans IA :
- le calendrier modifié depuis la génération du plan (ou, sans plan, depuis la clôture
  de la journée précédente), pour les événements qui touchent la journée opérationnelle
  (36 h au plus à partir du démarrage) ;
- les missions non faites de la journée opérationnelle précédente : ratées pendant cette
  journée, mises en standby ou remises au backlog à sa clôture ;
- une mission restée active d'avant le démarrage (à ne pas afficher comme mission du jour) ;
- les contraintes récentes : ghusl requis, jeûne en cours, demande de replan ouverte,
  missions en standby qui attendent une décision.

Lecture seule : rien n'est écrit, aucun appel de modèle. L'arbitrage local en cas de
conflit (local_executor via le scoring) n'est pas raccordé ici ; la réponse dit seulement
si la sélection est fraîche (« fresh ») ou à revoir (« review »).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.event import Event
from app.models.imperium import (
    ImperiumCalendarEvent,
    ImperiumDailyPlan,
    ImperiumMission,
    PlanningDay,
    PlanningReplanEvent,
)
from app.schemas.day_freshness import (
    DayFreshnessResponse,
    FreshnessCalendarChange,
    FreshnessConstraint,
    FreshnessMission,
)
from app.services.imperium.planning_days import get_current_planning_day
from app.services.imperium.replan import OPEN_STATUSES
from app.services.path import fasting, ghusl

OPERATIONAL_DAY_HORIZON = timedelta(hours=36)
FRESH_MESSAGE = "Programme à jour."
REVIEW_MESSAGE = "Des changements touchent ta journée : vérifie le programme."


class DayNotStartedError(ValueError):
    pass


def check_freshness(db: Session, *, current_user: User, now: datetime | None = None) -> DayFreshnessResponse:
    day = get_current_planning_day(db, current_user=current_user)
    if day is None:
        raise DayNotStartedError("Journée non démarrée.")
    now = now or datetime.now(UTC)
    plan = db.scalar(
        select(ImperiumDailyPlan).where(
            ImperiumDailyPlan.user_id == current_user.id,
            ImperiumDailyPlan.local_date == day.start_local_date,
            ImperiumDailyPlan.plan_status != "cancelled",
        )
    )
    prior = db.scalar(
        select(PlanningDay)
        .where(
            PlanningDay.user_id == current_user.id,
            PlanningDay.finished_at.is_not(None),
            PlanningDay.started_at < day.started_at,
        )
        .order_by(PlanningDay.started_at.desc())
        .limit(1)
    )
    reference = plan.updated_at if plan is not None else (prior.finished_at if prior is not None else None)
    calendar_changes = _calendar_changes(db, current_user, day, reference)
    stale = db.scalar(
        select(ImperiumMission).where(
            ImperiumMission.user_id == current_user.id,
            ImperiumMission.status == "active",
            ImperiumMission.started_at < day.started_at,
        )
    )
    failed, standby, returned = _prior_day_missions(db, current_user, prior)
    constraints = _constraints(db, current_user, now)

    reasons = [
        code
        for code, present in (
            ("calendar_changed", calendar_changes),
            ("stale_active_mission", stale is not None),
            ("prior_day_unfinished", failed or standby or returned),
            ("constraints", constraints),
        )
        if present
    ]
    return DayFreshnessResponse(
        planning_day_id=day.id,
        checked_at=now,
        status="review" if reasons else "fresh",
        reasons=reasons,
        plan_id=plan.id if plan is not None else None,
        plan_generated_at=plan.updated_at if plan is not None else None,
        calendar_changes=calendar_changes,
        stale_active_mission=_mission(stale) if stale is not None else None,
        prior_day_failed=failed,
        prior_day_standby=standby,
        prior_day_returned_to_backlog=returned,
        constraints=constraints,
        message=REVIEW_MESSAGE if reasons else FRESH_MESSAGE,
    )


def _calendar_changes(
    db: Session, user: User, day: PlanningDay, reference: datetime | None
) -> list[FreshnessCalendarChange]:
    if reference is None:
        return []
    horizon = day.started_at + OPERATIONAL_DAY_HORIZON
    rows = db.scalars(
        select(ImperiumCalendarEvent)
        .where(
            ImperiumCalendarEvent.user_id == user.id,
            ImperiumCalendarEvent.updated_at > reference,
            ImperiumCalendarEvent.starts_at < horizon,
            ImperiumCalendarEvent.blocks_time.is_(True),
        )
        .order_by(ImperiumCalendarEvent.starts_at, ImperiumCalendarEvent.id)
    )
    changes = []
    for row in rows:
        if (row.ends_at or row.starts_at) < day.started_at:
            continue
        if row.deleted_at is not None:
            if row.created_at > reference:
                continue  # créé puis supprimé après la génération : rien n'a changé pour le plan
            change = "deleted"
        else:
            change = "created" if row.created_at > reference else "updated"
        changes.append(FreshnessCalendarChange(id=row.id, title=row.title, starts_at=row.starts_at, change=change))
    return changes


def _prior_day_missions(
    db: Session, user: User, prior: PlanningDay | None
) -> tuple[list[FreshnessMission], list[FreshnessMission], int]:
    if prior is None:
        return [], [], 0
    failed = db.scalars(
        select(ImperiumMission)
        .where(
            ImperiumMission.user_id == user.id,
            ImperiumMission.status == "failed",
            ImperiumMission.ended_at >= prior.started_at,
            ImperiumMission.ended_at <= prior.finished_at,
        )
        .order_by(ImperiumMission.ended_at, ImperiumMission.id)
    )
    closing = db.scalar(
        select(Event).where(
            Event.user_id == user.id,
            Event.event_type == "planning.day.finished",
            Event.payload["planning_day_id"].astext == str(prior.id),
        )
    )
    payload = closing.payload if closing is not None else {}
    standby_ids = payload.get("standby_mission_ids") or []
    standby = (
        db.scalars(
            select(ImperiumMission)
            .where(ImperiumMission.user_id == user.id, ImperiumMission.status == "standby",
                   ImperiumMission.id.in_(standby_ids))
            .order_by(ImperiumMission.id)
        )
        if standby_ids
        else []
    )
    returned = int(payload.get("missions_returned_to_backlog") or 0)
    return [_mission(row) for row in failed], [_mission(row) for row in standby], returned


def _constraints(db: Session, user: User, now: datetime) -> list[FreshnessConstraint]:
    constraints = []
    if ghusl.current(db, current_user=user).ghusl_required:
        constraints.append(FreshnessConstraint(code="ghusl_required", message="Ghusl requis avant la prochaine prière."))
    fast = fasting.window_fast(db, user, now)
    if fast is not None and fast.status == "active":
        constraints.append(FreshnessConstraint(code="fasting_active", message="Jeûne en cours."))
    replan_open = db.scalar(
        select(PlanningReplanEvent.id).where(
            PlanningReplanEvent.user_id == user.id, PlanningReplanEvent.status.in_(OPEN_STATUSES)
        ).limit(1)
    )
    if replan_open is not None:
        constraints.append(FreshnessConstraint(code="replan_open", message="Une demande de replan est en cours."))
    standby_waiting = db.scalar(
        select(ImperiumMission.id).where(ImperiumMission.user_id == user.id, ImperiumMission.status == "standby").limit(1)
    )
    if standby_waiting is not None:
        constraints.append(
            FreshnessConstraint(code="standby_decision", message="Des missions en standby attendent ta décision.")
        )
    return constraints


def _mission(row: ImperiumMission) -> FreshnessMission:
    return FreshnessMission(id=row.id, title=row.title, status=row.status)
