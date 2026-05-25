from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium_path
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumPathCheckIn, ImperiumPathHabit
from app.schemas.path import PathHabitCreate
from app.services.path.habits import _hash_request


class FakeDb:
    def __init__(self, *, scalar_results=None, scalars_results=None) -> None:
        self.scalar_results = list(scalar_results or [])
        self.scalars_results = [list(result) for result in scalars_results] if scalars_results is not None else None
        self.added = []
        self.queries = []
        self.flushed = False
        self.committed = False
        self.rolled_back = False

    def add(self, obj) -> None:
        self._prepare(obj)
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed = True
        for item in self.added:
            self._prepare(item)

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
        if self.scalars_results is not None:
            if self.scalars_results:
                return self.scalars_results.pop(0)
            return []
        return []

    def _prepare(self, obj) -> None:
        now = datetime.now(UTC)
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()
        if hasattr(obj, "created_at") and getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if hasattr(obj, "updated_at") and getattr(obj, "updated_at", None) is None:
            obj.updated_at = now


def _user(user_id=None) -> SimpleNamespace:
    return SimpleNamespace(id=user_id or uuid4())


def _client(db: FakeDb, current_user: SimpleNamespace) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_path.router, prefix="/imperium/path")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _habit(user_id, **overrides) -> ImperiumPathHabit:
    now = datetime.now(UTC)
    return ImperiumPathHabit(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        title=overrides.pop("title", "Fajr on time"),
        description=overrides.pop("description", None),
        domain=overrides.pop("domain", "worship"),
        frequency=overrides.pop("frequency", "daily"),
        is_active=overrides.pop("is_active", True),
        created_at=overrides.pop("created_at", now),
        updated_at=overrides.pop("updated_at", now),
    )


def _check_in(user_id, habit_id, **overrides) -> ImperiumPathCheckIn:
    now = datetime.now(UTC)
    return ImperiumPathCheckIn(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        habit_id=habit_id,
        check_date=overrides.pop("check_date", date(2026, 5, 25)),
        status=overrides.pop("status", "done"),
        reason=overrides.pop("reason", None),
        note=overrides.pop("note", "Completed after prayer"),
        created_at=overrides.pop("created_at", now),
        updated_at=overrides.pop("updated_at", now),
    )


def test_create_path_habit_ok() -> None:
    current_user = _user()
    db = FakeDb()

    response = _client(db, current_user).post(
        "/imperium/path/habits",
        headers={"Idempotency-Key": "path-habit-create-1"},
        json={
            "title": "  Fajr on time  ",
            "description": " Wake before Fajr ",
            "domain": "worship",
            "frequency": "daily",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Fajr on time"
    assert body["description"] == "Wake before Fajr"
    assert body["domain"] == "worship"
    assert body["frequency"] == "daily"
    assert body["is_active"] is True
    assert "user_id" not in body
    habit = next(item for item in db.added if isinstance(item, ImperiumPathHabit))
    assert habit.user_id == current_user.id
    assert habit.title == "Fajr on time"
    assert any(isinstance(item, IdempotencyKey) for item in db.added)
    assert db.committed is True


def test_create_path_habit_requires_idempotency_key() -> None:
    response = _client(FakeDb(), _user()).post(
        "/imperium/path/habits",
        json={"title": "Fajr on time", "domain": "worship", "frequency": "daily"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing Idempotency-Key header."


def test_create_path_habit_replays_same_idempotency_key() -> None:
    current_user = _user()
    created_at = datetime.now(UTC)
    response_body = {
        "id": str(uuid4()),
        "title": "Fajr on time",
        "description": None,
        "domain": "worship",
        "frequency": "daily",
        "is_active": True,
        "created_at": created_at.isoformat(),
        "updated_at": created_at.isoformat(),
    }
    payload = PathHabitCreate(title="Fajr on time", domain="worship", frequency="daily")
    db = FakeDb(
        scalar_results=[
            IdempotencyKey(
                id=uuid4(),
                user_id=current_user.id,
                idempotency_key="path-habit-replay",
                request_method="POST",
                request_path="/imperium/path/habits",
                request_hash=_hash_request("path.habit.created", payload.model_dump(mode="json")),
                status="completed",
                response_status_code=201,
                response_body=response_body,
                created_at=created_at,
                updated_at=created_at,
            )
        ]
    )

    response = _client(db, current_user).post(
        "/imperium/path/habits",
        headers={"Idempotency-Key": "path-habit-replay"},
        json={"title": "Fajr on time", "domain": "worship", "frequency": "daily"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == response_body["id"]
    assert not any(isinstance(item, ImperiumPathHabit) for item in db.added)


def test_list_path_habits_user_scoped_and_no_idempotency_required() -> None:
    current_user = _user()
    habit = _habit(current_user.id)
    db = FakeDb(scalars_results=[[habit]])

    response = _client(db, current_user).get("/imperium/path/habits?is_active=true&domain=worship")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["title"] == "Fajr on time"
    assert body["safe_explanation"] == "Path habits/check-ins for current user."
    query_text = str(db.queries[0])
    assert "imperium_path_habits.user_id" in query_text
    assert "imperium_path_habits.is_active" in query_text
    assert "imperium_path_habits.domain" in query_text


def test_create_path_check_in_ok() -> None:
    current_user = _user()
    habit = _habit(current_user.id)
    db = FakeDb(scalar_results=[None, habit, None])

    response = _client(db, current_user).post(
        f"/imperium/path/habits/{habit.id}/check-ins",
        headers={"Idempotency-Key": "path-check-in-1"},
        json={"check_date": "2026-05-25", "status": "done", "note": "Completed after prayer"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["habit_id"] == str(habit.id)
    assert body["check_date"] == "2026-05-25"
    assert body["status"] == "done"
    assert body["reason"] is None
    assert body["note"] == "Completed after prayer"
    check_in = next(item for item in db.added if isinstance(item, ImperiumPathCheckIn))
    assert check_in.user_id == current_user.id
    assert check_in.habit_id == habit.id
    assert db.committed is True


def test_create_path_check_in_rejects_inactive_habit() -> None:
    current_user = _user()
    habit = _habit(current_user.id, is_active=False)
    db = FakeDb(scalar_results=[None, habit])

    response = _client(db, current_user).post(
        f"/imperium/path/habits/{habit.id}/check-ins",
        headers={"Idempotency-Key": "path-check-in-inactive"},
        json={"check_date": "2026-05-25", "status": "done"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Path habit is inactive."
    assert not any(isinstance(item, ImperiumPathCheckIn) for item in db.added)


def test_create_path_check_in_requires_reason_when_missed() -> None:
    current_user = _user()
    habit = _habit(current_user.id)

    response = _client(FakeDb(scalar_results=[None, habit]), current_user).post(
        f"/imperium/path/habits/{habit.id}/check-ins",
        headers={"Idempotency-Key": "path-check-in-missed"},
        json={"check_date": "2026-05-25", "status": "missed"},
    )

    assert response.status_code == 422


def test_create_path_check_in_conflicts_when_date_already_checked_with_other_key() -> None:
    current_user = _user()
    habit = _habit(current_user.id)
    existing = _check_in(current_user.id, habit.id)
    db = FakeDb(scalar_results=[None, habit, existing])

    response = _client(db, current_user).post(
        f"/imperium/path/habits/{habit.id}/check-ins",
        headers={"Idempotency-Key": "path-check-in-duplicate-date"},
        json={"check_date": "2026-05-25", "status": "done"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Path check-in already exists for this habit and date."


def test_list_path_check_ins_user_scoped_and_no_idempotency_required() -> None:
    current_user = _user()
    habit_id = uuid4()
    check_in = _check_in(current_user.id, habit_id)
    db = FakeDb(scalars_results=[[check_in]])

    response = _client(db, current_user).get(
        f"/imperium/path/check-ins?habit_id={habit_id}&status=done&date_from=2026-05-01&date_to=2026-05-31"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["habit_id"] == str(habit_id)
    assert body["safe_explanation"] == "Path habits/check-ins for current user."
    query_text = str(db.queries[0])
    assert "imperium_path_check_ins.user_id" in query_text
    assert "imperium_path_check_ins.habit_id" in query_text
    assert "imperium_path_check_ins.status" in query_text
    assert "imperium_path_check_ins.check_date" in query_text
