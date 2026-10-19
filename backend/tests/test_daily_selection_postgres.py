"""PostgreSQL : sélection Niveau 1, pull-forward et journal (spec Daily §5-7, §14 ; vague 28)."""
from __future__ import annotations

import time as clock
import urllib.request
from datetime import UTC, datetime, time, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("daily selection DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import daily, imperium  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.daily import DailySelectionLog, MissionDependency  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.imperium import ImperiumMission, ImperiumMissionScore  # noqa: E402
from app.services.daily import scores_refresh, selection  # noqa: E402
from app.services.params import set_parameter  # noqa: E402
from app.services.runner.engine import RunContext, Window  # noqa: E402
from app.services.travel import LatLng  # noqa: E402

PARIS = selection.PARIS
NOW = datetime(2026, 10, 21, 8, 0, tzinfo=UTC)  # mercredi 10 h à Paris
TODAY_18H = datetime(2026, 10, 21, 16, 0, tzinfo=UTC)
HOME = LatLng(48.8566, 2.3522)


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    # Les routes committent : transaction externe annulée, rien ne fuit.
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture()
def no_network(monkeypatch):
    calls = []

    def spy(*args, **kwargs):
        calls.append(args)
        raise AssertionError("outbound network request detected")

    monkeypatch.setattr(urllib.request, "urlopen", spy)
    return calls


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"dsel-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _flags(db, **values) -> None:
    for code, value in values.items():
        set_parameter(db, code=f"daily.{code}", value=value, origin="user", rationale_fr="Test.")
    db.commit()


def _mission(db, user, title: str, *, score: float = 50, deadline: datetime | None = None,
             planned: datetime | None = NOW, minutes: int = 20, status: str = "backlog", place: LatLng | None = None,
             **fields) -> ImperiumMission:
    mission = ImperiumMission(user_id=user.id, title=title, domain="finance", status=status, started_at=NOW,
                              planned_start_at=planned, deadline_at=deadline, estimated_minutes=minutes,
                              location_lat=place.lat if place else None, location_lng=place.lng if place else None,
                              **fields)
    db.add(mission)
    db.flush()
    db.add(ImperiumMissionScore(user_id=user.id, mission_id=mission.id, domain="finance", intrinsic_score=score / 10,
                                domain_coefficient=10, weighted_score=score, explanation={},
                                source="decision_framework_v1"))
    db.commit()
    return mission


def _near(km_east: float) -> LatLng:
    return LatLng(HOME.lat, HOME.lng + km_east / 73.0)  # ~73 km par degré de longitude à Paris


def _select(db, user, *, origin: LatLng | None = None, now: datetime = NOW) -> DailySelectionLog:
    row = selection.select_next(db, current_user=user, trigger="manual", origin=origin, now=now)
    db.commit()
    return row


def _entry(row: DailySelectionLog, mission: ImperiumMission) -> dict:
    return next(e for e in row.feasible_set if e["mission_id"] == str(mission.id))


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(daily.router, prefix="/api/daily")
    app.include_router(imperium.router, prefix="/api/imperium")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def test_seeded_off_and_routes_cut(db) -> None:
    assert selection.selection_enabled(db) is False
    assert selection.pullforward_enabled(db) is False  # la carte corrige le défaut true de la spec
    assert selection.queue_debug_enabled(db) is False
    flag = db.execute(text("SELECT value FROM v_parameters_current WHERE code = 'toolbox.travel_enabled'")).scalar()
    assert flag is False
    client = _client(db, _user(db))
    assert client.post("/api/daily/next", json={}).json()["code"] == "DAILY_SELECTION_DISABLED"
    assert client.get("/api/daily/current").status_code == 409
    assert client.post(f"/api/daily/complete/{uuid4()}", json={"outcome": "completed"},
                       headers={"Idempotency-Key": "k"}).status_code == 409


def test_mandatory_beats_a_higher_score_and_hierarchy_orders_inside(db) -> None:
    user = _user(db)
    high = _mission(db, user, "Haute, échéance lointaine", score=95, deadline=NOW + timedelta(days=5))
    due_low = _mission(db, user, "Échue aujourd'hui, basse", score=40, deadline=TODAY_18H)
    due_mid = _mission(db, user, "En retard, moyenne", score=60, deadline=NOW - timedelta(days=1))
    row = _select(db, user)
    assert row.outcome == "next_mission" and row.level == 1 and row.chosen_mission_id == due_mid.id
    assert set(row.mandatory_set) == {str(due_low.id), str(due_mid.id)}
    assert row.tiebreak_applied["pool"] == "mandatory"
    assert _entry(row, high)["blocked_by"] is None and _entry(row, high)["gates_passed"] == list(selection.GATES)


def test_blocked_mandatory_is_never_silently_dropped(db) -> None:
    user = _user(db)
    _mission(db, user, "Libre", score=90)
    closed = _mission(db, user, "Échue, fenêtre fermée", deadline=TODAY_18H, window_start=time(14, 0),
                      window_end=time(16, 0))
    row = _select(db, user)
    assert (row.outcome, row.level, row.condition, row.chosen_mission_id) == (
        "arbitration_pending", 2, "mandatory_conflict", None)
    assert _entry(row, closed)["blocked_by"] == "G3"
    event = db.scalar(select(Event).where(Event.user_id == user.id,
                                          Event.event_type == "planning.daily.arbitration_required"))
    assert event.payload == {"selection_log_id": str(row.id), "kind": "mandatory_conflict", "level": 2}


def test_mandatory_sum_over_remaining_time_is_a_conflict(db) -> None:
    user = _user(db)
    _mission(db, user, "Rendez-vous", is_fixed_commitment=True, fixed_at=NOW + timedelta(minutes=50), planned=None)
    _mission(db, user, "Échue A", deadline=TODAY_18H, minutes=30)
    _mission(db, user, "Échue B", deadline=TODAY_18H, minutes=30)
    row = _select(db, user)
    assert row.remaining_min == 50 and row.condition == "mandatory_conflict"


def test_dependency_gate_and_cycle_rejection(db) -> None:
    user = _user(db)
    parent = _mission(db, user, "Parent", score=30)
    child = _mission(db, user, "Enfant", score=90)
    _flags(db, selection_enabled=True)
    client = _client(db, user)
    created = client.post("/api/daily/dependencies",
                          json={"parent_mission_id": str(parent.id), "child_mission_id": str(child.id)})
    assert created.status_code == 201 and created.json()["hard"] is True
    cycle = client.post("/api/daily/dependencies",
                        json={"parent_mission_id": str(child.id), "child_mission_id": str(parent.id)})
    assert cycle.status_code == 422 and cycle.json()["code"] == "DEPENDENCY_CYCLE"
    again = client.post("/api/daily/dependencies",
                        json={"parent_mission_id": str(parent.id), "child_mission_id": str(child.id)})
    assert again.json()["code"] == "DEPENDENCY_EXISTS"
    row = _select(db, user)
    assert row.chosen_mission_id == parent.id and _entry(row, child)["blocked_by"] == "G2"
    parent.status = "completed"
    db.commit()
    assert _select(db, user).chosen_mission_id == child.id
    soft = _mission(db, user, "Préférence", score=99)
    db.add(MissionDependency(user_id=user.id, parent_mission_id=_mission(db, user, "Autre", score=1).id,
                             child_mission_id=soft.id, hard=False))
    db.commit()
    assert _select(db, user).chosen_mission_id == soft.id  # hard=false n'est pas une porte


def test_time_gate_before_next_fixed_commitment(db) -> None:
    user = _user(db)
    fixed = _mission(db, user, "Rendez-vous", is_fixed_commitment=True, fixed_at=NOW + timedelta(minutes=25),
                     planned=None)
    long = _mission(db, user, "Longue", score=90, minutes=30)
    short = _mission(db, user, "Courte", score=50, minutes=20)
    row = _select(db, user)
    assert row.remaining_min == 25 and row.next_fixed_ref == fixed.id
    assert _entry(row, long)["blocked_by"] == "G4" and row.chosen_mission_id == short.id
    assert all(e["mission_id"] != str(fixed.id) or e["blocked_by"] == "G1" for e in row.feasible_set)


def test_tiebreak_least_travel_inside_the_band_and_score_outside(db, no_network) -> None:
    user = _user(db)
    far = _mission(db, user, "Lointaine haute", score=100, place=_near(20))
    near = [_mission(db, user, f"Proche {i}", score=88 - i, place=_near(0.5 + i * 0.1)) for i in range(3)]
    row = _select(db, user, origin=HOME)
    assert row.chosen_mission_id == near[0].id  # clustering émergent : bande ≥ 85, moindre trajet
    assert row.tiebreak_applied["winner_reason"] == "least_travel"
    assert set(row.tiebreak_applied["band_members"]) == {str(far.id), *(str(m.id) for m in near)}
    assert {c["travel_source"] for c in row.tiebreak_applied["travel_costs"].values()} == {"fallback"}
    assert no_network == []

    other = _user(db)
    far = _mission(db, other, "Lointaine haute", score=100, place=_near(20))
    _mission(db, other, "Proche basse", score=80, place=_near(0.5))
    row = _select(db, other, origin=HOME)
    assert row.chosen_mission_id == far.id and row.tiebreak_applied["winner_reason"] == "only_candidate"


def test_pullforward_threshold_flag_and_day_done(db) -> None:
    user = _user(db)
    _mission(db, user, "Faite", status="completed")
    later = _mission(db, user, "Vendredi", planned=NOW + timedelta(days=2))
    _mission(db, user, "Semaine prochaine", planned=NOW + timedelta(days=7), score=99)
    row = _select(db, user)
    assert (row.outcome, row.level, row.chosen_mission_id) == ("day_done", 1, None)  # flag éteint
    _flags(db, pullforward_enabled=True)
    row = _select(db, user)
    assert (row.outcome, row.scope, row.pulled_forward, row.chosen_mission_id) == ("next_mission", "week", True, later.id)
    applied = db.scalar(select(Event).where(Event.user_id == user.id,
                                            Event.event_type == "planning.daily.pullforward_applied"))
    proposed = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "planning.daily.next_proposed",
                                             Event.payload["selection_log_id"].astext == str(row.id)))
    assert applied.causation_id == proposed.event_id
    late = _select(db, user, now=datetime(2026, 10, 21, 21, 30, tzinfo=UTC))  # 23 h 30 : 30 min < 45
    assert late.outcome == "day_done" and late.pulled_forward is False


def test_empty_feasible_with_missions_left_is_level_2(db) -> None:
    user = _user(db)
    _mission(db, user, "Fenêtre du soir", window_start=time(20, 0), window_end=time(22, 0))
    row = _select(db, user)
    assert (row.outcome, row.level, row.condition) == ("arbitration_pending", 2, "empty_feasible")


def test_complete_route_proposes_the_next_and_chains_events(db, no_network) -> None:
    user = _user(db)
    now = datetime.now(UTC)
    active = ImperiumMission(user_id=user.id, title="En cours", domain="finance", status="active", started_at=now)
    db.add(active)
    db.commit()
    nxt = _mission(db, user, "Suivante", planned=now, minutes=1)
    _flags(db, selection_enabled=True)
    client = _client(db, user)
    headers = {"Idempotency-Key": uuid4().hex}
    first = client.post(f"/api/daily/complete/{active.id}", json={"outcome": "completed"}, headers=headers)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["completion"]["mission"]["status"] == "completed"
    assert body["selection"]["outcome"] == "next_mission" and body["selection"]["next_mission"]["id"] == str(nxt.id)
    assert set(body["selection"]["next_mission"]) == {"id", "title", "domain", "estimated_minutes", "location_label",
                                                      "travel_source"}  # ni score ni file
    assert db.get(ImperiumMission, nxt.id).status == "backlog"  # proposée, jamais démarrée
    replay = client.post(f"/api/daily/complete/{active.id}", json={"outcome": "completed"}, headers=headers)
    assert replay.json()["selection"]["selection_log_id"] == body["selection"]["selection_log_id"]
    assert db.scalar(select(text("count(*)")).select_from(DailySelectionLog).where(
        DailySelectionLog.user_id == user.id)) == 1
    completed = db.get(Event, db.get(ImperiumMission, active.id).ended_by_event_id)
    proposed = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "planning.daily.next_proposed"))
    assert proposed.causation_id == completed.event_id and proposed.depth == completed.depth + 1
    assert proposed.correlation_id == completed.correlation_id
    assert proposed.payload["mission_id"] == str(nxt.id) and proposed.payload["level"] == 1
    current = client.get("/api/daily/current").json()
    assert current["active_mission_id"] is None and current["last_selection"]["next_mission"]["id"] == str(nxt.id)
    log = client.get("/api/daily/selection-log", params={"date": now.astimezone(PARIS).date().isoformat()}).json()
    assert [e["chosen_mission_id"] for e in log["entries"]] == [str(nxt.id)]
    assert client.get("/api/daily/queue").json()["code"] == "DAILY_QUEUE_DISABLED"
    _flags(db, queue_debug_enabled=True)
    assert client.get("/api/daily/queue").json()["chosen_mission_id"] == str(nxt.id)


def test_active_mission_is_never_touched(db) -> None:
    user = _user(db)
    db.add(ImperiumMission(user_id=user.id, title="En cours", domain="finance", status="active", started_at=NOW))
    db.commit()
    _flags(db, selection_enabled=True)
    response = _client(db, user).post("/api/daily/next", json={})
    assert response.status_code == 409 and response.json()["code"] == "MISSION_ACTIVE"


def test_constraints_route_replaces_and_validates(db) -> None:
    user = _user(db)
    mission = _mission(db, user, "Banque")
    _flags(db, selection_enabled=True)
    client = _client(db, user)
    body = {"location": {"lat": 48.87, "lng": 2.35, "label": "Agence"}, "window_start": "09:00:00",
            "window_end": "17:00:00", "window_days": ["mon", "tue"], "physical_load": 2}
    response = client.put(f"/api/daily/missions/{mission.id}/constraints", json=body)
    assert response.status_code == 200 and response.json()["location"]["label"] == "Agence"
    db.refresh(mission)
    assert (float(mission.location_lat), mission.window_days, mission.physical_load) == (48.87, ["mon", "tue"], 2)
    assert client.put(f"/api/daily/missions/{mission.id}/constraints", json={"is_fixed_commitment": True}).status_code == 422
    assert client.put(f"/api/daily/missions/{mission.id}/constraints", json={}).json()["location"] is None
    assert client.put(f"/api/daily/missions/{uuid4()}/constraints", json={}).status_code == 404


def test_nominal_path_has_no_model_no_network_and_stays_under_500ms(db, no_network, monkeypatch) -> None:
    user = _user(db)
    for i in range(50):
        _mission(db, user, f"M{i}", score=40 + i % 30, place=_near(i % 7), deadline=NOW + timedelta(days=1 + i % 5))
    from app.services.ai.providers import qwen

    model_calls = []
    monkeypatch.setattr(qwen.QwenClient, "__init__", lambda *a, **k: model_calls.append(a))
    started = clock.perf_counter()
    row = _select(db, user, origin=HOME)
    elapsed_ms = (clock.perf_counter() - started) * 1000
    assert row.outcome == "next_mission" and len(row.feasible_set) == 50
    assert elapsed_ms < 500 and row.latency_ms < 500
    assert no_network == [] and model_calls == []  # le fournisseur de modèle passe aussi par urlopen


def test_day_start_job_runs_the_initial_selection(db, monkeypatch) -> None:
    user = _user(db)
    monkeypatch.setattr("app.services.wr.metrics._job_user", lambda _db: user)
    mission = _mission(db, user, "Première", planned=datetime.now(UTC), minutes=1)
    _flags(db, selection_enabled=True)
    ctx = RunContext(db=db, job=None, run_id=uuid4(), trigger="event", trigger_ref=None)
    scores_refresh.day_start_job(ctx, Window(from_ts=None, to_ts=None))
    assert ctx.detail["selection"] == "next_mission"
    row = db.get(DailySelectionLog, ctx.detail["selection_log_id"])
    assert row.trigger == "day_start" and row.chosen_mission_id == mission.id
