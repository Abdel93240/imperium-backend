"""PostgreSQL : semaine du WR du mardi au lundi (`wr.week_start_weekday` semé à 1), proposée le mardi dès 1 h."""
from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("WR week DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models.auth import User  # noqa: E402
from app.models.imperium import ImperiumWeeklyReviewState  # noqa: E402
from app.services.imperium import weekly_review_conversation as wrc  # noqa: E402
from app.services.imperium import weekly_review_state as wrs  # noqa: E402
from app.services.params import set_parameter  # noqa: E402
from app.services.wr import metrics  # noqa: E402

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
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"ww-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _paris(*args) -> datetime:
    return datetime(*args, tzinfo=PARIS).astimezone(UTC)


def test_the_week_runs_from_tuesday_and_is_offered_from_1_am(db) -> None:
    assert wrs.week_weekday(db) == 1
    # Mardi 27/10 à 0 h 30 : la semaine du 20 n'est pas encore finie, on propose encore celle du 13.
    assert wrs.reviewable_weeks(db, _paris(2026, 10, 27, 0, 30)) == [date(2026, 10, 13), date(2026, 10, 6)]
    # Dès 1 h : la semaine du mardi 20 au lundi 26 est à revoir.
    assert wrs.reviewable_weeks(db, _paris(2026, 10, 27, 1, 5)) == [date(2026, 10, 20), date(2026, 10, 13)]
    assert wrs.reviewable_weeks(db, _paris(2026, 11, 2, 23, 0))[0] == date(2026, 10, 20)  # lundi soir : toujours elle
    set_parameter(db, code="wr.week_start_weekday", value=0, origin="user", rationale_fr="Test.")
    assert wrs.reviewable_weeks(db, _paris(2026, 10, 27, 1, 5))[0] == date(2026, 10, 19)


def test_launch_refuses_a_week_that_does_not_start_on_tuesday(db) -> None:
    user = _user(db)
    with pytest.raises(wrc.InvalidWeekStartError, match="Tuesday"):
        wrc.launch_weekly_review_session(db, current_user=user, week_start=date(2026, 10, 19),
                                         idempotency_key=str(uuid4()), request_method="POST", request_path="/launch")
    session = wrc.get_or_create_weekly_review_session(db, current_user=user, week_start=date(2026, 10, 20))
    assert (session.week_start, session.week_end) == (date(2026, 10, 20), date(2026, 10, 26))


def test_week_ready_job_marks_the_ended_week_once(db, monkeypatch) -> None:
    user = _user(db)
    monkeypatch.setattr(metrics, "_job_user", lambda db: user)
    ctx = SimpleNamespace(db=db, items_in=None, items_out=None, detail=None)
    wrs.week_ready_job(ctx, SimpleNamespace(to_ts=_paris(2026, 10, 27, 1, 5)))
    state = db.scalar(select(ImperiumWeeklyReviewState).where(ImperiumWeeklyReviewState.user_id == user.id))
    assert (state.week_start, state.ready, state.launched) == (date(2026, 10, 20), True, False)
    assert ctx.detail == {"week_start": "2026-10-20", "marked_ready": True}
    wrs.week_ready_job(ctx, SimpleNamespace(to_ts=_paris(2026, 10, 27, 2, 5)))
    assert ctx.detail["marked_ready"] is False and ctx.items_out == 0
