"""PostgreSQL : replanification de la journée (doc 43 §3.2–§3.4, doc 59 §12.6).

Circuit : demande (raison + détails, délai serveur) → tâche IA imperium.rolling_replan
→ proposition déposée par le runner → corrections (sans nouveau délai) → accepter
(applique au plan du jour, version +1) ou annuler (plan inchangé).
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("replan DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models.ai import AITask  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.imperium import ImperiumDailyPlan, PlanningDay, PlanningReplanEvent  # noqa: E402
from app.schemas.imperium import (  # noqa: E402
    ReplanProposalAttachRequest,
    ReplanRequestCreate,
    ReplanReviseRequest,
)
from app.services.imperium.replan import (  # noqa: E402
    REPLAN_DEBOUNCE_MINUTES,
    ReplanCooldownError,
    ReplanStateConflictError,
    accept_replan,
    attach_replan_proposal,
    cancel_replan,
    get_replan_state,
    request_hook_replan,
    request_replan,
    revise_replan,
)

T0 = datetime(2026, 10, 17, 7, 24, tzinfo=UTC)
BLOCKS = [
    {"block_type": "mission", "title": "Travail VTC", "planned_start": "2026-10-17T07:00:00+00:00", "change": "unchanged"},
    {"block_type": "mission", "title": "Pause récupération", "planned_start": "2026-10-17T13:25:00+00:00", "change": "new"},
    {"block_type": "mission", "title": "Lecture", "planned_start": "2026-10-17T20:30:00+00:00", "change": "removed"},
]


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
        {"id": str(user_id), "email": f"replan-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _day_with_plan(db, user) -> ImperiumDailyPlan:
    db.add(PlanningDay(user_id=user.id, started_at=T0 - timedelta(hours=4), start_local_date=date(2026, 10, 17),
                       timezone="Europe/Paris", felt_energy=3, idempotency_key=f"day-{uuid4().hex}"))
    plan = ImperiumDailyPlan(user_id=user.id, local_date=date(2026, 10, 17), timezone="Europe/Paris", plan_status="active",
                             generated_from={}, plan_blocks=[{"block_type": "mission", "title": "Lecture"}])
    db.add(plan)
    db.commit()
    return plan


def _request(db, user, *, now=T0, category="fatigue", detail="Longue nuit, je dois alléger l'après-midi."):
    return request_replan(
        db, current_user=user, payload=ReplanRequestCreate(reason_category=category, reason_detail=detail),
        idempotency_key=f"replan-{uuid4().hex}", request_method="POST", request_path="/api/imperium/day/replan", now=now,
    )


def _attach(db, request_id, blocks=BLOCKS, rationale="Je décale l'après-midi et retire la lecture."):
    return attach_replan_proposal(
        db, request_id=request_id, payload=ReplanProposalAttachRequest(blocks=blocks, rationale=rationale),
        idempotency_key=f"attach-{uuid4().hex}",
    )


def test_manual_request_requires_category_and_details_in_db(db) -> None:
    user = _user(db)
    db.add(PlanningReplanEvent(user_id=user.id, trigger="manual", status="requested", reason_category=None,
                               reason_detail=None, requested_at=T0, idempotency_key=f"k-{uuid4().hex}"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_request_queues_rolling_replan_ai_task_and_event(db) -> None:
    user = _user(db)
    _day_with_plan(db, user)

    response, replayed = _request(db, user)

    assert replayed is False and response.status == "requested"
    task = db.get(AITask, response.ai_task_id)
    assert task.task_type == "imperium.rolling_replan" and task.status == "queued"
    assert task.input_payload["reason_category"] == "fatigue"
    assert task.input_payload["replan_event_id"] == str(response.id)
    assert db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "planning.replan.requested")) is not None


def test_request_requires_an_open_operational_day(db) -> None:
    user = _user(db)
    with pytest.raises(ReplanStateConflictError):
        _request(db, user)


def test_debounce_blocks_a_second_manual_request_within_five_minutes(db) -> None:
    user = _user(db)
    _day_with_plan(db, user)
    first, _ = _request(db, user)
    cancel_replan(db, current_user=user, replan_id=first.id, now=T0 + timedelta(minutes=1))

    with pytest.raises(ReplanCooldownError) as err:
        _request(db, user, now=T0 + timedelta(minutes=3))
    assert err.value.eligible_at == T0 + timedelta(minutes=REPLAN_DEBOUNCE_MINUTES)

    state = get_replan_state(db, current_user=user, now=T0 + timedelta(minutes=3))
    assert state.eligible_at == T0 + timedelta(minutes=5) and state.can_request is False
    second, _ = _request(db, user, now=T0 + timedelta(minutes=5, seconds=1))
    assert second.status == "requested"


def test_only_one_open_request_at_a_time(db) -> None:
    user = _user(db)
    _day_with_plan(db, user)
    _request(db, user)
    with pytest.raises(ReplanStateConflictError):
        _request(db, user, now=T0 + timedelta(minutes=10))


def test_hook_exceptions_bypass_the_debounce(db) -> None:
    user = _user(db)
    _day_with_plan(db, user)
    first, _ = _request(db, user)
    cancel_replan(db, current_user=user, replan_id=first.id, now=T0)

    hooked = request_hook_replan(db, current_user=user, hook_type="ghusl_required", now=T0 + timedelta(minutes=1))
    assert hooked.status == "requested" and hooked.trigger == "hook"
    cancel_replan(db, current_user=user, replan_id=hooked.id, now=T0 + timedelta(minutes=1))
    with pytest.raises(ReplanCooldownError):
        request_hook_replan(db, current_user=user, hook_type="pulse.workout.skipped", now=T0 + timedelta(minutes=2))


def test_attach_proposal_then_revise_keeps_debounce_untouched(db) -> None:
    user = _user(db)
    _day_with_plan(db, user)
    created, _ = _request(db, user)

    proposed = _attach(db, created.id)
    assert proposed.status == "proposed" and proposed.proposal_version == 1
    assert [b["change"] for b in proposed.proposal] == ["unchanged", "new", "removed"]

    revised = revise_replan(db, current_user=user, replan_id=created.id, payload=ReplanReviseRequest(message="Garde la lecture ce soir."),
                            idempotency_key=f"rev-{uuid4().hex}", now=T0 + timedelta(minutes=2))
    assert revised.status == "revising"
    task = db.get(AITask, revised.ai_task_id)
    assert task.input_payload["correction"] == "Garde la lecture ce soir."
    second = _attach(db, created.id, blocks=BLOCKS[:2])
    assert second.status == "proposed" and second.proposal_version == 2
    # La correction ne compte pas comme une nouvelle replanification.
    assert get_replan_state(db, current_user=user, now=T0 + timedelta(minutes=2)).eligible_at == T0 + timedelta(minutes=5)


def test_accept_applies_proposal_to_daily_plan_and_emits_replanned(db) -> None:
    user = _user(db)
    plan = _day_with_plan(db, user)
    created, _ = _request(db, user)
    _attach(db, created.id)

    accepted = accept_replan(db, current_user=user, replan_id=created.id, now=T0 + timedelta(minutes=1))

    db.refresh(plan)
    assert accepted.status == "accepted"
    assert [b["title"] for b in plan.plan_blocks] == ["Travail VTC", "Pause récupération"]  # « removed » exclue
    assert plan.generated_from["replan_version"] == 1
    event = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "planning.daily_plan.replanned"))
    assert event.payload["reason"] == "fatigue" and event.payload["trigger"] == "manual"


def test_cancel_keeps_the_previous_plan(db) -> None:
    user = _user(db)
    plan = _day_with_plan(db, user)
    created, _ = _request(db, user)
    _attach(db, created.id)

    cancelled = cancel_replan(db, current_user=user, replan_id=created.id, now=T0 + timedelta(minutes=1))

    db.refresh(plan)
    assert cancelled.status == "cancelled"
    assert plan.plan_blocks == [{"block_type": "mission", "title": "Lecture"}]


def test_accept_requires_a_proposal(db) -> None:
    user = _user(db)
    _day_with_plan(db, user)
    created, _ = _request(db, user)
    with pytest.raises(ReplanStateConflictError):
        accept_replan(db, current_user=user, replan_id=created.id, now=T0)


def test_request_is_idempotent(db) -> None:
    user = _user(db)
    _day_with_plan(db, user)
    payload = ReplanRequestCreate(reason_category="new_event", reason_detail="Le client a annulé.")
    kwargs = dict(current_user=user, payload=payload, idempotency_key="same-key", request_method="POST", request_path="/api/imperium/day/replan", now=T0)
    first, _ = request_replan(db, **kwargs)
    again, replayed = request_replan(db, **kwargs)
    assert replayed is True and again.id == first.id
