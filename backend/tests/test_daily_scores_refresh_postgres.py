"""PostgreSQL : refresh du registre des scores (spec Daily §4.6, carte ACT-DLY-03)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("daily scores refresh DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import daily  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.imperium import ImperiumMission, ImperiumMissionScore  # noqa: E402
from app.schemas.imperium import StartMissionRequest  # noqa: E402
from app.services.daily import scores_refresh, scoring_settings  # noqa: E402
from app.services.imperium import decision_framework as df  # noqa: E402
from app.services.runner.engine import RunContext, Window  # noqa: E402


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    # Les jobs et le réglage committent : transaction externe annulée, rien ne fuit.
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
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"dsr-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _mission(db, user, *, days: int, status: str = "backlog", legacy: bool = False, domain: str = "finance"):
    deadline = datetime.now(UTC) + timedelta(days=days)
    mission = ImperiumMission(user_id=user.id, title=f"Mission J+{days}", domain=domain, status=status,
                              started_at=datetime.now(UTC),
                              deadline_at=deadline)
    db.add(mission)
    db.flush()
    request = StartMissionRequest(title=mission.title, domain=domain, deadline_at=deadline, impact="critical",
                                  mission_type="cat_b", dependency="some", recurrence="monthly")
    payload = df.build_mission_score_from_start_request(request, scales=df.load_scales(db))
    if legacy:
        payload["explanation"].pop("inputs")  # ligne écrite avant ACT-DLY-03
    score = ImperiumMissionScore(user_id=user.id, mission_id=mission.id, domain=payload["domain"],
                                 intrinsic_score=payload["intrinsic_score"],
                                 domain_coefficient=payload["domain_coefficient"],
                                 weighted_score=payload["weighted_score"], explanation=payload["explanation"],
                                 source=payload["source"])
    db.add(score)
    db.commit()
    return mission, score


def _age(db, mission, days: int) -> None:
    """La mission vieillit : son échéance se rapproche de `days` jours."""
    mission.deadline_at = mission.deadline_at - timedelta(days=days)
    db.commit()


def test_new_scores_keep_their_inputs(db) -> None:
    user = _user(db)
    _, score = _mission(db, user, days=20)
    assert score.explanation["inputs"] == {"impact": "critical", "mission_type": "cat_b", "dependency": "some",
                                           "recurrence": "monthly"}


def test_refresh_ages_deadlines_and_skips_closed_missions(db) -> None:
    user = _user(db)
    full_mission, full = _mission(db, user, days=20)  # A = 10
    legacy_mission, legacy = _mission(db, user, days=20, legacy=True)
    done_mission, done = _mission(db, user, days=20, status="completed")
    assert scores_refresh.refresh_scores(db, current_user=user).refreshed == 0  # rien n'a bougé
    for mission in (full_mission, legacy_mission, done_mission):
        _age(db, mission, 19)  # J+1 → A = 25
    stats = scores_refresh.refresh_scores(db, current_user=user)
    db.commit()
    assert (stats.scanned, stats.refreshed, stats.full, stats.deadline_only) == (2, 2, 1, 1)
    for score in (full, legacy):
        db.refresh(score)
        assert score.explanation["deadline_points"] == 25
        assert int(score.intrinsic_score) == 25 + 20 + 18 + 5 + 5
        assert int(score.weighted_score) == int(score.intrinsic_score) * 5  # finance en position 3
    db.refresh(done)
    assert done.explanation["deadline_points"] == 10  # mission terminée : registre figé


def test_scale_change_replays_full_rows_only(db) -> None:
    user = _user(db)
    _, full = _mission(db, user, days=20)
    _, legacy = _mission(db, user, days=20, legacy=True)
    before = int(full.intrinsic_score)
    scales = df.scale_parameter_values(df.load_scales(db))
    scales["df.impact_points"] = dict(scales["df.impact_points"], critical=28)
    scales["df.coefficient_by_position"] = {"1": 10, "2": 8, "3": 6, "4": 4}
    from app.services.params import set_parameter

    for code in ("df.impact_points", "df.coefficient_by_position"):
        set_parameter(db, code=code, value=scales[code], origin="user", rationale_fr="Test.")
    scores_refresh.refresh_scores(db, current_user=user)
    db.commit()
    db.refresh(full)
    db.refresh(legacy)
    assert int(full.intrinsic_score) == before + 8 and full.domain_coefficient == 6  # rejoué en entier
    assert int(legacy.intrinsic_score) == before and legacy.domain_coefficient == 6  # B-E stockés gardés
    assert int(full.weighted_score) == (before + 8) * 6


def test_settings_update_refreshes_the_registry(db, monkeypatch) -> None:
    monkeypatch.setattr(scoring_settings, "settings_enabled", lambda db: True)
    user = _user(db)
    _, score = _mission(db, user, days=20)
    app = FastAPI()
    app.include_router(daily.router, prefix="/api/daily")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    response = TestClient(app).put(
        "/api/daily/settings/scoring", headers={"Idempotency-Key": uuid4().hex},
        json={"changes": {"df.coefficient_by_position": {"1": 10, "2": 8, "3": 7, "4": 4}}, "reason_fr": "Finance."})
    assert response.status_code == 200
    db.refresh(score)
    assert (score.domain_coefficient, int(score.weighted_score)) == (7, int(score.intrinsic_score) * 7)


def test_jobs(db, monkeypatch) -> None:
    user = _user(db)
    monkeypatch.setattr("app.services.wr.metrics._job_user", lambda _db: user)
    mission, score = _mission(db, user, days=20)
    _age(db, mission, 19)
    ctx = RunContext(db=db, job=None, run_id=uuid4(), trigger="cron", trigger_ref=None)
    scores_refresh.scores_refresh_job(ctx, Window(from_ts=None, to_ts=datetime(2026, 11, 2, 4, 30, tzinfo=UTC)))
    assert ctx.detail == {"skipped": "not_refresh_hour"}  # 5 h 30 à Paris en hiver
    scores_refresh.scores_refresh_job(ctx, Window(from_ts=None, to_ts=datetime(2026, 11, 2, 5, 30, tzinfo=UTC)))
    assert (ctx.items_in, ctx.items_out) == (1, 1)
    start = RunContext(db=db, job=None, run_id=uuid4(), trigger="event", trigger_ref=None)
    scores_refresh.day_start_job(start, Window(from_ts=None, to_ts=None))
    assert start.detail["selection"] == "disabled" and start.items_out == 0
    jobs = db.execute(text("SELECT code, enabled, schedule, event_types FROM job_definitions "
                           "WHERE code IN ('daily.day_start', 'daily.scores_refresh') ORDER BY code")).all()
    assert [tuple(row) for row in jobs] == [("daily.day_start", False, None, ["planning.day.started"]),
                                            ("daily.scores_refresh", False, "30 4,5 * * *", None)]


def test_tuned_coefficients_are_accepted_by_the_database(db) -> None:
    user = _user(db)
    _, score = _mission(db, user, days=3)
    score.domain_coefficient = 12
    db.commit()
    db.execute(text("INSERT INTO imperium_user_priorities (id, user_id, domain, position, coefficient, is_active, "
                    "created_at, updated_at) VALUES (gen_random_uuid(), :u, 'finance', 1, 12, true, now(), now())"),
               {"u": user.id})
    db.commit()
    with pytest.raises(Exception):  # noqa: B017 - un coefficient nul reste refusé
        db.execute(text("UPDATE imperium_mission_scores SET domain_coefficient = 0 WHERE id = :id"), {"id": score.id})
