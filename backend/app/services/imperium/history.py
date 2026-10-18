"""Chronologie de l'historique Imperium (IMP.HISTORY.MAIN, doc 65 §7) — lecture seule.

Projection du registre d'événements (table events, en ajout seul) restreinte aux faits
Imperium : missions, journées opérationnelles, plans du jour, décisions (priorités, demandes
de replan) et projets ; plus bas, les blocs « Historique des journées » et « Finances » ; plus les Weekly Reviews approuvées (rapports finaux). Les autres
domaines (Vault, Pulse, Path, Vector) n'y entrent pas : leurs données sont plus sensibles et
ont leurs propres écrans.

Filtres de l'écran : all, missions, decisions (priorités, replans, projets), weekly, failed
(missions ratées). La recherche porte sur le titre. Les anciens noms d'événements sont lus
avec les nouveaux (expand_for_read). Au plus HISTORY_SCAN_LIMIT événements récents sont lus
par requête.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.event import Event
from app.models.imperium import ImperiumMission, ImperiumProject, ImperiumWeeklyReviewFinalReport, PlanningDay
from app.models.vault import ImperiumVaultTransaction
from app.schemas.history import (
    FinancePointRead,
    HistoryDayListResponse,
    HistoryDayRead,
    HistoryEventDetailResponse,
    HistoryEventListResponse,
    HistoryEventRead,
    HistoryFinancesResponse,
)
from app.services.events.nomenclature import canonical_event_type, expand_for_read

HISTORY_SCAN_LIMIT = 5000
WEEKLY_PREFIX = "weekly_report:"
WEEKLY_STATUSES = ("approved", "stored")

# type canonique → (type affiché, source, statut, titre par défaut)
EVENT_TYPES: dict[str, tuple[str, str, str, str]] = {
    "planning.mission.created": ("mission_created", "mission", "backlog", "Mission créée"),
    "planning.mission.started": ("mission_started", "mission", "active", "Mission démarrée"),
    "planning.mission.completed": ("mission_completed", "mission", "completed", "Mission faite"),
    "planning.mission.aborted": ("mission_failed", "mission", "failed", "Mission ratée"),
    "planning.mission.rescheduled": ("mission_rescheduled", "mission", "rescheduled", "Mission reprogrammée"),
    "planning.day.started": ("day_started", "day", "started", "Journée démarrée"),
    "planning.day.finished": ("day_finished", "day", "finished", "Journée terminée"),
    "planning.daily_plan.generated": ("plan_generated", "plan", "generated", "Plan du jour créé"),
    "planning.daily_plan.replanned": ("plan_replanned", "plan", "replanned", "Plan du jour modifié"),
    "decision.priorities.updated": ("priorities_updated", "decision", "updated", "Priorités modifiées"),
    "planning.replan.requested": ("replan_requested", "decision", "requested", "Replan demandé"),
    "planning.project.created": ("project_created", "project", "created", "Projet créé"),
    "planning.project.completed": ("project_completed", "project", "completed", "Projet accompli"),
    "planning.project.deleted": ("project_deleted", "project", "deleted", "Projet supprimé"),
    "planning.project.reordered": ("projects_reordered", "decision", "updated", "Projets réordonnés"),
}
CANCEL_REASONS = {"deleted_by_user": "Supprimée par l'utilisateur", "standby_cancelled": "Annulée depuis le standby"}
FILTER_SOURCES = {
    "missions": {"mission"},
    "decisions": {"decision", "project"},
    "weekly": {"weekly"},
}
LINKED_ROUTES = {
    "mission": "IMP.HISTORY.MAIN",
    "day": "IMP.PLAN.HISTORY",
    "plan": "IMP.PLAN.HISTORY",
    "decision": "IMP.SETTINGS.PRIORITIES",
    "project": "IMP.OPERATIONS.MAIN",
    "weekly": "IMP.WR.READ_ONLY",
}
DETAIL_KEYS = (
    "reason", "failure_reason", "failure_reason_code", "cancellation_reason", "previous_status", "decision",
    "deadline_at", "note", "outcome", "felt_energy", "trigger", "hook_type", "reason_category",
    "missions_returned_to_backlog", "local_date", "cancelled_missions",
)


class HistoryEventNotFoundError(ValueError):
    pass


def list_history_events(
    db: Session, *, current_user: User, filter_name: str = "all", query: str | None = None, limit: int = 30,
    offset: int = 0,
) -> HistoryEventListResponse:
    query = (query or "").strip() or None
    items = _items(db, current_user)
    if filter_name == "failed":
        items = [item for item in items if item.status == "failed"]
    elif filter_name in FILTER_SOURCES:
        items = [item for item in items if item.source in FILTER_SOURCES[filter_name]]
    if query is not None:
        needle = query.casefold()
        items = [item for item in items if needle in item.title.casefold()]
    page = items[offset : offset + limit]
    return HistoryEventListResponse(
        items=page, count=len(page), limit=limit, offset=offset, has_more=len(items) > offset + limit,
        filter=filter_name, query=query,
    )


def get_history_event(db: Session, *, current_user: User, event_id: str) -> HistoryEventDetailResponse:
    if event_id.startswith(WEEKLY_PREFIX):
        try:
            report_id = UUID(event_id.removeprefix(WEEKLY_PREFIX))
        except ValueError as exc:
            raise HistoryEventNotFoundError("Événement introuvable.") from exc
        report = db.scalar(
            select(ImperiumWeeklyReviewFinalReport).where(
                ImperiumWeeklyReviewFinalReport.id == report_id,
                ImperiumWeeklyReviewFinalReport.user_id == current_user.id,
                ImperiumWeeklyReviewFinalReport.status.in_(WEEKLY_STATUSES),
            )
        )
        if report is None:
            raise HistoryEventNotFoundError("Événement introuvable.")
        return HistoryEventDetailResponse(
            event=_weekly(report),
            details={"week_start": report.week_start.isoformat(), "week_end": report.week_end.isoformat(),
                     "session_id": str(report.session_id)},
        )
    row = db.scalar(
        select(Event).where(
            Event.user_id == current_user.id, Event.event_id == event_id,
            Event.event_type.in_(expand_for_read(list(EVENT_TYPES))),
        )
    )
    if row is None:
        raise HistoryEventNotFoundError("Événement introuvable.")
    item = _project([row], db, current_user)[0]
    payload = row.payload or {}
    return HistoryEventDetailResponse(event=item, details={key: payload[key] for key in DETAIL_KEYS if key in payload})


def _items(db: Session, user: User) -> list[HistoryEventRead]:
    rows = list(
        db.scalars(
            select(Event)
            .where(Event.user_id == user.id, Event.event_type.in_(expand_for_read(list(EVENT_TYPES))))
            .order_by(Event.occurred_at.desc(), Event.event_id.desc())
            .limit(HISTORY_SCAN_LIMIT)
        )
    )
    reports = db.scalars(
        select(ImperiumWeeklyReviewFinalReport).where(
            ImperiumWeeklyReviewFinalReport.user_id == user.id,
            ImperiumWeeklyReviewFinalReport.status.in_(WEEKLY_STATUSES),
        )
    )
    items = _project(rows, db, user) + [_weekly(report) for report in reports]
    items.sort(key=lambda item: (item.occurred_at, item.id), reverse=True)
    return items


def _project(rows: list[Event], db: Session, user: User) -> list[HistoryEventRead]:
    mission_ids = {_uuid((row.payload or {}).get("mission_id")) for row in rows} - {None}
    project_ids = {_uuid((row.payload or {}).get("project_id")) for row in rows} - {None}
    missions = (
        {m.id: m for m in db.scalars(select(ImperiumMission).where(
            ImperiumMission.user_id == user.id, ImperiumMission.id.in_(mission_ids)))}
        if mission_ids else {}
    )
    projects = (
        {p.id: p for p in db.scalars(select(ImperiumProject).where(
            ImperiumProject.user_id == user.id, ImperiumProject.id.in_(project_ids)))}
        if project_ids else {}
    )
    items = []
    for row in rows:
        canonical = canonical_event_type(row.event_type)
        kind, source, status, title = EVENT_TYPES[canonical]
        payload = row.payload or {}
        reason = None
        if canonical == "planning.mission.aborted":
            # Un échec porte toujours failure_reason ou failure_reason_code (FailMissionRequest) ;
            # tout autre abandon est une annulation : bouton Annulée, suppression, standby annulé.
            if row.event_type == "mission.failed" or "failure_reason" in payload or "failure_reason_code" in payload:
                reason = payload.get("failure_reason") or payload.get("failure_reason_code") or payload.get("reason")
            else:
                kind, status, title = "mission_cancelled", "cancelled", "Mission annulée"
                reason = (payload.get("cancellation_reason") or payload.get("note")
                          or CANCEL_REASONS.get(payload.get("reason")))
        mission = missions.get(_uuid(payload.get("mission_id")))
        project = projects.get(_uuid(payload.get("project_id")))
        if mission is not None:
            title = mission.title
        elif project is not None:
            title = project.title
        route = LINKED_ROUTES[source]
        if mission is not None and mission.status == "active":
            route = "IMP.MISSION.ACTIVE"
        items.append(
            HistoryEventRead(
                id=row.event_id, type=kind, title=title, status=status, occurred_at=row.occurred_at, source=source,
                reason=reason, linked_mission_id=mission.id if mission is not None else None, linked_route=route,
            )
        )
    return items


def _weekly(report: ImperiumWeeklyReviewFinalReport) -> HistoryEventRead:
    return HistoryEventRead(
        id=f"{WEEKLY_PREFIX}{report.id}", type="weekly_review", source="weekly", status=report.status,
        title=f"Weekly Review du {report.week_start:%d/%m/%Y}",
        occurred_at=report.approved_at or report.stored_at or report.created_at, linked_route=LINKED_ROUTES["weekly"],
    )


def _uuid(value) -> UUID | None:  # noqa: ANN001 - valeur de payload JSON
    try:
        return UUID(str(value)) if value else None
    except ValueError:
        return None


# ---------- Historique des journées et Finances (doc 65 §7.5) ----------

PERIOD_DAYS = {"week": 7, "month": 30, "3months": 90, "year": 365}


def list_history_days(db: Session, *, current_user: User, limit: int = 30, offset: int = 0,
                      now: datetime | None = None) -> HistoryDayListResponse:
    """Journées opérationnelles, de la plus récente à la plus ancienne, avec leurs missions.

    Une mission compte pour la journée où elle s'est terminée (faite, ratée, annulée) ;
    les missions annexes faites sont comptées à part (bonus, doc 53 §8).
    """
    now = now or datetime.now(UTC)
    rows = list(
        db.scalars(
            select(PlanningDay)
            .where(PlanningDay.user_id == current_user.id)
            .order_by(PlanningDay.started_at.desc(), PlanningDay.id)
            .offset(offset)
            .limit(limit + 1)
        )
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    missions = []
    if rows:
        start = min(row.started_at for row in rows)
        end = max(row.finished_at or now for row in rows)
        missions = list(
            db.scalars(
                select(ImperiumMission).where(
                    ImperiumMission.user_id == current_user.id,
                    ImperiumMission.status.in_(("completed", "failed", "cancelled")),
                    ImperiumMission.ended_at >= start,
                    ImperiumMission.ended_at <= end,
                )
            )
        )
    items = []
    for row in rows:
        end = row.finished_at or now
        inside = [m for m in missions if row.started_at <= m.ended_at <= end]
        principal = [m for m in inside if m.annex_of_mission_id is None]
        items.append(
            HistoryDayRead(
                planning_day_id=row.id, start_local_date=row.start_local_date, started_at=row.started_at,
                finished_at=row.finished_at, status="finished" if row.finished_at else "open",
                duration_minutes=int((end - row.started_at).total_seconds() // 60), felt_energy=row.felt_energy,
                missions_completed=sum(m.status == "completed" for m in principal),
                missions_failed=sum(m.status == "failed" for m in principal),
                missions_cancelled=sum(m.status == "cancelled" for m in principal),
                annexes_completed=sum(m.status == "completed" and m.annex_of_mission_id is not None for m in inside),
                day_review_id=row.day_review_id,
            )
        )
    return HistoryDayListResponse(items=items, count=len(items), limit=limit, offset=offset, has_more=has_more)


def history_finances(db: Session, *, current_user: User, period: str = "3months",
                     today: date | None = None) -> HistoryFinancesResponse:
    """Résultat net (gains − dépenses, EUR) par jour de Paris ; les écritures inverses s'annulent d'elles-mêmes.

    Périodes glissantes finissant aujourd'hui : 7, 30, 90 ou 365 jours ; « Tout » part de la
    première transaction, sans période précédente (écart = net depuis le début).
    """
    from app.services.path.fasting import paris_today
    from app.services.vault.wallet import wallet_state

    today = today or paris_today()
    daily = {
        day: int(net)
        for day, net in db.execute(
            select(
                ImperiumVaultTransaction.local_date,
                func.sum(
                    case((ImperiumVaultTransaction.transaction_type == "income", ImperiumVaultTransaction.amount_cents),
                         else_=-ImperiumVaultTransaction.amount_cents)
                ),
            )
            .where(ImperiumVaultTransaction.user_id == current_user.id, ImperiumVaultTransaction.currency == "EUR",
                   ImperiumVaultTransaction.local_date <= today)
            .group_by(ImperiumVaultTransaction.local_date)
        )
    }
    if period == "all":
        from_day = min(daily) if daily else None
        previous = None
    else:
        from_day = today - timedelta(days=PERIOD_DAYS[period] - 1)
        previous_start = from_day - timedelta(days=PERIOD_DAYS[period])
        previous = sum(net for day, net in daily.items() if previous_start <= day < from_day)
    points = []
    if from_day is not None:
        day = from_day
        while day <= today:
            points.append(FinancePointRead(day=day, net_cents=daily.get(day, 0)))
            day += timedelta(days=1)
    period_net = sum(point.net_cents for point in points)
    return HistoryFinancesResponse(
        period=period, from_day=from_day, to_day=today, currency="EUR", points=points, period_net_cents=period_net,
        previous_period_net_cents=previous, delta_cents=period_net - (previous or 0),
        balance_cents=wallet_state(db, current_user=current_user).predicted_total_cents,
    )
