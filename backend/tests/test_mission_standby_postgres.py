"""PostgreSQL : clôture de journée et statut standby (doc 43 §5.4, décision 2026-10-16).

Requiert une base migrée (IMPERIUM_TEST_DATABASE_URL) ; skip local sinon, échec en CI.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("mission standby DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models.auth import User  # noqa: E402
from app.models.imperium import ImperiumMission, PlanningDay  # noqa: E402
from app.schemas.imperium import AttachAnnexesRequest, FinishDayRequest, ResolveStandbyRequest  # noqa: E402
from app.services.imperium.day_finish import NoOpenPlanningDayError, finish_day  # noqa: E402
from app.services.imperium.missions import (  # noqa: E402
    MissionStateConflictError,
    attach_annexes,
    list_standby_missions,
    resolve_standby_mission,
)

NOW = datetime.now(UTC)
PAST = NOW - timedelta(hours=2)
FUTURE = NOW + timedelta(days=2)


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


def _user(db: Session) -> User:
    user_id = uuid4()
    db.execute(
        text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) VALUES (:id, :email, FALSE, now(), now())"),
        {"id": str(user_id), "email": f"standby-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _open_day(db: Session, user: User) -> PlanningDay:
    day = PlanningDay(
        user_id=user.id,
        started_at=NOW - timedelta(hours=10),
        start_local_date=(NOW - timedelta(hours=10)).date(),
        timezone="Europe/Paris",
        felt_energy=3,
        idempotency_key=f"start-{uuid4().hex}",
    )
    db.add(day)
    db.commit()
    return day


def _mission(db, user, *, status="backlog", planned=True, deadline=None, minutes=None, title=None) -> ImperiumMission:
    mission = ImperiumMission(
        user_id=user.id,
        title=title or f"Mission {uuid4().hex[:6]}",
        status=status,
        planned_start_at=NOW - timedelta(hours=1) if planned else None,
        planned_end_at=NOW if planned else None,
        deadline_at=deadline,
        estimated_minutes=minutes,
        started_at=NOW - timedelta(hours=3),
    )
    db.add(mission)
    db.commit()
    return mission


def _finish(db, user):
    return finish_day(
        db,
        current_user=user,
        payload=FinishDayRequest(local_date=NOW.date(), timezone="Europe/Paris", day_status="completed"),
        idempotency_key=f"finish-{uuid4().hex}",
        request_method="POST",
        request_path="/api/imperium/day/finish",
    )


def _resolve(db, user, mission, **kwargs):
    return resolve_standby_mission(
        db,
        current_user=user,
        mission_id=mission.id,
        payload=ResolveStandbyRequest(**kwargs),
        idempotency_key=f"resolve-{uuid4().hex}",
        request_method="POST",
        request_path=f"/api/imperium/missions/{mission.id}/standby/resolve",
    )


# ---------- Schéma ----------

def test_standby_status_and_deadline_column_are_accepted(db) -> None:
    user = _user(db)
    mission = _mission(db, user, status="standby", deadline=PAST)
    db.refresh(mission)
    assert mission.status == "standby" and mission.deadline_at is not None


def test_unknown_status_still_rejected(db) -> None:
    user = _user(db)
    with pytest.raises(IntegrityError):
        _mission(db, user, status="expired")


# ---------- Clôture de journée ----------

def test_finish_day_returns_unfinished_missions_to_backlog(db) -> None:
    user = _user(db)
    _open_day(db, user)
    active = _mission(db, user, status="active", deadline=FUTURE)
    planned = _mission(db, user)

    response, _ = _finish(db, user)

    for mission in (active, planned):
        db.refresh(mission)
        assert mission.status == "backlog"
        assert mission.planned_start_at is None and mission.planned_end_at is None
    assert response.missions_returned_to_backlog == 2
    assert response.missions_to_standby == 0


def test_finish_day_puts_overdue_missions_in_standby(db) -> None:
    user = _user(db)
    _open_day(db, user)
    overdue_active = _mission(db, user, status="active", deadline=PAST)
    overdue_planned = _mission(db, user, deadline=PAST)

    response, _ = _finish(db, user)

    for mission in (overdue_active, overdue_planned):
        db.refresh(mission)
        assert mission.status == "standby"
    assert response.missions_to_standby == 2
    assert sorted(response.standby_mission_ids) == sorted([overdue_active.id, overdue_planned.id])


def test_finish_day_leaves_unplanned_and_terminal_missions_untouched(db) -> None:
    user = _user(db)
    _open_day(db, user)
    unplanned_overdue = _mission(db, user, planned=False, deadline=PAST)
    done = _mission(db, user, status="completed", deadline=PAST)

    _finish(db, user)

    db.refresh(unplanned_overdue)
    db.refresh(done)
    assert unplanned_overdue.status == "backlog"
    assert done.status == "completed"


def test_finish_day_releases_annex_links_of_the_active_mission(db) -> None:
    user = _user(db)
    _open_day(db, user)
    carrier = _mission(db, user, status="active", minutes=300)
    annex = _mission(db, user, planned=False, minutes=10)
    attach_annexes(
        db,
        current_user=user,
        mission_id=carrier.id,
        payload=AttachAnnexesRequest(mission_ids=[annex.id]),
        idempotency_key=f"attach-{uuid4().hex}",
        request_method="POST",
        request_path="/x",
    )

    _finish(db, user)

    db.refresh(annex)
    assert annex.annex_of_mission_id is None and annex.status == "backlog"


# ---------- Sortie du standby ----------

def test_list_standby_missions_is_user_scoped(db) -> None:
    user, other = _user(db), _user(db)
    mine = _mission(db, user, status="standby", deadline=PAST, title="Renouveler la carte VTC")
    _mission(db, other, status="standby", deadline=PAST)

    listing = list_standby_missions(db, current_user=user)

    assert [m.id for m in listing.missions] == [mine.id]
    assert listing.intervention_required is True


def test_resolve_reschedule_returns_to_backlog_with_new_deadline(db) -> None:
    user = _user(db)
    mission = _mission(db, user, status="standby", deadline=PAST)

    _resolve(db, user, mission, decision="reschedule", deadline_at=FUTURE)

    db.refresh(mission)
    assert mission.status == "backlog" and mission.deadline_at == FUTURE


def test_resolve_reschedule_rejects_a_past_deadline(db) -> None:
    user = _user(db)
    mission = _mission(db, user, status="standby", deadline=PAST)
    with pytest.raises(MissionStateConflictError):
        _resolve(db, user, mission, decision="reschedule", deadline_at=PAST)


@pytest.mark.parametrize("decision", ["completed", "cancelled"])
def test_resolve_completed_or_cancelled_is_terminal(db, decision) -> None:
    user = _user(db)
    mission = _mission(db, user, status="standby", deadline=PAST)

    _resolve(db, user, mission, decision=decision)

    db.refresh(mission)
    assert mission.status == decision and mission.ended_at is not None
    assert list_standby_missions(db, current_user=user).intervention_required is False


def test_resolve_rejects_missions_not_in_standby(db) -> None:
    user = _user(db)
    mission = _mission(db, user, status="backlog")
    with pytest.raises(MissionStateConflictError):
        _resolve(db, user, mission, decision="completed")


def test_a_day_restarted_on_the_same_date_can_still_be_finished(db) -> None:
    user = _user(db)
    first = _open_day(db, user)
    done, _duplicate = _finish(db, user)
    second = _open_day(db, user)  # redémarrée le même jour : la date a déjà son bilan
    assert second.start_local_date == first.start_local_date
    again, _duplicate = finish_day(
        db, current_user=user,
        payload=FinishDayRequest(local_date=NOW.date(), timezone="Europe/Paris", day_status="partial", main_win="Mairie faite"),
        idempotency_key=f"finish-{uuid4().hex}", request_method="POST", request_path="/api/imperium/day/finish")
    assert again.review.id == done.review.id  # un seul bilan pour la date, complété
    assert (again.review.day_status, again.review.main_win) == ("partial", "Mairie faite")
    db.refresh(second)
    assert second.finished_at is not None and second.day_review_id == done.review.id
    with pytest.raises(NoOpenPlanningDayError):
        _finish(db, user)
