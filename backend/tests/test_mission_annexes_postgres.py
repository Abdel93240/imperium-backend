"""PostgreSQL : missions annexes V1 allégées (doc 53 §3.1), estimated_minutes, failure_reason_code.

Requiert une base migrée (IMPERIUM_TEST_DATABASE_URL) ; skip local sinon, échec en CI.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("mission annex DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models.auth import User  # noqa: E402
from app.models.imperium import ImperiumMission  # noqa: E402
from app.schemas.imperium import AttachAnnexesRequest, CompleteMissionRequest, FailMissionRequest  # noqa: E402
from app.services.imperium.missions import (  # noqa: E402
    AnnexValidationError,
    attach_annexes,
    complete_mission,
    fail_mission,
    get_current_active_mission,
)


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
        {"id": str(user_id), "email": f"annex-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _mission(db: Session, user: User, *, status: str = "backlog", minutes: int | None = 10, title: str | None = None) -> ImperiumMission:
    mission = ImperiumMission(
        user_id=user.id,
        title=title or f"Mission {uuid4().hex[:6]}",
        status=status,
        estimated_minutes=minutes,
        started_at=datetime.now(UTC),
    )
    db.add(mission)
    db.commit()
    return mission


def _attach(db, user, carrier, annexes, key=None):
    return attach_annexes(
        db,
        current_user=user,
        mission_id=carrier.id,
        payload=AttachAnnexesRequest(mission_ids=[a.id for a in annexes]),
        idempotency_key=key or f"attach-{uuid4().hex}",
        request_method="POST",
        request_path=f"/imperium/missions/{carrier.id}/annexes",
    )


# ---------- Schéma ----------

def test_estimated_minutes_must_be_positive(db) -> None:
    user = _user(db)
    with pytest.raises(IntegrityError):
        _mission(db, user, minutes=0)


def test_failure_reason_code_is_constrained(db) -> None:
    user = _user(db)
    mission = _mission(db, user)
    mission.failure_reason_code = "lazy"
    with pytest.raises(IntegrityError):
        db.commit()


def test_mission_cannot_be_its_own_annex(db) -> None:
    user = _user(db)
    mission = _mission(db, user)
    mission.annex_of_mission_id = mission.id
    with pytest.raises(IntegrityError):
        db.commit()


# ---------- Accrochage ----------

def test_attach_links_short_backlog_missions_to_active_carrier(db) -> None:
    user = _user(db)
    carrier = _mission(db, user, status="active", minutes=300, title="Travail VTC")
    annexes = [_mission(db, user, minutes=m) for m in (5, 10, 15)]

    response, replayed = _attach(db, user, carrier, annexes)

    assert replayed is False
    assert sorted(str(a.id) for a in annexes) == sorted(str(x.id) for x in response.annexes)
    for annex in annexes:
        db.refresh(annex)
        assert annex.annex_of_mission_id == carrier.id
        assert annex.status == "backlog"


@pytest.mark.parametrize("minutes", [None, 16, 60])
def test_attach_rejects_missions_without_short_estimate(db, minutes) -> None:
    user = _user(db)
    carrier = _mission(db, user, status="active", minutes=300)
    long_one = _mission(db, user, minutes=minutes)
    with pytest.raises(AnnexValidationError):
        _attach(db, user, carrier, [long_one])


def test_attach_rejects_more_than_five_in_one_request() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AttachAnnexesRequest(mission_ids=[uuid4() for _ in range(6)])


def test_attach_caps_total_annexes_at_five(db) -> None:
    user = _user(db)
    carrier = _mission(db, user, status="active", minutes=300)
    _attach(db, user, carrier, [_mission(db, user) for _ in range(3)])
    with pytest.raises(AnnexValidationError):
        _attach(db, user, carrier, [_mission(db, user) for _ in range(3)])


def test_attach_rejects_non_backlog_or_already_attached_or_self(db) -> None:
    user = _user(db)
    carrier = _mission(db, user, status="active", minutes=300)
    other_carrier = _mission(db, user, status="backlog", minutes=120)
    done = _mission(db, user, status="completed")
    taken = _mission(db, user)
    _attach(db, user, other_carrier, [taken])
    for bad in ([done], [taken], [carrier]):
        with pytest.raises(AnnexValidationError):
            _attach(db, user, carrier, bad)


def test_attach_rejects_annex_of_another_user(db) -> None:
    user, stranger = _user(db), _user(db)
    carrier = _mission(db, user, status="active", minutes=300)
    with pytest.raises(AnnexValidationError):
        _attach(db, user, carrier, [_mission(db, stranger)])


def test_active_mission_read_lists_annexes(db) -> None:
    user = _user(db)
    carrier = _mission(db, user, status="active", minutes=300, title="Travail VTC")
    annex = _mission(db, user, minutes=10, title="Appeler Yacine")
    _attach(db, user, carrier, [annex])

    read = get_current_active_mission(db, current_user=user)

    assert read.mission.estimated_minutes == 300
    assert [(a.title, a.estimated_minutes) for a in read.mission.annexes] == [("Appeler Yacine", 10)]


# ---------- Complétion / échec ----------

def test_complete_carrier_completes_checked_annexes_and_releases_others(db) -> None:
    user = _user(db)
    carrier = _mission(db, user, status="active", minutes=300)
    done_annex, skipped = _mission(db, user), _mission(db, user)
    _attach(db, user, carrier, [done_annex, skipped])

    response, _ = complete_mission(
        db,
        current_user=user,
        mission_id=carrier.id,
        payload=CompleteMissionRequest(outcome="completed", completed_annex_mission_ids=[done_annex.id]),
        idempotency_key=f"complete-{uuid4().hex}",
        request_method="POST",
        request_path=f"/imperium/missions/{carrier.id}/complete",
    )

    db.refresh(done_annex)
    db.refresh(skipped)
    assert response.completed_annex_mission_ids == [done_annex.id]
    assert done_annex.status == "completed" and done_annex.ended_at is not None
    assert done_annex.annex_of_mission_id == carrier.id  # trace de la mission porteuse
    assert skipped.status == "backlog" and skipped.annex_of_mission_id is None


def test_complete_rejects_ids_that_are_not_annexes_of_this_mission(db) -> None:
    user = _user(db)
    carrier = _mission(db, user, status="active", minutes=300)
    stranger = _mission(db, user)
    with pytest.raises(AnnexValidationError):
        complete_mission(
            db,
            current_user=user,
            mission_id=carrier.id,
            payload=CompleteMissionRequest(outcome="completed", completed_annex_mission_ids=[stranger.id]),
            idempotency_key=f"complete-{uuid4().hex}",
            request_method="POST",
            request_path="/x",
        )
    db.rollback()
    db.refresh(carrier)
    assert carrier.status == "active"


def test_fail_carrier_releases_all_annexes_without_penalty(db) -> None:
    user = _user(db)
    carrier = _mission(db, user, status="active", minutes=300)
    annexes = [_mission(db, user), _mission(db, user)]
    _attach(db, user, carrier, annexes)

    fail_mission(
        db,
        current_user=user,
        mission_id=carrier.id,
        payload=FailMissionRequest(failure_reason_code="too_tired"),
        idempotency_key=f"fail-{uuid4().hex}",
        request_method="POST",
        request_path="/x",
    )

    for annex in annexes:
        db.refresh(annex)
        assert annex.status == "backlog" and annex.annex_of_mission_id is None
    db.refresh(carrier)
    assert carrier.failure_reason_code == "too_tired"
    assert db.scalar(select(ImperiumMission.status).where(ImperiumMission.id == carrier.id)) == "failed"
