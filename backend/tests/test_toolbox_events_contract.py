"""§13.6 events: filled envelope on a declared flow, NOTIFY delivered,
heartbeat consumes through the cursor contract, 30-day rename compat."""

from __future__ import annotations

import time
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text

from _postgres import require_test_database_url

pytest.importorskip("psycopg")

from sqlalchemy.orm import Session  # noqa: E402

from app.models import ai, auth, event, idempotency, imperium, path, toolbox, vault  # noqa: E402,F401
from app.models.event import Event  # noqa: E402
from app.models.toolbox import JobCursor, JobDefinition  # noqa: E402
from app.services.events.emitter import build_event  # noqa: E402
from app.services.events.nomenclature import (  # noqa: E402
    READ_COMPAT_UNTIL,
    RENAMES,
    canonical_event_type,
    expand_for_read,
)
from app.services.runner.engine import execute_job  # noqa: E402


@pytest.fixture(scope="module")
def engine():
    engine = create_engine(require_test_database_url("toolbox events tests"), future=True)
    yield engine
    engine.dispose()


@pytest.fixture()
def user_id(engine):
    user_id = uuid4()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                "VALUES (:id, :email, FALSE, now(), now())"
            ),
            {"id": str(user_id), "email": f"toolbox-events-{user_id}@example.test"},
        )
    return user_id


def test_declared_replan_flow_fills_causation_correlation_and_depth(engine, user_id) -> None:
    # Declared chain: plan generated (root) → cancelled with reason → replanned.
    with Session(engine) as db:
        root = build_event(
            db,
            user_id=user_id,
            event_type="day.plan.created",  # legacy name: canonicalised at emission
            payload={"plan_id": "p-1"},
            idempotency_key=f"idem-{uuid4().hex}",
        )
        db.add(root)
        db.commit()
        assert root.event_type == "planning.daily_plan.generated"
        assert root.depth == 1
        assert root.causation_id is None

        cancelled = build_event(
            db,
            user_id=user_id,
            event_type="planning.daily_plan.replanned",
            payload={"plan_id": "p-1", "reason": "fatigue", "trigger": "cancelled"},
            idempotency_key=f"idem-{uuid4().hex}",
            causation_id=root.event_id,
        )
        db.add(cancelled)
        db.commit()
        assert cancelled.depth == 2
        assert cancelled.correlation_id == root.correlation_id  # same dossier

        replanned = build_event(
            db,
            user_id=user_id,
            event_type="planning.daily_plan.replanned",
            payload={"plan_id": "p-2", "reason": "fatigue", "trigger": "replan"},
            idempotency_key=f"idem-{uuid4().hex}",
            causation_id=cancelled.event_id,
        )
        db.add(replanned)
        db.commit()
        assert replanned.depth == 3
        assert replanned.correlation_id == root.correlation_id


def test_pg_notify_events_new_is_delivered_on_insert(engine, user_id) -> None:
    import psycopg

    url = require_test_database_url("events NOTIFY test").replace("+psycopg", "")
    with psycopg.connect(url, autocommit=True) as listener:
        listener.execute("LISTEN events_new")
        with Session(engine) as db:
            event = build_event(
                db,
                user_id=user_id,
                event_type="planning.day.finished",
                payload={},
                idempotency_key=f"idem-{uuid4().hex}",
            )
            db.add(event)
            db.commit()
            event_pk = str(event.id)
        deadline = time.monotonic() + 5
        payloads = []
        while time.monotonic() < deadline and not payloads:
            payloads = [n.payload for n in listener.notifies(timeout=1.0, stop_after=1)]
        assert event_pk in payloads


def test_heartbeat_consumes_events_and_advances_cursor(engine, user_id, monkeypatch) -> None:
    from types import SimpleNamespace

    from app.services.runner import engine as engine_module

    monkeypatch.setattr(
        engine_module, "get_settings", lambda: SimpleNamespace(runner_enabled=True)
    )
    with Session(engine) as db:
        for _ in range(3):
            db.add(
                build_event(
                    db,
                    user_id=user_id,
                    event_type="finance.transaction.created",
                    payload={},
                    idempotency_key=f"idem-{uuid4().hex}",
                )
            )
        db.commit()

        job = db.scalar(
            select(JobDefinition).where(JobDefinition.code == "system.events_heartbeat")
        )
        original_enabled = job.enabled
        job.enabled = True
        db.commit()
        try:
            run = execute_job(db, job_code="system.events_heartbeat", trigger="manual")
            assert run.status == "completed"
            assert run.detail["counts_by_type"]["finance.transaction.created"] >= 3
            assert run.items_in >= 3
            cursor = db.get(JobCursor, "system.events_heartbeat")
            assert cursor is not None  # the journal finally has a reader

            # Second run over an empty window: cursor moves, no double count.
            run_2 = execute_job(db, job_code="system.events_heartbeat", trigger="manual")
            assert run_2.status == "completed"
            assert run_2.detail["counts_by_type"].get("finance.transaction.created", 0) == 0
        finally:
            db.expire_all()
            job = db.scalar(
                select(JobDefinition).where(JobDefinition.code == "system.events_heartbeat")
            )
            job.enabled = original_enabled
            db.commit()


def test_rename_table_and_read_compat_30_days() -> None:
    # DV-11: path.* stays canonical (worship.* non-retained).
    assert canonical_event_type("path.item.completed") == "path.item.completed"
    assert canonical_event_type("path.ghusl.required") == "path.ghusl.required"
    # Doc 77 renames applied, E1 resolves the double emitter.
    assert canonical_event_type("vault.transaction.created") == "finance.transaction.created"
    assert canonical_event_type("mission.failed") == "planning.mission.aborted"
    assert canonical_event_type("mission.abandoned") == "planning.mission.aborted"
    assert canonical_event_type("day.finished") == "planning.day.finished"
    assert canonical_event_type("priority.rules.updated") == "decision.priorities.updated"
    assert "path.item.created" not in RENAMES

    # Inside the window both names match a reader filter.
    today = date(2026, 7, 20)
    assert today <= READ_COMPAT_UNTIL
    expanded = expand_for_read(["finance.transaction.created"], today=today)
    assert set(expanded) == {"finance.transaction.created", "vault.transaction.created"}
    expanded_from_old = expand_for_read(["mission.failed"], today=today)
    assert "planning.mission.aborted" in expanded_from_old

    # After the window: canonical only.
    after = date(2026, 8, 15)
    assert expand_for_read(["finance.transaction.created"], today=after) == [
        "finance.transaction.created"
    ]


def test_ingestion_completes_envelope_from_declared_cause(engine, user_id) -> None:
    from app.models.auth import User
    from app.schemas.events import EventEnvelope
    from app.services.events.ingestion import ingest_event

    with Session(engine) as db:
        current_user = db.get(User, user_id)
        parent_envelope = EventEnvelope(
            event_id=f"evt_{uuid4().hex}",
            event_type="path.item.created",
            schema_version="1.0",
            occurred_at=datetime.now(UTC),
            source_app="imperium",
            user_id=user_id,
            idempotency_key=f"idem-{uuid4().hex}",
            privacy_level="medium",
            payload={"item_id": "i-1"},
        )
        ingest_event(
            db,
            envelope=parent_envelope,
            current_user=current_user,
            request_method="POST",
            request_path="/api/events",
        )
        child_envelope = EventEnvelope(
            event_id=f"evt_{uuid4().hex}",
            event_type="path.item.completed",
            schema_version="1.0",
            occurred_at=datetime.now(UTC),
            source_app="imperium",
            user_id=user_id,
            idempotency_key=f"idem-{uuid4().hex}",
            causation_id=parent_envelope.event_id,
            privacy_level="medium",
            payload={"item_id": "i-1"},
        )
        ingest_event(
            db,
            envelope=child_envelope,
            current_user=current_user,
            request_method="POST",
            request_path="/api/events",
        )
        parent = db.scalar(select(Event).where(Event.event_id == parent_envelope.event_id))
        child = db.scalar(select(Event).where(Event.event_id == child_envelope.event_id))
        assert parent.depth == 1
        assert child.depth == 2
        assert child.correlation_id == parent.correlation_id
