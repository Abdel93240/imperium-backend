from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium_path
from app.models.imperium import ImperiumPathCheckIn, ImperiumPathHabit


class FakeDb:
    def __init__(self, *, scalar_result=None, scalar_results=None, check_ins=None) -> None:
        self.scalar_result = scalar_result
        self.scalar_results = list(scalar_results or [])
        self.check_ins = list(check_ins or [])
        self.added = []
        self.queries = []
        self.flushed = False
        self.committed = False
        self.rolled_back = False

    def add(self, obj) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed = True

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def scalar(self, query):
        self.queries.append(query)
        if self.scalar_results:
            return self.scalar_results.pop(0)
        return self.scalar_result

    def scalars(self, query):
        self.queries.append(query)
        return list(self.check_ins)



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
        description=overrides.pop("description", "Pray before sunrise"),
        domain=overrides.pop("domain", "worship"),
        frequency=overrides.pop("frequency", "daily"),
        is_active=overrides.pop("is_active", True),
        created_at=overrides.pop("created_at", now),
        updated_at=overrides.pop("updated_at", now),
    )



def _check_in(user_id, habit_id) -> ImperiumPathCheckIn:
    now = datetime.now(UTC)
    return ImperiumPathCheckIn(
        id=uuid4(),
        user_id=user_id,
        habit_id=habit_id,
        check_date=date(2026, 5, 25),
        status="done",
        reason=None,
        note="Completed",
        created_at=now,
        updated_at=now,
    )



def test_path_habit_detail_returns_active_habit_for_current_user() -> None:
    current_user = _user()
    habit = _habit(current_user.id, is_active=True)
    response = _client(FakeDb(scalar_result=habit), current_user).get(f"/imperium/path/habits/{habit.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["habit"]["id"] == str(habit.id)
    assert body["habit"]["is_active"] is True
    assert body["safe_explanation"] == "Path habit detail for current user."



def test_path_habit_detail_returns_inactive_habit_for_current_user() -> None:
    current_user = _user()
    habit = _habit(current_user.id, is_active=False)
    response = _client(FakeDb(scalar_result=habit), current_user).get(f"/imperium/path/habits/{habit.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["habit"]["id"] == str(habit.id)
    assert body["habit"]["is_active"] is False



def test_path_habit_detail_returns_404_when_missing() -> None:
    response = _client(FakeDb(scalar_result=None), _user()).get(f"/imperium/path/habits/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Path habit not found."



def test_path_habit_detail_returns_404_when_non_owned() -> None:
    current_user = _user()
    foreign_habit = _habit(_user().id)

    response = _client(FakeDb(scalar_result=None), current_user).get(f"/imperium/path/habits/{foreign_habit.id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Path habit not found."



def test_path_habit_detail_does_not_require_idempotency_key() -> None:
    current_user = _user()
    habit = _habit(current_user.id)
    response = _client(FakeDb(scalar_result=habit), current_user).get(f"/imperium/path/habits/{habit.id}")

    assert response.status_code == 200



def test_path_habit_detail_is_read_only_and_does_not_create_check_ins() -> None:
    current_user = _user()
    habit = _habit(current_user.id)
    check_in = _check_in(current_user.id, habit.id)
    db = FakeDb(scalar_result=habit, check_ins=[check_in])

    response = _client(db, current_user).get(f"/imperium/path/habits/{habit.id}")

    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False
    assert db.rolled_back is False
    assert db.check_ins == [check_in]



def test_path_habit_detail_does_not_expose_user_id() -> None:
    current_user = _user()
    habit = _habit(current_user.id)

    response = _client(FakeDb(scalar_result=habit), current_user).get(f"/imperium/path/habits/{habit.id}")

    assert response.status_code == 200
    assert "user_id" not in response.json()["habit"]
