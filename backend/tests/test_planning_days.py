from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import CheckConstraint

from app.api.deps import get_current_user, get_db
from app.api.v1.router import api_router
from app.api.v1.routes import imperium
from app.models.event import Event
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumDailyPlan, ImperiumDayReview, PlanningDay
from app.schemas.imperium import StartPlanningDayRequest
from app.services.imperium.planning_days import start_planning_day


class FakeDb:
    def __init__(self, *, scalar_results=None) -> None:
        self.scalar_results = list(scalar_results or [])
        self.added = []
        self.queries = []
        self.committed = False
        self.rolled_back = False

    def add(self, obj) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        now = datetime(2026, 9, 22, 14, 0, tzinfo=UTC)
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()
            if hasattr(obj, "created_at") and getattr(obj, "created_at", None) is None:
                obj.created_at = now
            if hasattr(obj, "updated_at") and getattr(obj, "updated_at", None) is None:
                obj.updated_at = now

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def scalar(self, query):
        self.queries.append(query)
        if self.scalar_results:
            return self.scalar_results.pop(0)
        return None

    def scalars(self, query):
        self.queries.append(query)
        return []


def _user(
    user_id: UUID | None = None,
    *,
    timezone: str = "Europe/Paris",
) -> SimpleNamespace:
    return SimpleNamespace(id=user_id or uuid4(), timezone=timezone)


def _client(db: FakeDb, current_user: SimpleNamespace) -> TestClient:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/api/imperium")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _api_client(db: FakeDb, current_user: SimpleNamespace) -> TestClient:
    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _open_day(user_id: UUID, **overrides) -> PlanningDay:
    started_at = overrides.pop("started_at", datetime(2026, 9, 22, 14, 0, tzinfo=UTC))
    return PlanningDay(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        started_at=started_at,
        finished_at=overrides.pop("finished_at", None),
        start_local_date=overrides.pop("start_local_date", date(2026, 9, 22)),
        timezone=overrides.pop("timezone", "Europe/Paris"),
        felt_energy=overrides.pop("felt_energy", 3),
        day_review_id=overrides.pop("day_review_id", None),
        idempotency_key=overrides.pop("idempotency_key", "start-day-1"),
        created_at=overrides.pop("created_at", started_at),
        updated_at=overrides.pop("updated_at", started_at),
    )


def _finish_payload() -> dict:
    return {
        "local_date": "2026-09-22",
        "timezone": "Europe/Paris",
        "day_status": "completed",
    }


def test_start_day_creates_open_day_and_emits_canonical_event() -> None:
    current_user = _user()
    db = FakeDb(scalar_results=[None, None])

    response = _client(db, current_user).post(
        "/api/imperium/day/start",
        json={"felt_energy": 4, "idempotency_key": "start-day-1"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "started"
    assert body["planning_day"]["felt_energy"] == 4
    assert body["planning_day"]["finished_at"] is None
    assert body["planning_day"]["timezone"] == "Europe/Paris"
    planning_day = next(item for item in db.added if isinstance(item, PlanningDay))
    event = next(item for item in db.added if isinstance(item, Event))
    assert planning_day.user_id == current_user.id
    assert event.event_type == "planning.day.started"
    assert event.payload == {"planning_day_id": str(planning_day.id), "felt_energy": 4}
    assert db.committed is True


def test_start_day_uses_europe_paris_calendar_date() -> None:
    current_user = _user(timezone="UTC")
    db = FakeDb(scalar_results=[None, None])

    response, duplicate = start_planning_day(
        db,
        current_user=current_user,
        payload=StartPlanningDayRequest(
            felt_energy=4,
            idempotency_key="start-day-paris-date",
        ),
        request_method="POST",
        request_path="/api/imperium/day/start",
        now=datetime(2026, 9, 22, 22, 30, tzinfo=UTC),
    )

    assert duplicate is False
    assert response.planning_day.timezone == "Europe/Paris"
    assert response.planning_day.start_local_date == date(2026, 9, 23)


def test_start_day_rejects_a_second_open_day() -> None:
    current_user = _user()
    db = FakeDb(scalar_results=[None, _open_day(current_user.id)])

    response = _client(db, current_user).post(
        "/api/imperium/day/start",
        json={"felt_energy": 2, "idempotency_key": "another-start"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "An operational day is already open."
    assert db.rolled_back is True


def test_start_day_is_idempotent_for_same_key_and_payload() -> None:
    current_user = _user()
    planning_day = _open_day(current_user.id)
    stored_response = {
        "planning_day": {
            "id": str(planning_day.id),
            "started_at": planning_day.started_at.isoformat(),
            "finished_at": None,
            "start_local_date": planning_day.start_local_date.isoformat(),
            "timezone": planning_day.timezone,
            "felt_energy": planning_day.felt_energy,
            "day_review_id": None,
            "idempotency_key": planning_day.idempotency_key,
            "created_at": planning_day.created_at.isoformat(),
            "updated_at": planning_day.updated_at.isoformat(),
        },
        "event_id": "evt_existing",
        "status": "started",
    }
    existing_key = IdempotencyKey(
        user_id=current_user.id,
        idempotency_key="start-day-1",
        request_method="POST",
        request_path="/api/imperium/day/start",
        request_hash="c99662f2360cba6282bf8cbbb6b47d4c2aa64c70a5f48604753cfbf4d44ffba7",
        status="completed",
        response_status_code=201,
        response_body=stored_response,
    )
    db = FakeDb(scalar_results=[existing_key])

    response = _client(db, current_user).post(
        "/api/imperium/day/start",
        json={"felt_energy": 3, "idempotency_key": "start-day-1"},
    )

    assert response.status_code == 200
    assert response.json()["event_id"] == "evt_existing"
    assert response.json()["planning_day"]["id"] == str(planning_day.id)
    assert response.json()["planning_day"]["felt_energy"] == 3
    assert db.added == []


def test_start_day_rejects_idempotency_key_reused_on_another_endpoint() -> None:
    current_user = _user()
    existing_key = IdempotencyKey(
        user_id=current_user.id,
        idempotency_key="start-day-1",
        request_method="POST",
        request_path="/api/imperium/another-mutation",
        request_hash="c99662f2360cba6282bf8cbbb6b47d4c2aa64c70a5f48604753cfbf4d44ffba7",
        status="completed",
        response_status_code=201,
        response_body={"status": "other"},
    )

    response = _client(FakeDb(scalar_results=[existing_key]), current_user).post(
        "/api/imperium/day/start",
        json={"felt_energy": 3, "idempotency_key": "start-day-1"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Idempotency-Key already used on a different endpoint."


def test_current_day_is_user_scoped_and_returns_null_or_open_day() -> None:
    current_user = _user()
    empty_db = FakeDb(scalar_results=[None])

    empty_response = _client(empty_db, current_user).get("/api/imperium/day/current")

    assert empty_response.status_code == 200
    assert empty_response.json() is None
    assert "planning_days.user_id" in str(empty_db.queries[0])
    open_day = _open_day(current_user.id)

    open_response = _client(FakeDb(scalar_results=[open_day]), current_user).get(
        "/api/imperium/day/current"
    )

    assert open_response.status_code == 200
    assert open_response.json()["id"] == str(open_day.id)


def test_finish_day_rejects_when_no_operational_day_is_open() -> None:
    db = FakeDb(scalar_results=[None, None])

    response = _client(db, _user()).post(
        "/api/imperium/day/finish",
        headers={"Idempotency-Key": "finish-day-1"},
        json=_finish_payload(),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "No operational day is open."
    assert db.rolled_back is True


def test_finish_day_rejects_idempotency_key_reused_on_another_endpoint() -> None:
    current_user = _user()
    existing_key = IdempotencyKey(
        user_id=current_user.id,
        idempotency_key="finish-day-1",
        request_method="POST",
        request_path="/api/imperium/another-mutation",
        request_hash="b5ea4b24ce16ceeba27548c263f335bb965ec8b691182549b76849532366486b",
        status="completed",
        response_status_code=201,
        response_body={"status": "other"},
    )

    response = _client(FakeDb(scalar_results=[existing_key]), current_user).post(
        "/api/imperium/day/finish",
        headers={"Idempotency-Key": "finish-day-1"},
        json=_finish_payload(),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Idempotency-Key already used on a different endpoint."


def test_finish_day_closes_open_day_and_links_review() -> None:
    current_user = _user()
    planning_day = _open_day(
        current_user.id,
        start_local_date=date(2026, 9, 22),
        timezone="Europe/Paris",
    )
    db = FakeDb(scalar_results=[None, planning_day, None])

    response = _client(db, current_user).post(
        "/api/imperium/day/finish",
        headers={"Idempotency-Key": "finish-day-1"},
        json={
            "local_date": "2026-09-23",
            "timezone": "UTC",
            "day_status": "completed",
        },
    )

    assert response.status_code == 201
    review = next(item for item in db.added if isinstance(item, ImperiumDayReview))
    event = next(item for item in db.added if isinstance(item, Event))
    assert review.local_date == date(2026, 9, 22)
    assert review.timezone == "Europe/Paris"
    assert planning_day.finished_at is not None
    assert planning_day.finished_at >= planning_day.started_at
    assert planning_day.day_review_id == review.id
    assert event.event_type == "planning.day.finished"
    assert event.payload["planning_day_id"] == str(planning_day.id)
    assert "planning_days.user_id" in "\n".join(str(query) for query in db.queries)
    assert db.committed is True


def test_today_plan_uses_open_day_start_date_after_midnight() -> None:
    current_user = _user()
    observed_at = datetime(2026, 9, 23, 0, 0, tzinfo=UTC)
    planning_day = _open_day(
        current_user.id,
        started_at=datetime(2026, 9, 22, 14, 0, tzinfo=UTC),  # 16:00 Europe/Paris
        start_local_date=date(2026, 9, 22),
    )
    plan = ImperiumDailyPlan(
        id=uuid4(),
        user_id=current_user.id,
        local_date=date(2026, 9, 22),
        timezone="Europe/Paris",
        plan_status="active",
        title="Operational plan",
        summary=None,
        focus_priority_key=None,
        current_mission_id=None,
        generated_from={},
        plan_blocks=[],
        notes=None,
        created_at=datetime(2026, 9, 22, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 9, 22, 12, 0, tzinfo=UTC),
    )
    # The request represents 02:00 Europe/Paris on 23 September. Resolution
    # must remain pinned to the open day's 22 September start date.
    db = FakeDb(scalar_results=[planning_day, plan])

    assert planning_day.started_at.astimezone(ZoneInfo("Europe/Paris")).hour == 16
    assert observed_at.astimezone(ZoneInfo("Europe/Paris")).hour == 2
    response = _client(db, current_user).get("/api/imperium/day/plan/today")

    assert response.status_code == 200
    assert response.json()["local_date"] == "2026-09-22"
    query_text = str(db.queries[1])
    assert "imperium_daily_plans.local_date" in query_text
    assert "imperium_daily_plans.user_id" in query_text
    assert date(2026, 9, 22) in db.queries[1].compile().params.values()


def test_today_plan_explicitly_reports_day_not_started() -> None:
    response = _client(FakeDb(scalar_results=[None]), _user()).get(
        "/api/imperium/day/plan/today"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Operational day has not been started."


def test_dashboard_hides_stale_mission_when_day_is_not_started() -> None:
    db = FakeDb(scalar_results=[None, None])

    response = _api_client(db, _user()).get("/api/imperium/dashboard")

    assert response.status_code == 200
    assert response.json()["day_status"] == "not_started"
    assert response.json()["mission"]["active_mission"] is None
    assert response.json()["mission"]["safe_explanation"] == "Operational day has not been started."
    assert "imperium_missions" not in "\n".join(str(query) for query in db.queries)


def test_planning_day_model_and_migration_lock_database_invariants() -> None:
    assert PlanningDay.__tablename__ == "planning_days"
    assert set(PlanningDay.__table__.columns.keys()) >= {
        "id",
        "user_id",
        "started_at",
        "finished_at",
        "start_local_date",
        "timezone",
        "felt_energy",
        "day_review_id",
        "created_at",
        "updated_at",
        "idempotency_key",
    }
    open_index = next(
        index
        for index in PlanningDay.__table__.indexes
        if index.name == "planning_days_one_open_per_user_idx"
    )
    assert open_index.unique is True
    assert str(open_index.dialect_options["postgresql"]["where"]) == "finished_at IS NULL"
    checks = {
        str(constraint.sqltext)
        for constraint in PlanningDay.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    check_names = {
        constraint.name
        for constraint in PlanningDay.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "felt_energy >= 1 AND felt_energy <= 5" in checks
    assert "finished_at IS NULL OR finished_at >= started_at" in checks
    assert check_names == {
        "ck_planning_days_felt_energy_range",
        "ck_planning_days_finished_after_started",
    }

    migration = Path("alembic/versions/20260923_0042_planning_days.py").read_text(encoding="utf-8")
    assert 'revision: str = "20260923_0042"' in migration
    assert 'down_revision: str | None = "20260716_0041"' in migration
    assert 'op.create_table(\n        "planning_days"' in migration
    assert 'name="felt_energy_range"' in migration
    assert 'name="finished_after_started"' in migration
    assert 'op.drop_table("planning_days")' in migration


def test_planning_day_is_documented_in_schema_and_event_catalog() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    schema_doc = (repository_root / "docs_master/05_DATABASE_SCHEMA.md").read_text(encoding="utf-8")
    events_doc = (repository_root / "docs_master/77_EVENTS_CATALOG.md").read_text(encoding="utf-8")

    assert "### planning_days" in schema_doc
    assert "planning.day.started" in events_doc
    assert "planning_day_id" in events_doc
    assert "felt_energy" in events_doc
