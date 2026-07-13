from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.router import api_router


BACKEND_ROOT = Path(__file__).resolve().parents[1]


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


def test_home_bootstrap_endpoint_registered_and_jwt_scoped() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/home/bootstrap")
    assert response.status_code == 200


def test_home_bootstrap_does_not_require_idempotency_key() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/home/bootstrap")
    assert response.status_code == 200


def test_home_bootstrap_contract_shape_and_deterministic_modules() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/home/bootstrap")
    assert response.status_code == 200

    body = response.json()
    assert set(body) == {"backend_version", "read_only", "modules", "safe_explanation"}
    assert body["backend_version"] == "v1"
    assert body["read_only"] is True
    assert body["safe_explanation"] == "Imperium home bootstrap metadata for the current user."

    expected = [
        ("dashboard", "available", "/api/imperium/dashboard"),
        ("daily_plan", "available", "/api/imperium/daily-plan"),
        ("mission", "available", "/api/imperium/missions/active"),
        ("vault", "available", "/api/imperium/vault/summary"),
        ("path", "available", "/api/imperium/path/today"),
        ("pulse", "available", "/api/imperium/pulse/today"),
    ]
    assert [(m["name"], m["status"], m["primary_endpoint"]) for m in body["modules"]] == expected


def test_home_bootstrap_has_no_user_id_or_sensitive_infra_provider_metadata() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/home/bootstrap")
    assert response.status_code == 200
    payload_text = str(response.json()).lower()

    assert "user_id" not in payload_text
    assert "provider" not in payload_text
    assert "host" not in payload_text
    assert "secret" not in payload_text
    assert "infra" not in payload_text
    assert "database" not in payload_text
    assert "postgres" not in payload_text
    assert "pgvector" not in payload_text
    assert "n8n" not in payload_text
    assert "openai" not in payload_text
    assert "anthropic" not in payload_text
    assert "gemini" not in payload_text
    assert "claude" not in payload_text


def test_home_bootstrap_contains_no_business_payload_keys() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/home/bootstrap")
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
        "recommendation",
        "coaching",
        "health",
    ):
        assert forbidden not in payload_text


def test_home_bootstrap_read_only_no_db_write() -> None:
    db = FakeDb()
    response = _client(db, _user()).get("/api/imperium/home/bootstrap")

    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False

