"""Chronologie de l'historique Imperium (IMP.HISTORY.MAIN, doc 65 §7) — lecture seule.

Projection du registre d'événements (table events, en ajout seul) restreinte aux faits
Imperium : missions, journées opérationnelles, plans du jour, décisions (priorités, demandes
de replan) et projets ; plus les Weekly Reviews approuvées (rapports finaux). Les autres
domaines (Vault, Pulse, Path, Vector) n'y entrent pas : leurs données sont plus sensibles et
ont leurs propres écrans.

Filtres de l'écran : all, missions, decisions (priorités, replans, projets), weekly, failed
(missions ratées). La recherche porte sur le titre. Les anciens noms d'événements sont lus
avec les nouveaux (expand_for_read). Au plus HISTORY_SCAN_LIMIT événements récents sont lus
par requête.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.event import Event
from app.models.imperium import ImperiumMission, ImperiumProject, ImperiumWeeklyReviewFinalReport
from app.schemas.history import HistoryEventDetailResponse, HistoryEventListResponse, HistoryEventRead
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
            if payload.get("reason") == "cancelled" or payload.get("decision") == "cancelled":
                kind, status, title = "mission_cancelled", "cancelled", "Mission annulée"
                reason = payload.get("cancellation_reason") or payload.get("note")
            else:
                reason = payload.get("failure_reason") or payload.get("failure_reason_code") or payload.get("reason")
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
