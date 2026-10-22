"""PostgreSQL : calendrier V1 (doc 51) — récurrences, occurrences sautées ou déplacées, conflits, pas de passé,
règle des 7 jours (proposition de préparation d'une échéance, à valider), contrôle du matin, moteur du jour."""
from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("calendar v1 DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.imperium import ImperiumCalendarEvent, ImperiumMission, PlanningDay  # noqa: E402
from app.schemas.imperium import (  # noqa: E402
    CalendarConflictCheck,
    CalendarEventCreate,
    CalendarEventUpdate,
    CalendarOccurrenceOverride,
)
from app.schemas.operations import ProjectCreate, ProjectMissionCreate  # noqa: E402
from app.services.daily import selection  # noqa: E402
from app.services.imperium import calendar, calendar_threshold, operations  # noqa: E402
from app.services.params import set_parameter  # noqa: E402

PARIS = ZoneInfo("Europe/Paris")


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"cal-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _at(days: int, hour: int, minute: int = 0) -> datetime:
    day = datetime.now(PARIS).date() + timedelta(days=days)
    return datetime.combine(day, time(hour, minute), tzinfo=PARIS)


def _create(db, user, **fields):
    payload = CalendarEventCreate(**{"event_type": "event", "title": "Événement", **fields})
    read, _duplicate = calendar.create_calendar_event(db, current_user=user, payload=payload, idempotency_key=str(uuid4()),
                                                      request_method="POST", request_path="/api/imperium/calendar/events")
    return read


def test_recurrence_occurrences_skip_move_and_conflicts(db) -> None:
    user = _user(db)
    start = _at(10, 19)
    dars = _create(db, user, title="Cours Dars", starts_at=start, ends_at=start + timedelta(hours=2),
                   recurrence_rrule="FREQ=WEEKLY;BYDAY=" + ("MO", "TU", "WE", "TH", "FR", "SA", "SU")[start.weekday()])
    assert dars.recurrence_text.startswith("Toutes les semaines le ")
    window = calendar.list_occurrences(db, current_user=user, starts_from=start - timedelta(hours=1),
                                       starts_to=start + timedelta(days=21, hours=3))
    assert [o.starts_at.astimezone(PARIS).hour for o in window] == [19, 19, 19, 19]  # l'heure locale tient
    second = window[1]
    calendar.override_occurrence(db, current_user=user, event_id=dars.id,
                                 payload=CalendarOccurrenceOverride(occurrence_at=second.occurrence_at, action="skip"))
    third = window[2]
    moved_to = third.starts_at + timedelta(days=1, hours=-5)
    calendar.override_occurrence(db, current_user=user, event_id=dars.id, payload=CalendarOccurrenceOverride(
        occurrence_at=third.occurrence_at, action="move", new_starts_at=moved_to, new_ends_at=moved_to + timedelta(hours=2)))
    after = calendar.list_occurrences(db, current_user=user, starts_from=start - timedelta(hours=1),
                                      starts_to=start + timedelta(days=21, hours=3))
    assert len(after) == 3 and after[1].moved and after[1].starts_at == moved_to
    clash = calendar.conflicts(db, current_user=user, check=CalendarConflictCheck(
        starts_at=start + timedelta(minutes=30), ends_at=start + timedelta(minutes=90)))
    assert [c.title for c in clash] == ["Cours Dars"]
    assert calendar.conflicts(db, current_user=user, check=CalendarConflictCheck(
        starts_at=second.starts_at, ends_at=second.starts_at + timedelta(hours=1))) == []  # occurrence sautée
    with pytest.raises(calendar.CalendarEventValidationError):
        calendar.override_occurrence(db, current_user=user, event_id=dars.id, payload=CalendarOccurrenceOverride(
            occurrence_at=start + timedelta(days=2), action="skip"))  # pas une occurrence de la série


def test_no_past_events_and_periods_need_an_end(db) -> None:
    user = _user(db)
    with pytest.raises(calendar.CalendarEventValidationError, match="passé"):
        _create(db, user, starts_at=_at(-2, 10))
    with pytest.raises(calendar.CalendarEventValidationError):
        _create(db, user, event_type="vacation", starts_at=_at(3, 0))
    with pytest.raises(calendar.CalendarEventValidationError, match="Recurrence"):
        _create(db, user, starts_at=_at(3, 10), recurrence_rrule="FREQ=HOURLY")
    today = _create(db, user, title="Journée entière", starts_at=_at(0, 0), ends_at=_at(0, 23, 59), all_day=True)
    assert today.all_day


def test_deadline_in_window_gets_a_free_prep_slot_to_validate(db) -> None:
    user = _user(db)
    far = _create(db, user, event_type="deadline", title="Impôts", starts_at=_at(20, 12), prep_minutes=120)
    assert far.prep_proposal is None  # à plus de 7 jours : seulement rangé
    blocked = _at(2, 8)
    _create(db, user, title="Médecin", starts_at=blocked, ends_at=blocked + timedelta(hours=3))
    deadline = _create(db, user, event_type="deadline", title="Dossier CAF", task="Envoyer le dossier CAF",
                       starts_at=_at(3, 12), prep_minutes=60)
    proposal = deadline.prep_proposal
    assert proposal["status"] == "proposed" and proposal["source"] == "rules"
    slot = datetime.fromisoformat(proposal["starts_at"]).astimezone(PARIS)
    assert slot == _at(2, 11)  # la veille, après le médecin (8 h-11 h)
    hook = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "user.calendar.event_added"))
    assert hook is not None
    accepted = calendar.decide_prep(db, current_user=user, event_id=deadline.id, accept=True)
    mission = db.get(ImperiumMission, accepted.prep_mission_id)
    assert (mission.title, mission.project_id, mission.estimated_minutes) == ("Envoyer le dossier CAF", None, 60)
    assert mission.deadline_at == _at(3, 12) and mission.planned_start_at.astimezone(PARIS) == _at(2, 11)
    with pytest.raises(calendar.CalendarEventValidationError):
        calendar.decide_prep(db, current_user=user, event_id=deadline.id, accept=True)
    calendar.update_calendar_event(db, current_user=user, event_id=deadline.id,
                                   payload=CalendarEventUpdate(starts_at=_at(4, 18)))
    assert mission.deadline_at == _at(4, 18)  # la préparation suit l'échéance
    calendar.delete_calendar_event(db, current_user=user, event_id=deadline.id)
    assert mission.status == "cancelled"


def test_morning_check_urgent_missed_and_completed(db) -> None:
    user = _user(db)
    tomorrow = _create(db, user, event_type="deadline", title="Assurance moto", starts_at=_at(1, 18), prep_minutes=30)
    calendar.decide_prep(db, current_user=user, event_id=tomorrow.id, accept=False)
    soon = _create(db, user, event_type="deadline", title="Rapport", starts_at=_at(1, 20))
    done = calendar.decide_prep(db, current_user=user, event_id=soon.id, accept=True)
    db.get(ImperiumMission, done.prep_mission_id).status = "completed"
    db.commit()
    counts = calendar_threshold.morning_check(db, current_user=user)
    assert counts["urgent"] == 1 and counts["completed"] == 1
    event = db.get(ImperiumCalendarEvent, tomorrow.id)
    urgent = db.get(ImperiumMission, event.prep_mission_id)
    assert urgent.title.startswith("URGENT : Préparer : Assurance moto (échéance demain 18:00)")
    assert db.get(ImperiumCalendarEvent, soon.id).status == "completed"
    assert calendar_threshold.morning_check(db, current_user=user)["urgent"] == 0  # une fois par jour
    later = datetime.combine(_at(1, 18).date() + timedelta(days=1), time(9), tzinfo=PARIS).astimezone(UTC)
    assert calendar_threshold.morning_check(db, current_user=user, now=later)["missed"] == 1
    assert event.status == "deadline_missed"


def test_calendar_bounds_the_day_and_active_projects_feed_it(db) -> None:
    user = _user(db)
    set_parameter(db, code="daily.selection_enabled", value=True, origin="user", rationale_fr="Test.")
    set_parameter(db, code="daily.calendar_commitments_enabled", value=True, origin="user", rationale_fr="Test.")
    now = datetime.now(UTC)
    db.add(PlanningDay(user_id=user.id, started_at=now, start_local_date=now.astimezone(PARIS).date(),
                       timezone="Europe/Paris", felt_energy=3, idempotency_key=str(uuid4())))
    db.commit()
    project = operations.create_project(db, current_user=user, payload=ProjectCreate(title="Site"), idempotency_key=str(uuid4()))
    first = operations.add_project_mission(db, current_user=user, project_id=project.id, idempotency_key=str(uuid4()),
                                           payload=ProjectMissionCreate(title="Maquette", estimated_minutes=30))
    operations.add_project_mission(db, current_user=user, project_id=project.id, idempotency_key=str(uuid4()),
                                   payload=ProjectMissionCreate(title="Textes", estimated_minutes=30))
    row = selection.select_next(db, current_user=user, trigger="manual", now=now)
    assert row.chosen_mission_id == first.id  # la prochaine mission du projet actif, sans date
    meeting = now + timedelta(minutes=40)
    _create(db, user, title="Rendez-vous", starts_at=meeting, ends_at=meeting + timedelta(hours=1))
    row = selection.select_next(db, current_user=user, trigger="manual", now=now)
    assert row.remaining_min <= 25 and row.outcome != "next_mission"  # 40 min − 15 de marge : la mission ne tient plus
    assert db.scalar(select(selection.DailySelectionLog.trigger).where(
        selection.DailySelectionLog.user_id == user.id, selection.DailySelectionLog.trigger == "calendar").limit(1))
