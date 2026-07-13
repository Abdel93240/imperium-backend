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


def test_frontend_navigation_endpoint_present_and_jwt_scoped() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/navigation")
    assert response.status_code == 200


def test_frontend_navigation_get_only_no_idempotency_key_required() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/navigation")
    assert response.status_code == 200


def test_frontend_navigation_response_shape_and_deterministic_order() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/navigation")
    assert response.status_code == 200
    body = response.json()

    assert set(body) == {"navigation_version", "read_only", "items", "safe_explanation"}
    assert body["navigation_version"] == "v1"
    assert body["read_only"] is True
    assert body["safe_explanation"] == "Frontend navigation metadata for Imperium."

    expected = [
        ("home", "Home", "/home", "/api/imperium/home/bootstrap", 10, True),
        ("dashboard", "Dashboard", "/dashboard", "/api/imperium/dashboard", 20, True),
        ("daily_plan", "Daily Plan", "/daily-plan", "/api/imperium/daily-plan", 30, True),
        ("missions", "Missions", "/missions", "/api/imperium/missions/active", 40, True),
        ("vault", "Vault", "/vault", "/api/imperium/vault/summary", 50, True),
        ("path", "The Path", "/path", "/api/imperium/path/today", 60, True),
        ("pulse", "Pulse", "/pulse", "/api/imperium/pulse/today", 70, True),
    ]
    assert [
        (item["key"], item["label"], item["route"], item["api_endpoint"], item["order"], item["enabled"])
        for item in body["items"]
    ] == expected


def test_frontend_navigation_has_no_user_or_secret_provider_infra_metadata() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/navigation")
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


def test_frontend_navigation_contains_no_business_payload_keys() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/navigation")
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
    ):
        assert forbidden not in payload_text


def test_frontend_navigation_read_only_no_db_write() -> None:
    db = FakeDb()
    response = _client(db, _user()).get("/api/imperium/frontend/navigation")
    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False
