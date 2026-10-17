"""PostgreSQL : job runner imperium.rolling_replan (doc 43 §3.2)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("replan runner DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models.ai import AITask  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.imperium import ImperiumDailyPlan, PlanningDay, PlanningReplanEvent  # noqa: E402
from app.models.toolbox import JobDefinition  # noqa: E402
from app.schemas.imperium import ReplanRequestCreate, ReplanReviseRequest  # noqa: E402
from app.services.imperium import replan_runner  # noqa: E402
from app.services.imperium.replan import request_replan, revise_replan  # noqa: E402

T0 = datetime.now(UTC).replace(microsecond=0)


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
        {"id": str(user_id), "email": f"runner-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _setup(db, user):
    db.add(PlanningDay(user_id=user.id, started_at=T0 - timedelta(hours=4), start_local_date=date.today(),
                       timezone="Europe/Paris", felt_energy=3, idempotency_key=f"day-{uuid4().hex}"))
    later = (T0 + timedelta(hours=2)).isoformat()
    db.add(ImperiumDailyPlan(user_id=user.id, local_date=date.today(), timezone="Europe/Paris", plan_status="active",
                             generated_from={}, plan_blocks=[{"block_type": "mission", "title": "Démarches", "planned_start": later,
                                                              "planned_end": (T0 + timedelta(hours=3)).isoformat()}]))
    db.commit()
    created, _ = request_replan(db, current_user=user, payload=ReplanRequestCreate(reason_category="new_event", reason_detail="Le client a annulé."),
                                idempotency_key=f"r-{uuid4().hex}", request_method="POST", request_path="/x", now=T0)
    return created


def _run(db, call_model=None):
    ctx = SimpleNamespace(db=db, items_in=None, items_out=None, detail={})
    replan_runner.process_queued_replans(ctx, call_model=call_model, now=T0 + timedelta(seconds=5))
    db.commit()
    return ctx


def test_job_definition_is_seeded_as_event_subscription(db) -> None:
    job = db.scalar(select(JobDefinition).where(JobDefinition.code == "imperium.rolling_replan"))
    assert job is not None
    assert job.kind == "event_subscription"
    assert set(job.event_types) == {"planning.replan.requested", "planning.replan.revision_requested"}
    assert job.handler_ref == "app.services.imperium.replan_runner:rolling_replan_job"


def test_runner_attaches_a_deterministic_proposal(db) -> None:
    user = _user(db)
    created = _setup(db, user)

    ctx = _run(db)

    row = db.get(PlanningReplanEvent, created.id)
    task = db.get(AITask, created.ai_task_id)
    assert row.status == "proposed" and row.proposal_version == 1
    assert row.proposal[0]["change"] == "moved" and "30 min" in row.rationale
    assert task.status == "result_received" and task.completed_at is not None
    assert ctx.items_out >= 1


def test_runner_applies_revision_with_local_model(db) -> None:
    user = _user(db)
    created = _setup(db, user)
    _run(db)
    revise_replan(db, current_user=user, replan_id=created.id, payload=ReplanReviseRequest(message="Remets les démarches à l'heure."),
                  idempotency_key=f"rev-{uuid4().hex}")
    assert db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "planning.replan.revision_requested")) is not None

    _run(db, call_model=lambda prompt: {"blocks": [{"block_type": "mission", "title": "Démarches", "change": "unchanged"}], "rationale": "Remis à l'heure."})

    row = db.get(PlanningReplanEvent, created.id)
    assert row.status == "proposed" and row.proposal_version == 2 and row.rationale == "Remis à l'heure."


def test_runner_cancels_superseded_tasks(db) -> None:
    user = _user(db)
    created = _setup(db, user)
    row = db.get(PlanningReplanEvent, created.id)
    row.status = "cancelled"
    db.commit()

    _run(db)

    assert db.get(AITask, created.ai_task_id).status == "cancelled"
    assert db.get(PlanningReplanEvent, created.id).proposal is None


def test_runner_marks_request_failed_when_processing_breaks(db, monkeypatch) -> None:
    user = _user(db)
    created = _setup(db, user)

    def boom(*_args, **_kwargs):
        raise ValueError("bad plan data")

    monkeypatch.setattr(replan_runner, "build_deterministic_proposal", boom)
    _run(db)

    row = db.get(PlanningReplanEvent, created.id)
    task = db.get(AITask, created.ai_task_id)
    assert row.status == "failed" and row.resolved_at is not None
    assert task.status == "failed" and task.error_message == "bad plan data"
