"""PostgreSQL : cycle quotidien de Pulse (bloc 2) — semaine de repas le mardi, révision du programme, revue,
règles médicales proposées après une prise de sang, objectif d'eau personnalisé."""
from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("pulse cycle DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models.ai import KnowledgeInboxItem  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.imperium import PulseMedicalRule, PulseWorkout  # noqa: E402
from app.models.pulse import PulseDietPlan, PulseLabResult, PulseProgram, PulseProgramRequest, PulseShoppingItem  # noqa: E402
from app.models.wr import WrDocketItem  # noqa: E402
from app.services.params import set_parameter  # noqa: E402
from app.services.pulse import cycle, health_consent, hydration, program_design  # noqa: E402
from app.services.pulse.expiry import PARIS  # noqa: E402


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


@pytest.fixture()
def flags(db):
    for code in ("pulse.diet_enabled", "pulse.programs_enabled"):
        set_parameter(db, code=code, value=True, origin="user", rationale_fr="Test.")
    db.commit()
    yield
    for code in ("pulse.diet_enabled", "pulse.programs_enabled"):
        set_parameter(db, code=code, value=False, origin="user", rationale_fr="Test.")
    db.commit()


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"cyc-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _next(weekday: int) -> date:
    today = datetime.now(PARIS).date()
    return today + timedelta(days=(weekday - today.weekday()) % 7 or 7)


def _at(day: date) -> datetime:
    return datetime.combine(day, time(6, 5), tzinfo=PARIS)


def test_tuesday_requests_seven_days_of_meals_once(db, flags):
    user = _user(db)
    wednesday = _next(2)
    assert cycle.run(db, user, _at(wednesday)).get("diet_requested") is None  # pas le jour de la revue
    tuesday = _next(1)
    assert cycle.run(db, user, _at(tuesday))["diet_requested"] == 1
    plan = db.scalar(select(PulseDietPlan).where(PulseDietPlan.user_id == user.id))
    assert (plan.week_start, plan.status) == (tuesday, "generating")
    assert cycle.run(db, user, _at(tuesday))["diet_requested"] == 0


def _design(hydration_target=None) -> dict:
    exercise = {"name": "Pompes", "muscle_group": "chest", "sets": 3, "reps": 10, "duration_seconds": None,
                "rest_seconds": 60, "equipment": [], "notes": "Gainage."}
    return {"name": "Force", "phase": "fondations", "weeks_total": 4, "progression_fr": "+1", "recovery_fr": "48 h.",
            "rationale_fr": "Sert l'objectif 1.", "hydration": hydration_target,
            "sessions": [{"weekday": "MO", "title": "Haut du corps", "session_type": "strength", "duration_minutes": 30,
                          "intensity": "medium", "systemic_load": 5, "exercises": [exercise]}]}


def test_program_revision_after_four_weeks_carries_the_real_record(db, flags):
    user = _user(db)
    from app.schemas.pulse_training import ProgramRequestCreate
    first, _ = program_design.request(db, current_user=user, idempotency_key="p", payload=ProgramRequestCreate(
        goal="Force", level="beginner", days=["MO"], session_minutes=40, preferred_time="18:00"))
    target = {"min_ml": 1800, "good_ml": 2300, "very_good_ml": 2800, "rationale_fr": "Chaleur au volant."}
    program_design.generate(db, first.id, call=lambda s, p, sc: (_design(target), "cloud", {}))
    accepted = program_design.accept(db, current_user=user, request_id=first.id)
    program = db.get(PulseProgram, accepted.program_id)
    assert program.hydration_target["good_ml"] == 2300
    day = hydration.day_view(db, current_user=user, day=datetime.now(PARIS).date())
    assert day.target["very_good_ml"] == 2800 and day.target_message is None

    assert cycle.run(db, user, datetime.now(UTC))["revision_requested"] == 0  # pas encore dû
    program.created_at = datetime.now(UTC) - timedelta(days=30)
    db.add(PulseWorkout(user_id=user.id, title="Haut du corps", status="skipped", skip_reason="fatigue",
                        planned_at=datetime.now(UTC) - timedelta(days=3), program_id=program.id,
                        idempotency_key=uuid4().hex, request_hash="h"))
    db.commit()
    assert cycle.run(db, user, datetime.now(UTC))["revision_requested"] == 1
    revision = db.scalar(select(PulseProgramRequest).where(PulseProgramRequest.user_id == user.id,
                                                           PulseProgramRequest.kind == "revision"))
    assert revision.status == "generating" and "sautées : 1 (raisons : fatigue)" in revision.inputs["revision"]
    prompts = []
    program_design.generate(db, revision.id, call=lambda s, p, sc: (prompts.append(p), (_design(), "cloud", {}))[1])
    assert "## Révision du programme en cours" in prompts[0]
    assert cycle.run(db, user, datetime.now(UTC))["revision_requested"] == 0  # une proposition attend déjà


def test_tuesday_deposits_review_items_once(db, flags):
    user = _user(db)
    tuesday = _next(1)
    old = [PulseDietPlan(user_id=user.id, week_start=tuesday - timedelta(days=7 * k), status="superseded",
                         idempotency_key=uuid4().hex, request_hash="h") for k in (2, 3)]
    db.add_all(old)
    db.flush()
    for plan in old:
        db.add(PulseShoppingItem(user_id=user.id, plan_id=plan.id, name="Brocolis", quantity=Decimal(500), unit="g",
                                 status="removed", created_at=_at(tuesday) - timedelta(days=10)))
    for status in ("completed", "skipped", "skipped"):
        db.add(PulseWorkout(user_id=user.id, title="Séance", status=status, skip_reason="pas le temps" if status == "skipped" else None,
                            planned_at=_at(tuesday) - timedelta(days=2), program_id=None,
                            idempotency_key=uuid4().hex, request_hash="h"))
    db.commit()
    db.execute(text("UPDATE pulse_workouts SET program_id = NULL WHERE user_id = :u"), {"u": user.id})
    program = PulseProgram(id=uuid4(), user_id=user.id, name="P", objective_weights={},
                           mesocycle={"phase": "x", "week_current": 1, "weeks_total": 4}, status="active", version=1,
                           idempotency_key="k", request_hash="h")
    db.add(program)
    db.flush()
    db.execute(text("UPDATE pulse_workouts SET program_id = :p WHERE user_id = :u"), {"p": program.id, "u": user.id})
    db.commit()
    assert cycle.run(db, user, _at(tuesday))["docket_items"] == 2
    items = {i.item_type: i for i in db.scalars(select(WrDocketItem).where(WrDocketItem.user_id == user.id))}
    assert "Brocolis" in items["user_question"].title_fr and items["user_question"].domain == "pulse"
    assert items["anomaly"].title_fr == "Sport : 1 séance faite sur 3 cette semaine"
    assert items["anomaly"].payload["skip_reasons"] == ["pas le temps"]
    assert cycle.run(db, user, _at(tuesday))["docket_items"] == 0


def test_lab_rules_are_proposed_never_activated(db):
    user = _user(db)
    health_consent.grant(db, current_user=user, domain="medical", text_version=health_consent.TEXT_VERSION)
    item = KnowledgeInboxItem(user_id=user.id, title="Bilan", entry_app="pulse", status="validated", destination="lab_results",
                              extraction_final={"lab_results": []})
    db.add(item)
    db.flush()
    db.add(PulseLabResult(user_id=user.id, inbox_item_id=item.id, analyte="Ferritine", analyte_key="ferritine",
                          value=Decimal(12), unit="µg/L", ref_low=Decimal(30), ref_high=Decimal(400),
                          measured_on=date(2026, 9, 12), source="inbox"))
    db.commit()
    assert cycle.propose_lab_rules(db, user, call=lambda s, p, sc: None) == 0  # aucun cerveau : attend
    db.refresh(item)
    assert not item.extraction_final.get("rules_checked")
    prompts = []
    rules = {"rules": [{"rule_type": "nutrition_constraint", "severity": "warning", "source_quote": "Ferritine 12 µg/L",
                        "rule_text": "Privilégie les aliments riches en fer avec de la vitamine C."}]}
    assert cycle.propose_lab_rules(db, user, call=lambda s, p, sc: (prompts.append(p), rules)[1]) == 1
    assert "Ferritine : 12" in prompts[0] and "sous la norme" in prompts[0]
    rule = db.scalar(select(PulseMedicalRule).where(PulseMedicalRule.user_id == user.id))
    assert (rule.status, rule.rule_type, rule.source_quote) == ("proposed", "nutrition_constraint", "Ferritine 12 µg/L")
    assert cycle.propose_lab_rules(db, user, call=lambda s, p, sc: rules) == 0  # déjà relue
