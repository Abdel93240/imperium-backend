"""PostgreSQL : projets, missions de projet et routines (doc 71 §3, §4.1, §8 ; doc 01).

Requiert une base migrée (IMPERIUM_TEST_DATABASE_URL) ; skip local sinon, échec en CI.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("operations DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models.auth import User  # noqa: E402
from app.models.imperium import ImperiumMission, ImperiumRoutine, PlanningDay  # noqa: E402
from app.schemas.operations import (  # noqa: E402
    MissionContentUpdate,
    ProjectCreate,
    ProjectMissionCreate,
    ProjectProgressUpdate,
    ProjectUpdate,
    RoutineCreate,
    RoutineUpdate,
)
from app.services.imperium import operations as ops  # noqa: E402

NOW = datetime.now(UTC).replace(microsecond=0)


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    with Session(engine) as session:
        yield session
        session.rollback()


def _user(db) -> User:
    user_id = uuid4()
    db.execute(
        text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) VALUES (:id, :email, FALSE, now(), now())"),
        {"id": str(user_id), "email": f"ops-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _project(db, user, title, **kwargs):
    return ops.create_project(db, current_user=user, payload=ProjectCreate(title=title, **kwargs), idempotency_key=f"p-{uuid4().hex}")


def _mission(db, user, project, title, **kwargs):
    return ops.add_project_mission(
        db, current_user=user, project_id=project.id, payload=ProjectMissionCreate(title=title, **kwargs), idempotency_key=f"m-{uuid4().hex}"
    )


def _open_day(db, user, local_date=None):
    db.add(PlanningDay(user_id=user.id, started_at=NOW - timedelta(hours=3), start_local_date=local_date or date.today(),
                       timezone="Europe/Paris", felt_energy=3, idempotency_key=f"d-{uuid4().hex}"))
    db.commit()


# ---------- Projets ----------

def test_first_two_projects_of_the_ranking_are_active(db) -> None:
    user = _user(db)
    for title in ("Imperium", "Activité VTC", "Apprendre le russe"):
        _project(db, user, title)

    listing = ops.list_projects(db, current_user=user)

    assert [(p.title, p.rank, p.active) for p in listing.projects] == [
        ("Imperium", 1, True), ("Activité VTC", 2, True), ("Apprendre le russe", 3, False)]


def test_reorder_moves_a_project_into_the_active_slots(db) -> None:
    user = _user(db)
    a, b, c = (_project(db, user, t) for t in ("A", "B", "C"))

    listing = ops.reorder_projects(db, current_user=user, project_ids=[c.id, a.id, b.id])

    assert [(p.title, p.active) for p in listing.projects] == [("C", True), ("A", True), ("B", False)]


def test_reorder_requires_the_exact_set_of_open_projects(db) -> None:
    user = _user(db)
    a, b = _project(db, user, "A"), _project(db, user, "B")
    with pytest.raises(ops.OperationsValidationError):
        ops.reorder_projects(db, current_user=user, project_ids=[a.id])
    with pytest.raises(ops.OperationsValidationError):
        ops.reorder_projects(db, current_user=user, project_ids=[a.id, b.id, uuid4()])


def test_update_project_title_and_description(db) -> None:
    user = _user(db)
    project = _project(db, user, "Russe")
    updated = ops.update_project(db, current_user=user, project_id=project.id,
                                 payload=ProjectUpdate(title="Apprendre le russe", description="Conversation simple."))
    assert updated.title == "Apprendre le russe" and updated.description == "Conversation simple."


def test_delete_project_cancels_future_missions_and_keeps_history(db) -> None:
    user = _user(db)
    project = _project(db, user, "Navettes")
    done = _mission(db, user, project, "Étudier la demande")
    todo = _mission(db, user, project, "Contacter l'aéroport")
    db.get(ImperiumMission, done.id).status = "completed"
    db.commit()

    ops.delete_project(db, current_user=user, project_id=project.id, now=NOW)

    assert db.get(ImperiumMission, todo.id).status == "cancelled"
    assert db.get(ImperiumMission, todo.id).completion_note == "Projet supprimé"
    assert db.get(ImperiumMission, done.id).status == "completed"
    assert db.get(ImperiumMission, done.id).project_id == project.id  # nom du projet figé dans l'historique
    assert [p.title for p in ops.list_projects(db, current_user=user).projects] == []


def test_completing_the_first_project_promotes_the_next(db) -> None:
    user = _user(db)
    for title in ("Imperium", "Activité VTC", "Apprendre le russe"):
        _project(db, user, title)
    first = ops.list_projects(db, current_user=user).projects[0]

    ops.complete_project(db, current_user=user, project_id=first.id, now=NOW)

    listing = ops.list_projects(db, current_user=user)
    assert [(p.title, p.rank, p.active) for p in listing.projects] == [("Activité VTC", 1, True), ("Apprendre le russe", 2, True)]
    assert [p.title for p in ops.list_completed_projects(db, current_user=user)] == ["Imperium"]


def test_progress_comes_from_the_weekly_review_and_is_bounded(db) -> None:
    user = _user(db)
    project = _project(db, user, "Activité VTC")
    assert project.progress_percent is None  # barre masquée avant la première WR

    updated = ops.record_project_progress(db, project_id=project.id, payload=ProjectProgressUpdate(percent=35, why="Les premières étapes sont terminées."), now=NOW)

    assert updated.progress_percent == 35 and updated.progress_why.startswith("Les premières") and updated.progress_at == NOW


def test_progress_percent_is_constrained_in_db(db) -> None:
    user = _user(db)
    project = _project(db, user, "X")
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE imperium_projects SET progress_percent = 120 WHERE id = :id"), {"id": str(project.id)})


# ---------- Missions de projet ----------

def test_project_missions_are_ordered_and_carry_content(db) -> None:
    user = _user(db)
    project = _project(db, user, "Apprendre le russe")
    first = _mission(db, user, project, "Choisir une méthode", estimated_minutes=15)
    second = _mission(db, user, project, "Faire des cours avec Ivanov", description="Conversation et prononciation.",
                      notes="Ivanov est disponible le vendredi de 14 h à 16 h.", estimated_minutes=60)

    ops.reorder_project_missions(db, current_user=user, project_id=project.id, mission_ids=[second.id, first.id])
    listing = ops.list_projects(db, current_user=user)

    missions = listing.projects[0].missions
    assert [m.title for m in missions] == ["Faire des cours avec Ivanov", "Choisir une méthode"]
    assert missions[0].notes.startswith("Ivanov") and missions[0].estimated_minutes == 60
    assert db.get(ImperiumMission, second.id).status == "backlog"
    assert listing.projects[0].next_mission_title == "Faire des cours avec Ivanov"


def test_mission_content_update_and_terminal_missions_are_read_only(db) -> None:
    user = _user(db)
    project = _project(db, user, "P")
    mission = _mission(db, user, project, "M")
    updated = ops.update_mission_content(db, current_user=user, mission_id=mission.id,
                                         payload=MissionContentUpdate(notes="Nouvelle note", estimated_minutes=20))
    assert updated.notes == "Nouvelle note" and updated.estimated_minutes == 20

    db.get(ImperiumMission, mission.id).status = "completed"
    db.commit()
    with pytest.raises(ops.OperationsConflictError):
        ops.update_mission_content(db, current_user=user, mission_id=mission.id, payload=MissionContentUpdate(notes="x"))


def test_delete_mission_cancels_only_unfinished_missions(db) -> None:
    user = _user(db)
    project = _project(db, user, "P")
    todo, done = _mission(db, user, project, "À faire"), _mission(db, user, project, "Faite")
    db.get(ImperiumMission, done.id).status = "completed"
    db.commit()

    ops.delete_mission(db, current_user=user, mission_id=todo.id, now=NOW)

    assert db.get(ImperiumMission, todo.id).status == "cancelled"
    with pytest.raises(ops.OperationsConflictError):
        ops.delete_mission(db, current_user=user, mission_id=done.id, now=NOW)


def test_other_users_projects_are_invisible(db) -> None:
    user, stranger = _user(db), _user(db)
    project = _project(db, user, "Privé")
    with pytest.raises(ops.OperationsNotFoundError):
        ops.update_project(db, current_user=stranger, project_id=project.id, payload=ProjectUpdate(title="x"))


def test_project_create_is_idempotent(db) -> None:
    user = _user(db)
    first = ops.create_project(db, current_user=user, payload=ProjectCreate(title="Bureau"), idempotency_key="same")
    again = ops.create_project(db, current_user=user, payload=ProjectCreate(title="Bureau"), idempotency_key="same")
    assert again.id == first.id and len(ops.list_projects(db, current_user=user).projects) == 1


# ---------- Routines ----------

def _routine(db, user, name, **kwargs):
    return ops.create_routine(db, current_user=user, payload=RoutineCreate(name=name, **kwargs), idempotency_key=f"r-{uuid4().hex}")


def test_routine_fields_and_hidden_pins(db) -> None:
    user = _user(db)
    routine = _routine(db, user, "Entretien du véhicule", frequency="weekly", estimated_minutes=30, priority="high")
    updated = ops.update_routine(db, current_user=user, routine_id=routine.id,
                                 payload=RoutineUpdate(pinned_weekday=6, pinned_time=time(9, 0)))
    assert (updated.frequency, updated.priority, updated.pinned_weekday, updated.pinned_time) == ("weekly", "high", 6, time(9, 0))


def test_routine_constraints_in_db(db) -> None:
    user = _user(db)
    routine = _routine(db, user, "Lecture", frequency="daily")
    db.get(ImperiumRoutine, routine.id).frequency = "twice_a_week"
    with pytest.raises(IntegrityError):
        db.commit()


def test_today_lists_daily_routines_and_placed_ones_with_total(db) -> None:
    user = _user(db)
    _open_day(db, user)
    _routine(db, user, "Lecture", frequency="daily", estimated_minutes=20)
    _routine(db, user, "Mobilité", frequency="daily", estimated_minutes=10)
    weekly = _routine(db, user, "Entretien du véhicule", frequency="weekly", estimated_minutes=30)
    _routine(db, user, "Classement des papiers", frequency="biweekly", estimated_minutes=20)
    paused = _routine(db, user, "Rangement", frequency="daily", estimated_minutes=15)
    ops.update_routine(db, current_user=user, routine_id=paused.id, payload=RoutineUpdate(active=False))

    ops.place_routine(db, current_user=user, routine_id=weekly.id)
    today = ops.today_routines(db, current_user=user)

    assert sorted(item.name for item in today.items) == ["Entretien du véhicule", "Lecture", "Mobilité"]
    assert today.total_minutes == 60


def test_check_routine_for_the_operational_day(db) -> None:
    user = _user(db)
    _open_day(db, user)
    routine = _routine(db, user, "Lecture", frequency="daily", estimated_minutes=20)

    ops.check_routine(db, current_user=user, routine_id=routine.id, done=True, now=NOW)
    today = ops.today_routines(db, current_user=user)
    assert today.items[0].done is True

    ops.check_routine(db, current_user=user, routine_id=routine.id, done=False, now=NOW)
    assert ops.today_routines(db, current_user=user).items[0].done is False


def test_routines_require_an_open_day_for_today(db) -> None:
    user = _user(db)
    routine = _routine(db, user, "Lecture", frequency="daily")
    with pytest.raises(ops.OperationsConflictError):
        ops.check_routine(db, current_user=user, routine_id=routine.id, done=True, now=NOW)


def test_delete_routine_keeps_past_checks(db) -> None:
    user = _user(db)
    _open_day(db, user)
    routine = _routine(db, user, "Lecture", frequency="daily", estimated_minutes=20)
    ops.check_routine(db, current_user=user, routine_id=routine.id, done=True, now=NOW)

    ops.delete_routine(db, current_user=user, routine_id=routine.id, now=NOW)

    assert ops.list_routines(db, current_user=user).routines == []
    assert ops.today_routines(db, current_user=user).items == []
    remaining = db.execute(text("SELECT count(*) FROM imperium_routine_checks WHERE routine_id = :id"), {"id": str(routine.id)}).scalar()
    assert remaining == 1


def test_daily_routine_cannot_be_placed(db) -> None:
    user = _user(db)
    _open_day(db, user)
    routine = _routine(db, user, "Lecture", frequency="daily")
    with pytest.raises(ops.OperationsValidationError):
        ops.place_routine(db, current_user=user, routine_id=routine.id)
