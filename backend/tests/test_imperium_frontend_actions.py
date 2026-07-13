from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.router import api_router


class FakeDb:
    def __init__(self) -> None:
        self.added = []
        self.flushed = False
        self.committed = False

    def add(self, obj) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed = True

    def commit(self) -> None:
        self.committed = True


def _client(db: FakeDb, current_user: SimpleNamespace) -> TestClient:
    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4())


def test_frontend_actions_endpoint_present_and_jwt_scoped() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/actions")
    assert response.status_code == 200


def test_frontend_actions_get_only_no_idempotency_key_required() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/actions")
    assert response.status_code == 200


def test_frontend_actions_response_shape_and_deterministic_order() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/actions")
    assert response.status_code == 200
    body = response.json()

    assert set(body) == {"actions_version", "read_only", "items", "safe_explanation"}
    assert body["actions_version"] == "v1"
    assert body["read_only"] is True
    assert body["safe_explanation"] == "Frontend action registry metadata for Imperium V1."
    assert len(body["items"]) == 6
    assert [item["key"] for item in body["items"]] == [
        "open_missions",
        "open_vault",
        "open_path",
        "open_pulse",
        "open_daily_plan",
        "open_dashboard",
    ]

    expected = [
        ("open_missions", "Open missions", "mission", "navigate", "/missions", False),
        ("open_vault", "Open Vault", "vault", "navigate", "/vault", False),
        ("open_path", "Open The Path", "path", "navigate", "/path", False),
        ("open_pulse", "Open Pulse", "pulse", "navigate", "/pulse", False),
        ("open_daily_plan", "Open Daily Plan", "daily_plan", "navigate", "/daily-plan", False),
        ("open_dashboard", "Open Dashboard", "dashboard", "navigate", "/dashboard", False),
    ]
    assert [
        (
            item["key"],
            item["label"],
            item["module"],
            item["action_type"],
            item["route"],
            item["requires_confirmation"],
        )
        for item in body["items"]
    ] == expected


def test_frontend_actions_has_no_user_or_secret_provider_infra_metadata() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/actions")
    assert response.status_code == 200
    payload_text = str(response.json()).lower()

    for forbidden in (
        "user_id",
        "provider",
        "host",
        "secret",
        "infra",
        "database",
        "postgres",
        "pgvector",
        "n8n",
        "openai",
        "anthropic",
        "gemini",
        "claude",
    ):
        assert forbidden not in payload_text


def test_frontend_actions_contains_no_business_payload_keys() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/actions")
    assert response.status_code == 200
    payload_text = str(response.json()).lower()

    for forbidden in (
        "income",
        "expense",
        "transaction",
        "balance",
        "mission_title",
        "mission_status",
        "prayer",
        "sadaqa",
        "workout",
        "calories",
        "score",
        "coaching",
        "recommendation",
        "health",
        "ocr",
        "openai",
        "anthropic",
        "gemini",
        "claude",
    ):
        assert forbidden not in payload_text


def test_frontend_actions_read_only_no_db_write() -> None:
    db = FakeDb()
    response = _client(db, _user()).get("/api/imperium/frontend/actions")
    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False
