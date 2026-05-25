from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium_path
from app.models.imperium import ImperiumPathCheckIn, ImperiumPathHabit


BACKEND_ROOT = Path(__file__).resolve().parents[1]


class FakeDb:
    def __init__(self, *, scalar_result=None, scalar_results=None, scalars_results=None) -> None:
        self.scalar_result = scalar_result
        self.scalar_results = list(scalar_results or [])
        self.scalars_results = [list(result) for result in scalars_results] if scalars_results is not None else None
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
        if self.scalars_results is not None:
            if self.scalars_results:
                return self.scalars_results.pop(0)
            return []
        return []



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



def _check_in(user_id, habit_id, **overrides) -> ImperiumPathCheckIn:
    now = datetime.now(UTC)
    return ImperiumPathCheckIn(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        habit_id=habit_id,
        check_date=overrides.pop("check_date", date(2026, 5, 25)),
        status=overrides.pop("status", "done"),
        reason=overrides.pop("reason", None),
        note=overrides.pop("note", "Completed"),
        created_at=overrides.pop("created_at", now),
        updated_at=overrides.pop("updated_at", now),
    )



def test_path_check_in_detail_returns_current_user_check_in() -> None:
    current_user = _user()
    habit = _habit(current_user.id)
    check_in = _check_in(current_user.id, habit.id)

    response = _client(FakeDb(scalar_result=check_in), current_user).get(f"/imperium/path/check-ins/{check_in.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["check_in"]["id"] == str(check_in.id)
    assert body["check_in"]["habit_id"] == str(habit.id)
    assert body["check_in"]["check_date"] == "2026-05-25"
    assert body["check_in"]["status"] == "done"
    assert body["check_in"]["reason"] is None
    assert body["check_in"]["note"] == "Completed"
    assert body["safe_explanation"] == "Path check-in detail for current user."



def test_path_check_in_detail_returns_404_for_missing_check_in() -> None:
    response = _client(FakeDb(scalar_result=None), _user()).get(f"/imperium/path/check-ins/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Path check-in not found."



def test_path_check_in_detail_returns_404_for_non_owned_check_in() -> None:
    current_user = _user()
    foreign_check_in = _check_in(_user().id, _habit(_user().id).id)

    response = _client(FakeDb(scalar_result=None), current_user).get(f"/imperium/path/check-ins/{foreign_check_in.id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Path check-in not found."



def test_path_check_in_detail_does_not_require_idempotency_key() -> None:
    current_user = _user()
    check_in = _check_in(current_user.id, _habit(current_user.id).id)

    response = _client(FakeDb(scalar_result=check_in), current_user).get(f"/imperium/path/check-ins/{check_in.id}")

    assert response.status_code == 200



def test_path_check_in_detail_is_read_only_and_does_not_create_or_modify_entities() -> None:
    current_user = _user()
    habit = _habit(current_user.id, title="Keep title")
    check_in = _check_in(current_user.id, habit.id, note="Keep note")
    db = FakeDb(scalar_result=check_in, scalars_results=[[check_in]])

    before_habit_title = habit.title
    before_check_in_note = check_in.note

    response = _client(db, current_user).get(f"/imperium/path/check-ins/{check_in.id}")

    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False
    assert db.rolled_back is False
    assert check_in.note == before_check_in_note
    assert habit.title == before_habit_title
    assert db.scalars_results == [[check_in]]



def test_path_check_in_detail_does_not_expose_user_id() -> None:
    current_user = _user()
    check_in = _check_in(current_user.id, _habit(current_user.id).id)

    response = _client(FakeDb(scalar_result=check_in), current_user).get(f"/imperium/path/check-ins/{check_in.id}")

    assert response.status_code == 200
    assert "user_id" not in response.json()["check_in"]



def test_path_check_in_detail_route_order_keeps_check_ins_list_route_distinct() -> None:
    route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_path.py").read_text(encoding="utf-8")

    list_index = route_text.index('@router.get("/check-ins"')
    detail_index = route_text.index('@router.get("/check-ins/{check_in_id}"')

    assert list_index < detail_index



def test_path_check_in_detail_does_not_introduce_ai_n8n_pgvector_embedding_memory_calendar_or_scoring() -> None:
    route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_path.py").read_text(encoding="utf-8").lower()
    service_text = (BACKEND_ROOT / "app" / "services" / "path" / "habits.py").read_text(encoding="utf-8").lower()
    schema_text = (BACKEND_ROOT / "app" / "schemas" / "path.py").read_text(encoding="utf-8").lower()
    combined = "\n".join([route_text, service_text, schema_text])

    for forbidden in (
        "qwenclient",
        "providers",
        "openai",
        "anthropic",
        "gemini",
        "claude",
        "n8n_client",
        "trigger_n8n",
        "n8n-nodes-langchain.agent",
        "pgvector",
        "embedding",
        "ai_memories",
        "automatic memory",
        "memory commit",
        "calendar",
        "scoring",
    ):
        assert forbidden not in combined
