"""PostgreSQL : digest du WR et mode léger du docket (spec WR §3.6, §9 P1/P4, §13.2, §14.7)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("wr digest DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, func, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import wr  # noqa: E402
from app.models import ai  # noqa: E402,F401 - FK de la session WR vers ai_tasks
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.imperium import ImperiumWeeklyReviewSession  # noqa: E402
from app.models.toolbox import SignalValue  # noqa: E402
from app.models.wr import WrDigest, WrRollupDaily  # noqa: E402
from app.services.imperium.weekly_review_state import week_start_on  # noqa: E402
from app.services.imperium import weekly_review_conversation  # noqa: E402
from app.services.runner.engine import RunContext, Window  # noqa: E402
from app.services.wr import anomalies  # noqa: E402
from app.services.params import set_parameter  # noqa: E402
from app.services.wr import digest as digest_service  # noqa: E402
from app.services.wr import docket  # noqa: E402


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
        {"id": str(user_id), "email": f"digest-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(wr.router, prefix="/api/wr")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _session(db, user, *, launched: bool = True, status: str = "conversation_active") -> ImperiumWeeklyReviewSession:
    week_start = week_start_on(date.today(), 1)  # semaine du WR (mardi)
    session = ImperiumWeeklyReviewSession(
        user_id=user.id, week_start=week_start, week_end=week_start + timedelta(days=6), status=status,
    )
    if launched:
        session.launched_at = datetime.now(UTC)
    db.add(session)
    db.commit()
    return session


def _item(db, user, **overrides):
    fields = {
        "item_type": "anomaly", "domain": "vault", "title_fr": "Écart carburant",
        "payload": {"signal": "vault.fuel"}, "evidence_refs": {"events": ["evt_x"]},
        "impact_estimate": 3, "source_worker": "w4",
    }
    fields.update(overrides)
    item = docket.create_item(db, current_user=user, **fields)
    db.commit()
    return item


def test_digest_caps_per_type_and_freezes(db) -> None:
    user = _user(db)
    session = _session(db, user)
    for impact in range(1, 6):
        _item(db, user, item_type="belief_review_due", impact_estimate=impact)
    for _ in range(2):
        _item(db, user, item_type="belief_review_due", impact_estimate=1)  # 7 > cap 6
    question = _item(db, user, item_type="user_question", source_worker="manual")
    decided = _item(db, user)
    docket.decide(db, current_user=user, item_id=decided.id,
                  request=docket.DocketDecisionRequest(decision="refused", decision_note="Faux."), idempotency_key=uuid4().hex, request_path="/x")
    client = _client(db, user)
    assert client.get("/api/wr/digest/current").status_code == 404
    first = client.post("/api/wr/digest")
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["review_session_id"] == str(session.id)
    assert (body["window_from"], body["window_to"]) == (session.week_start.isoformat(), session.week_end.isoformat())
    sections = body["digest"]["docket"]
    beliefs = sections["belief_review_due"]
    assert len(beliefs) == 6 and beliefs[0]["impact_estimate"] == 5  # cap §13.2, par priorité
    assert body["digest"]["counts"]["belief_review_due"] == {"open": 7, "included": 6}
    assert [entry["id"] for entry in sections["user_question"]] == [str(question.id)]  # type sans cap
    assert "anomaly" not in sections  # l'item refusé n'est plus ouvert
    assert body["digest"]["unavailable"] == ["plan_state"]
    assert 0 < body["token_estimate"] <= 40000 and body["digest"]["truncated"] is False
    # Instantané figé : un nouvel item n'entre pas, le second appel rend le même digest.
    _item(db, user, item_type="user_question", source_worker="manual")
    again = client.post("/api/wr/digest")
    assert (again.status_code, again.json()) == (200, body)
    assert client.get("/api/wr/digest/current").json() == body
    event = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "planning.wr_digest.assembled"))
    assert event.payload == {"digest_id": body["id"], "review_session_id": str(session.id),
                             "token_estimate": body["token_estimate"], "items": 7}


def test_token_cap_truncates_lowest_priority_first(db) -> None:
    user = _user(db)
    _session(db, user)
    red = _item(db, user, item_type="red_flag_ref", severity="red", impact_estimate=1, title_fr="Rouge")
    for impact in (5, 4, 2):
        _item(db, user, impact_estimate=impact, payload={"signal": "x" * 2000})
    set_parameter(db, code="wr.digest_token_cap", value=1200, origin="test", rationale_fr="test")
    db.commit()
    body = _client(db, user).post("/api/wr/digest").json()
    assert body["token_estimate"] <= 1200 and body["digest"]["truncated"] is True
    kept = [entry["impact_estimate"] for entry in body["digest"]["docket"].get("anomaly", [])]
    assert kept == sorted(kept, reverse=True) and 2 not in kept  # le moins prioritaire part d'abord
    assert body["digest"]["docket"]["red_flag_ref"][0]["id"] == str(red.id)  # rouge protégé de la troncature
    set_parameter(db, code="wr.digest_token_cap", value=40000, origin="test", rationale_fr="reset")
    db.commit()


def test_whitelist_rejects_raw_content(db) -> None:
    user = _user(db)
    _session(db, user)
    _item(db, user, payload={"conversation": ["message brut"]})
    with pytest.raises(digest_service.DigestWhitelistError):
        digest_service.assemble_digest(db, current_user=user)
    db.rollback()
    with pytest.raises(digest_service.DigestWhitelistError):
        digest_service.check_section("review_messages")
    digest_service.check_section("docket")


def test_digest_needs_an_open_review(db) -> None:
    user = _user(db)
    client = _client(db, user)
    no_session = client.post("/api/wr/digest")
    assert (no_session.status_code, no_session.json()["code"]) == (409, "WR_NOT_OPEN")
    _session(db, user, launched=False, status="ready")
    assert client.post("/api/wr/digest").json()["code"] == "WR_NOT_OPEN"
    assert db.scalar(select(func.count()).select_from(WrDigest).where(WrDigest.user_id == user.id)) == 0


def test_light_mode_keeps_only_urgent_types(db) -> None:
    user = _user(db)
    red = _item(db, user, item_type="red_flag_ref", severity="red")
    contradiction = _item(db, user, item_type="pattern_contradiction", source_worker="w3")
    delta = _item(db, user, item_type="plan_delta_proposal", source_worker="phase3")
    forced = _item(db, user)
    forced.force_decision = True
    db.commit()
    _item(db, user, item_type="pattern_new", source_worker="w3")
    client = _client(db, user)
    light = {row["id"] for row in client.get("/api/wr/docket", params={"mode": "light"}).json()["items"]}
    assert light == {str(red.id), str(contradiction.id), str(delta.id), str(forced.id)}
    assert len(client.get("/api/wr/docket", params={"mode": "full"}).json()["items"]) == 5
    assert client.get("/api/wr/docket", params={"mode": "quick"}).status_code == 422


def test_digest_carries_week_rollups_and_anomalies(db) -> None:
    user = _user(db)
    session = _session(db, user)
    monday = session.week_start
    for offset, (income, minutes) in enumerate([(10000, 120), (5000, 0)]):
        day = monday + timedelta(days=offset)
        db.add(WrRollupDaily(user_id=user.id, local_date=day, domain="finance",
                             metrics={"income_cents": income, "expense_cents": 1000, "net_cents": income - 1000,
                                      "transaction_count": 2, "reversal_count": 0, "pressure_score": 30 + offset}))
        db.add(WrRollupDaily(user_id=user.id, local_date=day, domain="rides",
                             metrics={"sessions_ended": 1 if minutes else 0, "revenue_cents": 6000 if minutes else 0,
                                      "expense_cents": 0, "worked_minutes": minutes, "drop_zones": 2}))
    db.add(WrRollupDaily(user_id=user.id, local_date=monday - timedelta(days=1), domain="finance",
                         metrics={"income_cents": 999999}))  # semaine précédente : exclue
    for code, band, z, day in (("wr.finance.expense", "orange", 3.4, monday), ("wr.missions.failed", "red", 5.0, monday),
                               ("wr.finance.income", "green", 0.3, monday),
                               ("wr.finance.expense", "red", 9.0, monday - timedelta(days=2))):
        db.add(SignalValue(signal_code=code, measured_at=anomalies.measured_at(day), value=1, band=band,
                           flags={"flag": band != "green", "unexplained": band != "green"},
                           detail={"user_id": str(user.id), "local_date": day.isoformat(), "baseline": 0, "z": z}))
    db.commit()
    row, _ = digest_service.assemble_digest(db, current_user=user)
    rollups = row.digest["rollups"]
    assert (rollups["finance"]["days"], rollups["finance"]["income_cents"], rollups["finance"]["pressure_last"],
            rollups["finance"]["pressure_max"]) == (2, 15000, 31, 31)
    assert (rollups["rides"]["worked_minutes"], rollups["rides"]["net_per_hour_cents"]) == (120, 3000)
    assert [(entry["signal_code"], entry["band"]) for entry in row.digest["anomalies"]] == [
        ("wr.missions.failed", "red"), ("wr.finance.expense", "orange")]  # |z| décroissant, semaine seule


def test_launch_emits_once_and_the_job_assembles_the_digest(db) -> None:
    user = _user(db)
    week_start = week_start_on(date.today(), 1)  # semaine du WR (mardi)
    for key in (uuid4().hex, uuid4().hex):
        weekly_review_conversation.launch_weekly_review_session(
            db, current_user=user, week_start=week_start, idempotency_key=key, request_method="POST", request_path="/x")
    launched = db.scalars(select(Event).where(Event.user_id == user.id,
                                              Event.event_type == "planning.weekly_review.launched")).all()
    assert len(launched) == 1
    ctx = RunContext(db=db, job=None, run_id=uuid4(), trigger="event", trigger_ref=launched[0].id)
    digest_service.digest_on_open_job(ctx, Window(from_ts=None, to_ts=datetime.now(UTC)))
    assert ctx.items_out == 1 and ctx.detail["created"] is True
    assert db.scalar(select(WrDigest).where(WrDigest.user_id == user.id)) is not None
    again = RunContext(db=db, job=None, run_id=uuid4(), trigger="event", trigger_ref=launched[0].id)
    digest_service.digest_on_open_job(again, Window(from_ts=None, to_ts=datetime.now(UTC)))
    assert (again.items_out, again.detail["created"]) == (0, False)  # déjà figé
