"""PostgreSQL : métriques hebdomadaires du WR et politique de saut (spec WR §3.8, §7, §14.6)."""
from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("wr metrics DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import wr  # noqa: E402
from app.models import ai  # noqa: E402,F401 - FK de la session WR vers ai_tasks
from app.models.auth import User  # noqa: E402
from app.models.imperium import ImperiumWeeklyReviewSession  # noqa: E402
from app.models.wr import WrMetricsWeekly  # noqa: E402
from app.schemas.wr import DocketDecisionRequest  # noqa: E402
from app.services.wr import docket, metrics  # noqa: E402

PARIS = ZoneInfo("Europe/Paris")
WEEK = date(2026, 9, 7)  # un lundi


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
        {"id": str(user_id), "email": f"wrmetrics-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _at(day: date, hour: int = 12) -> datetime:
    return datetime.combine(day, time(hour), tzinfo=PARIS).astimezone(UTC)


def _item(db, user, *, when: datetime, item_type: str = "anomaly"):
    item = docket.create_item(db, current_user=user, item_type=item_type, domain="vault", title_fr="Point",
                              payload={}, evidence_refs={}, impact_estimate=3, source_worker="w4", now=when)
    db.commit()
    return item


def _decide(db, user, item, decision: str, when: datetime) -> None:
    docket.decide(db, current_user=user, item_id=item.id, request=DocketDecisionRequest(decision=decision),
                  idempotency_key=uuid4().hex, request_path="/x", now=when)


def test_week_counts_docket_activity_inside_the_paris_window(db) -> None:
    user = _user(db)
    monday = _at(WEEK, 0)  # 00:00 Paris = dimanche 22:00 UTC, dans la semaine
    a = _item(db, user, when=monday)
    b = _item(db, user, when=_at(WEEK + timedelta(days=2)), item_type="chain_proposal")
    c = _item(db, user, when=_at(WEEK + timedelta(days=3)), item_type="pattern_new")
    d = _item(db, user, when=_at(WEEK + timedelta(days=3)), item_type="pattern_contradiction")
    _item(db, user, when=_at(WEEK + timedelta(days=7)))  # semaine suivante
    _decide(db, user, a, "validated", _at(WEEK + timedelta(days=4)))
    _decide(db, user, b, "refused", _at(WEEK + timedelta(days=4)))
    for offset in (4, 5, 6):
        _decide(db, user, c, "deferred", _at(WEEK + timedelta(days=offset)))  # 3e report → forcé
    _decide(db, user, d, "deferred", _at(WEEK + timedelta(days=8)))  # hors fenêtre
    db.commit()
    row = metrics.compute_week(db, current_user=user, week_start=WEEK, now=_at(WEEK + timedelta(days=9)))
    assert (row.docket_created, row.docket_validated, row.docket_refused, row.docket_deferred,
            row.docket_forced_decisions) == (4, 1, 1, 3, 1)
    assert (row.chain_proposals, row.patterns_new, row.contradictions) == (1, 1, 1)
    assert (row.factory_runs, row.events_processed, row.patterns_reinforced) == (0, None, None)
    assert row.wr_mode is None  # fenêtre du WR pas encore close : ni tenu ni sauté


def test_skip_policy_and_duration(db) -> None:
    user = _user(db)
    late = _at(WEEK + timedelta(days=14))
    assert metrics.compute_week(db, current_user=user, week_start=WEEK, now=late).wr_mode == "skipped"
    session = ImperiumWeeklyReviewSession(
        user_id=user.id, week_start=WEEK, week_end=WEEK + timedelta(days=6), status="stored",
        launched_at=_at(WEEK + timedelta(days=8), 20), completed_at=_at(WEEK + timedelta(days=8), 21) - timedelta(minutes=20),
    )
    db.add(session)
    db.commit()
    held = metrics.compute_week(db, current_user=user, week_start=WEEK, now=late)
    assert (held.wr_mode, held.wr_duration_min) == ("full", 40)
    # Un WR lancé avant la clôture de la fenêtre compte dès qu'il existe.
    assert metrics.compute_week(db, current_user=user, week_start=WEEK, now=_at(WEEK + timedelta(days=9))).wr_mode == "full"
    with pytest.raises(ValueError):
        metrics.compute_week(db, current_user=user, week_start=WEEK + timedelta(days=1))


def test_rollup_job_upserts_the_two_last_weeks(db, monkeypatch) -> None:
    user = _user(db)
    monkeypatch.setattr(metrics, "_job_user", lambda _db: user)
    _item(db, user, when=_at(WEEK + timedelta(days=1)))
    from app.services.runner.engine import RunContext, Window

    now = _at(WEEK + timedelta(days=15))  # mardi de la semaine W+2
    ctx = RunContext(db=db, job=None, run_id=uuid4(), trigger="manual", trigger_ref=None)
    metrics.metrics_rollup_job(ctx, Window(from_ts=None, to_ts=now))
    rows = db.scalars(select(WrMetricsWeekly).where(WrMetricsWeekly.user_id == user.id)
                      .order_by(WrMetricsWeekly.week_start)).all()
    assert [(row.week_start, row.docket_created, row.wr_mode) for row in rows] == [
        (WEEK, 1, "skipped"), (WEEK + timedelta(days=7), 0, None),
    ]
    assert (ctx.items_out, ctx.cursor_ts) == (2, now)
    _item(db, user, when=_at(WEEK + timedelta(days=2)))
    metrics.metrics_rollup_job(ctx, Window(from_ts=None, to_ts=now))
    db.expire_all()
    assert db.scalar(select(WrMetricsWeekly.docket_created).where(
        WrMetricsWeekly.user_id == user.id, WrMetricsWeekly.week_start == WEEK)) == 2  # recalcul, pas de doublon


def test_metrics_route_is_read_only(db) -> None:
    user = _user(db)
    app = FastAPI()
    app.include_router(wr.router, prefix="/api/wr")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    body = client.get("/api/wr/metrics/weekly", params={"weeks": 3}).json()
    assert len(body["weeks"]) == 3
    starts = [date.fromisoformat(row["week_start"]) for row in body["weeks"]]
    assert all(start.weekday() == 0 for start in starts) and starts == sorted(starts, reverse=True)
    assert db.scalar(select(WrMetricsWeekly).where(WrMetricsWeekly.user_id == user.id)) is None
    assert client.get("/api/wr/metrics/weekly", params={"weeks": 0}).status_code == 422
