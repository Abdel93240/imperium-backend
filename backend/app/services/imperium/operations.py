"""Opérations : projets, missions de projet, missions hors projet et routines (doc 71 §3, §4.1, §8 ; doc 01).

Règles V1 (décisions utilisateur 2026-10-15/16/17) :
- les 2 premiers projets du classement sont actifs ; pas d'activation manuelle ;
- la complétion d'un projet est un acte explicite ; le suivant remonte par le classement ;
- suppressions : le passé est conservé (missions à venir annulées, coches gardées) ;
- une mission terminée ne se supprime pas et ses contenus sont en lecture seule ;
- routines : 4 fréquences fermées ; jour/heure forcés seulement via le chatbot ;
  le jour liste les quotidiennes actives et les routines placées ce jour-là ;
- missions hors projet (paperasse, démarches… ; décision utilisateur 2026-10-21) : missions du backlog sans
  projet, ni annexe, ni engagement fixe ; le moteur du jour les propose dès leur date de début ou à leur
  échéance. « Faite » les termine hors du plan du jour (comme une mission faite ailleurs).
"""

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import IdempotencyStatus
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumMission, ImperiumProject, ImperiumRoutine, ImperiumRoutineCheck
from app.schemas.operations import (
    IntrinsicMissionCreate,
    IntrinsicMissionListResponse,
    IntrinsicMissionRead,
    MissionContentUpdate,
    ProjectCreate,
    ProjectListResponse,
    ProjectMissionCreate,
    ProjectMissionRead,
    ProjectProgressUpdate,
    ProjectRead,
    ProjectUpdate,
    RoutineCreate,
    RoutineListResponse,
    RoutineRead,
    RoutineTodayItem,
    RoutineTodayResponse,
    RoutineUpdate,
)
from app.services.events.emitter import build_event
from app.services.imperium.planning_days import get_current_planning_day

ACTIVE_PROJECT_SLOTS = 2
TERMINAL_MISSION_STATUSES = ("completed", "failed", "abandoned", "cancelled")
UNFINISHED_MISSION_STATUSES = ("backlog", "active", "standby")


class OperationsNotFoundError(ValueError):
    pass


class OperationsConflictError(ValueError):
    pass


class OperationsValidationError(ValueError):
    pass


# ---------- Projets ----------

def list_projects(db: Session, *, current_user: User) -> ProjectListResponse:
    projects = _open_projects(db, current_user=current_user)
    reads = _project_reads(db, projects)
    return ProjectListResponse(projects=reads, active_count=sum(1 for read in reads if read.active))


def list_completed_projects(db: Session, *, current_user: User) -> list[ProjectRead]:
    projects = list(
        db.scalars(
            select(ImperiumProject)
            .where(ImperiumProject.user_id == current_user.id, ImperiumProject.status == "completed")
            .order_by(ImperiumProject.completed_at.desc())
        )
    )
    return _project_reads(db, projects, active_slots=0)


def create_project(db: Session, *, current_user: User, payload: ProjectCreate, idempotency_key: str) -> ProjectRead:
    existing = db.scalar(
        select(ImperiumProject).where(
            ImperiumProject.user_id == current_user.id, ImperiumProject.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        if existing.title != payload.title:
            raise OperationsConflictError("Idempotency key already used with different payload.")
        return _single_read(db, current_user, existing)
    last_rank = db.scalar(
        select(func.max(ImperiumProject.rank_order)).where(
            ImperiumProject.user_id == current_user.id, ImperiumProject.status == "open"
        )
    )
    project = ImperiumProject(
        id=uuid4(),
        user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        source=payload.source,
        rank_order=(last_rank or 0) + 1,
        status="open",
        idempotency_key=idempotency_key,
    )
    db.add(project)
    db.flush()
    _emit(db, current_user, "planning.project.created", {"project_id": str(project.id), "source": payload.source,
                                                         "rank": project.rank_order}, f"project-create:{project.id}")
    db.commit()
    return _single_read(db, current_user, project)


def update_project(db: Session, *, current_user: User, project_id: UUID, payload: ProjectUpdate) -> ProjectRead:
    project = _get_open_project(db, current_user=current_user, project_id=project_id)
    for field in payload.model_fields_set:
        setattr(project, field, getattr(payload, field))
    db.commit()
    return _single_read(db, current_user, project)


def reorder_projects(db: Session, *, current_user: User, project_ids: list[UUID]) -> ProjectListResponse:
    projects = _open_projects(db, current_user=current_user)
    by_id = {project.id: project for project in projects}
    if set(project_ids) != set(by_id) or len(project_ids) != len(by_id):
        raise OperationsValidationError("project_ids must list every open project exactly once.")
    for rank, project_id in enumerate(project_ids, start=1):
        by_id[project_id].rank_order = rank
    _emit(db, current_user, "planning.project.reordered", {"project_ids": [str(pid) for pid in project_ids]},
          f"project-reorder:{uuid4().hex}")
    db.commit()
    return list_projects(db, current_user=current_user)


def delete_project(db: Session, *, current_user: User, project_id: UUID, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    project = _get_open_project(db, current_user=current_user, project_id=project_id)
    cancelled = 0
    for mission in db.scalars(
        select(ImperiumMission).where(
            ImperiumMission.project_id == project.id, ImperiumMission.status.in_(UNFINISHED_MISSION_STATUSES)
        )
    ):
        _cancel_mission(mission, now=now, note="Projet supprimé")
        cancelled += 1
    project.status = "deleted"
    project.deleted_at = now
    _normalize_ranks(_open_projects(db, current_user=current_user, exclude=project.id))
    _emit(db, current_user, "planning.project.deleted", {"project_id": str(project.id), "cancelled_missions": cancelled},
          f"project-delete:{project.id}")
    db.commit()


def complete_project(db: Session, *, current_user: User, project_id: UUID, now: datetime | None = None) -> ProjectRead:
    """Complétion explicite (doc 01 : jamais purement automatique) ; le suivant remonte."""
    now = now or datetime.now(UTC)
    project = _get_open_project(db, current_user=current_user, project_id=project_id)
    project.status = "completed"
    project.completed_at = now
    project.completion_method = "manual"
    remaining = _open_projects(db, current_user=current_user, exclude=project.id)
    _normalize_ranks(remaining)
    _emit(db, current_user, "planning.project.completed",
          {"project_id": str(project.id), "promoted_project_ids": [str(p.id) for p in remaining[:ACTIVE_PROJECT_SLOTS]]},
          f"project-complete:{project.id}")
    db.commit()
    return _project_reads(db, [project], active_slots=0)[0]


def record_project_progress(
    db: Session, *, project_id: UUID, payload: ProjectProgressUpdate, now: datetime | None = None
) -> ProjectRead:
    """Estimation déposée par la Weekly Review (route interne, doc 47 §11)."""
    project = db.get(ImperiumProject, project_id)
    if project is None or project.status != "open":
        raise OperationsNotFoundError("Open project not found.")
    project.progress_percent = payload.percent
    project.progress_why = payload.why
    project.progress_at = now or datetime.now(UTC)
    db.commit()
    user = db.get(User, project.user_id)
    return _single_read(db, user, project)


# ---------- Missions de projet ----------

def add_project_mission(
    db: Session, *, current_user: User, project_id: UUID, payload: ProjectMissionCreate, idempotency_key: str
) -> ProjectMissionRead:
    existing = db.scalar(
        select(IdempotencyKey).where(IdempotencyKey.user_id == current_user.id, IdempotencyKey.idempotency_key == idempotency_key)
    )
    if existing is not None and existing.response_body is not None:
        return ProjectMissionRead(**existing.response_body)
    project = _get_open_project(db, current_user=current_user, project_id=project_id)
    last_position = db.scalar(select(func.max(ImperiumMission.project_position)).where(ImperiumMission.project_id == project.id))
    now = datetime.now(UTC)
    mission = ImperiumMission(
        id=uuid4(),
        user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        notes=payload.notes,
        estimated_minutes=payload.estimated_minutes,
        project_id=project.id,
        project_position=(last_position or 0) + 1,
        status="backlog",
        started_at=now,
    )
    db.add(mission)
    db.flush()
    event = _emit(db, current_user, "planning.mission.created",
                  {"mission_id": str(mission.id), "project_id": str(project.id), "created_by": "user"}, idempotency_key)
    db.flush()
    mission.created_by_event_id = event.id
    read = ProjectMissionRead.model_validate(mission)
    db.add(
        IdempotencyKey(
            user_id=current_user.id,
            idempotency_key=idempotency_key,
            request_method="POST",
            request_path=f"/api/imperium/projects/{project.id}/missions",
            request_hash=f"project-mission:{project.id}:{payload.title}",
            status=IdempotencyStatus.completed,
            response_status_code=201,
            response_body=read.model_dump(mode="json"),
        )
    )
    db.commit()
    return read


def update_mission_content(
    db: Session, *, current_user: User, mission_id: UUID, payload: MissionContentUpdate
) -> ProjectMissionRead:
    mission = _get_user_mission(db, current_user=current_user, mission_id=mission_id)
    if mission.status in TERMINAL_MISSION_STATUSES:
        raise OperationsConflictError("A finished mission is read-only.")
    for field in payload.model_fields_set:
        setattr(mission, field, getattr(payload, field))
    db.commit()
    return ProjectMissionRead.model_validate(mission)


def reorder_project_missions(db: Session, *, current_user: User, project_id: UUID, mission_ids: list[UUID]) -> None:
    project = _get_open_project(db, current_user=current_user, project_id=project_id)
    missions = list(
        db.scalars(select(ImperiumMission).where(ImperiumMission.project_id == project.id, ImperiumMission.status != "cancelled"))
    )
    by_id = {mission.id: mission for mission in missions}
    if set(mission_ids) != set(by_id) or len(mission_ids) != len(by_id):
        raise OperationsValidationError("mission_ids must list every mission of the project exactly once.")
    for position, mission_id in enumerate(mission_ids, start=1):
        by_id[mission_id].project_position = position
    db.commit()


def delete_mission(db: Session, *, current_user: User, mission_id: UUID, now: datetime | None = None) -> None:
    """Seule une mission non faite se supprime : elle passe en annulée (doc 71)."""
    mission = _get_user_mission(db, current_user=current_user, mission_id=mission_id)
    if mission.status in TERMINAL_MISSION_STATUSES:
        raise OperationsConflictError("A finished mission cannot be deleted.")
    _cancel_mission(mission, now=now or datetime.now(UTC), note="Supprimée par l'utilisateur")
    _emit(db, current_user, "mission.abandoned", {"mission_id": str(mission.id), "reason": "deleted_by_user"},
          f"mission-delete:{mission.id}")
    db.commit()


# ---------- Missions hors projet ----------

INTRINSIC_DONE_SHOWN = 10


def list_intrinsic_missions(db: Session, *, current_user: User) -> IntrinsicMissionListResponse:
    """À faire (échéance la plus proche d'abord, puis date de début, puis ancienneté) et dernières faites."""
    base = select(ImperiumMission).where(
        ImperiumMission.user_id == current_user.id, ImperiumMission.project_id.is_(None),
        ImperiumMission.annex_of_mission_id.is_(None), ImperiumMission.is_fixed_commitment.is_(False))
    todo = db.scalars(base.where(ImperiumMission.status.in_(UNFINISHED_MISSION_STATUSES)).order_by(
        ImperiumMission.deadline_at.asc().nulls_last(), ImperiumMission.planned_start_at.asc().nulls_last(),
        ImperiumMission.created_at.asc()))
    done = db.scalars(base.where(ImperiumMission.status == "completed")
                      .order_by(ImperiumMission.ended_at.desc().nulls_last()).limit(INTRINSIC_DONE_SHOWN))
    return IntrinsicMissionListResponse(missions=[IntrinsicMissionRead.model_validate(m) for m in todo],
                                        done=[IntrinsicMissionRead.model_validate(m) for m in done])


def create_intrinsic_mission(
    db: Session, *, current_user: User, payload: IntrinsicMissionCreate, idempotency_key: str
) -> IntrinsicMissionRead:
    existing = db.scalar(
        select(IdempotencyKey).where(IdempotencyKey.user_id == current_user.id, IdempotencyKey.idempotency_key == idempotency_key)
    )
    if existing is not None and existing.response_body is not None:
        return IntrinsicMissionRead(**existing.response_body)
    now = datetime.now(UTC)
    mission = ImperiumMission(
        id=uuid4(), user_id=current_user.id, title=payload.title, description=payload.description, notes=payload.notes,
        domain=payload.domain, deadline_at=payload.deadline_at, planned_start_at=payload.planned_start_at,
        estimated_minutes=payload.estimated_minutes, status="backlog", started_at=now,
    )
    db.add(mission)
    db.flush()
    event = _emit(db, current_user, "planning.mission.created",
                  {"mission_id": str(mission.id), "project_id": None, "created_by": payload.source}, idempotency_key)
    db.flush()
    mission.created_by_event_id = event.id
    read = IntrinsicMissionRead.model_validate(mission)
    db.add(
        IdempotencyKey(
            user_id=current_user.id,
            idempotency_key=idempotency_key,
            request_method="POST",
            request_path="/api/imperium/intrinsic-missions",
            request_hash=f"intrinsic-mission:{payload.title}",
            status=IdempotencyStatus.completed,
            response_status_code=201,
            response_body=read.model_dump(mode="json"),
        )
    )
    db.commit()
    return read


def mark_mission_done(db: Session, *, current_user: User, mission_id: UUID, now: datetime | None = None
                      ) -> IntrinsicMissionRead:
    """« Faite » hors du plan du jour : une mission ouverte et pas en cours se termine (événement de complétion)."""
    mission = _get_user_mission(db, current_user=current_user, mission_id=mission_id)
    if mission.status not in ("backlog", "standby"):
        raise OperationsConflictError("Only a mission waiting in the backlog or in standby can be marked done here.")
    now = now or datetime.now(UTC)
    event = _emit(db, current_user, "mission.completed",
                  {"mission_id": str(mission.id), "outcome": "completed", "reason": "Faite hors du plan du jour."},
                  f"mission-done:{mission.id}")
    db.flush()
    for annex in mission.pending_annexes or []:
        annex.annex_of_mission_id = None
    mission.status, mission.ended_at, mission.completion_note = "completed", now, "Faite hors du plan du jour."
    mission.ended_by_event_id = event.id
    db.commit()
    return IntrinsicMissionRead.model_validate(mission)


# ---------- Routines ----------

def list_routines(db: Session, *, current_user: User) -> RoutineListResponse:
    return RoutineListResponse(routines=[RoutineRead.model_validate(r) for r in _routines(db, current_user=current_user)])


def create_routine(db: Session, *, current_user: User, payload: RoutineCreate, idempotency_key: str) -> RoutineRead:
    existing = db.scalar(
        select(ImperiumRoutine).where(
            ImperiumRoutine.user_id == current_user.id, ImperiumRoutine.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        if existing.name != payload.name:
            raise OperationsConflictError("Idempotency key already used with different payload.")
        return RoutineRead.model_validate(existing)
    routine = ImperiumRoutine(
        id=uuid4(),
        user_id=current_user.id,
        name=payload.name,
        frequency=payload.frequency.value,
        estimated_minutes=payload.estimated_minutes,
        priority=payload.priority.value,
        notes=payload.notes,
        active=payload.active,
        anchor_date=datetime.now(UTC).date(),
        idempotency_key=idempotency_key,
    )
    db.add(routine)
    db.commit()
    return RoutineRead.model_validate(routine)


def update_routine(db: Session, *, current_user: User, routine_id: UUID, payload: RoutineUpdate) -> RoutineRead:
    routine = _get_routine(db, current_user=current_user, routine_id=routine_id)
    for field in payload.model_fields_set - {"clear_pins"}:
        value = getattr(payload, field)
        setattr(routine, field, value.value if hasattr(value, "value") else value)
    if payload.clear_pins:
        routine.pinned_weekday = routine.pinned_month_day = routine.pinned_time = None
    db.commit()
    return RoutineRead.model_validate(routine)


def delete_routine(db: Session, *, current_user: User, routine_id: UUID, now: datetime | None = None) -> None:
    """Elle ne sera plus planifiée ; l'historique (coches) est conservé."""
    routine = _get_routine(db, current_user=current_user, routine_id=routine_id)
    routine.deleted_at = now or datetime.now(UTC)
    routine.active = False
    db.commit()


def today_routines(db: Session, *, current_user: User) -> RoutineTodayResponse:
    day = get_current_planning_day(db, current_user=current_user)
    if day is None:
        return RoutineTodayResponse(operational_date=None, items=[], total_minutes=0)
    checks = {
        check.routine_id: check
        for check in db.scalars(
            select(ImperiumRoutineCheck).where(
                ImperiumRoutineCheck.user_id == current_user.id,
                ImperiumRoutineCheck.operational_date == day.start_local_date,
            )
        )
    }
    items = []
    for routine in _routines(db, current_user=current_user):
        if not routine.active:
            continue
        check = checks.get(routine.id)
        if routine.frequency != "daily" and check is None:
            continue  # non quotidienne : seulement le jour où elle est placée
        items.append(
            RoutineTodayItem(
                routine_id=routine.id,
                name=routine.name,
                frequency=routine.frequency,
                estimated_minutes=routine.estimated_minutes,
                priority=routine.priority,
                done=check is not None and check.status == "done",
            )
        )
    return RoutineTodayResponse(
        operational_date=day.start_local_date,
        items=items,
        total_minutes=sum(item.estimated_minutes or 0 for item in items),
    )


def place_routine(
    db: Session, *, current_user: User, routine_id: UUID, operational_date: date | None = None
) -> RoutineTodayResponse:
    """Le planificateur (ou le chatbot) place une routine non quotidienne sur une journée."""
    routine = _get_routine(db, current_user=current_user, routine_id=routine_id)
    if routine.frequency == "daily":
        raise OperationsValidationError("Daily routines are listed every day and cannot be placed.")
    if not routine.active:
        raise OperationsConflictError("Inactive routines cannot be placed.")
    day = _require_open_day(db, current_user=current_user)
    target = operational_date or day.start_local_date
    _upsert_check(db, current_user, routine, day_id=day.id, operational_date=target, status="planned", checked_at=None,
                  keep_done=True)
    db.commit()
    return today_routines(db, current_user=current_user)


def check_routine(
    db: Session, *, current_user: User, routine_id: UUID, done: bool, now: datetime | None = None
) -> RoutineTodayResponse:
    routine = _get_routine(db, current_user=current_user, routine_id=routine_id)
    day = _require_open_day(db, current_user=current_user)
    _upsert_check(db, current_user, routine, day_id=day.id, operational_date=day.start_local_date,
                  status="done" if done else "planned", checked_at=(now or datetime.now(UTC)) if done else None)
    db.commit()
    return today_routines(db, current_user=current_user)


# ---------- internes ----------

def _open_projects(db: Session, *, current_user: User, exclude: UUID | None = None) -> list[ImperiumProject]:
    query = select(ImperiumProject).where(ImperiumProject.user_id == current_user.id, ImperiumProject.status == "open")
    if exclude is not None:
        query = query.where(ImperiumProject.id != exclude)
    return list(db.scalars(query.order_by(ImperiumProject.rank_order.asc(), ImperiumProject.created_at.asc())))


def _normalize_ranks(projects: list[ImperiumProject]) -> None:
    for rank, project in enumerate(projects, start=1):
        project.rank_order = rank


def _project_reads(db: Session, projects: list[ImperiumProject], *, active_slots: int = ACTIVE_PROJECT_SLOTS) -> list[ProjectRead]:
    if not projects:
        return []
    missions_by_project: dict[UUID, list[ImperiumMission]] = {project.id: [] for project in projects}
    for mission in db.scalars(
        select(ImperiumMission)
        .where(ImperiumMission.project_id.in_(missions_by_project), ImperiumMission.status != "cancelled")
        .order_by(ImperiumMission.project_position.asc().nulls_last(), ImperiumMission.created_at.asc())
    ):
        missions_by_project[mission.project_id].append(mission)
    reads = []
    for index, project in enumerate(projects):
        read = ProjectRead.model_validate(project)
        read.active = project.status == "open" and index < active_slots
        missions = missions_by_project[project.id]
        read.missions = [ProjectMissionRead.model_validate(mission) for mission in missions]
        upcoming = next((m for m in missions if m.status in UNFINISHED_MISSION_STATUSES), None)
        read.next_mission_title = upcoming.title if upcoming else None
        reads.append(read)
    return reads


def _single_read(db: Session, current_user: User, project: ImperiumProject) -> ProjectRead:
    for read in list_projects(db, current_user=current_user).projects:
        if read.id == project.id:
            return read
    return _project_reads(db, [project], active_slots=0)[0]


def _get_open_project(db: Session, *, current_user: User, project_id: UUID) -> ImperiumProject:
    project = db.get(ImperiumProject, project_id)
    if project is None or project.user_id != current_user.id or project.status != "open":
        raise OperationsNotFoundError("Project not found.")
    return project


def _get_user_mission(db: Session, *, current_user: User, mission_id: UUID) -> ImperiumMission:
    mission = db.get(ImperiumMission, mission_id)
    if mission is None or mission.user_id != current_user.id:
        raise OperationsNotFoundError("Mission not found.")
    return mission


def _cancel_mission(mission: ImperiumMission, *, now: datetime, note: str) -> None:
    for annex in mission.pending_annexes or []:
        annex.annex_of_mission_id = None
    mission.status = "cancelled"
    mission.ended_at = now
    mission.completion_note = note
    mission.planned_start_at = mission.planned_end_at = None


def _routines(db: Session, *, current_user: User) -> list[ImperiumRoutine]:
    return list(
        db.scalars(
            select(ImperiumRoutine)
            .where(ImperiumRoutine.user_id == current_user.id, ImperiumRoutine.deleted_at.is_(None))
            .order_by(ImperiumRoutine.created_at.asc(), ImperiumRoutine.id.asc())
        )
    )


def _get_routine(db: Session, *, current_user: User, routine_id: UUID) -> ImperiumRoutine:
    routine = db.get(ImperiumRoutine, routine_id)
    if routine is None or routine.user_id != current_user.id or routine.deleted_at is not None:
        raise OperationsNotFoundError("Routine not found.")
    return routine


def _require_open_day(db: Session, *, current_user: User):
    day = get_current_planning_day(db, current_user=current_user)
    if day is None:
        raise OperationsConflictError("No operational day is open.")
    return day


def _upsert_check(db, current_user, routine, *, day_id, operational_date, status, checked_at, keep_done=False) -> None:
    check = db.scalar(
        select(ImperiumRoutineCheck).where(
            ImperiumRoutineCheck.routine_id == routine.id, ImperiumRoutineCheck.operational_date == operational_date
        )
    )
    if check is None:
        db.add(
            ImperiumRoutineCheck(
                id=uuid4(),
                user_id=current_user.id,
                routine_id=routine.id,
                planning_day_id=day_id,
                operational_date=operational_date,
                status=status,
                checked_at=checked_at,
            )
        )
        return
    if keep_done and check.status == "done":
        return
    check.status = status
    check.checked_at = checked_at


def _emit(db: Session, current_user: User, event_type: str, payload: dict, idempotency_key: str):
    event = build_event(db, user_id=current_user.id, event_type=event_type, payload=payload, idempotency_key=idempotency_key)
    db.add(event)
    return event
