from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.router import api_router


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = BACKEND_ROOT.parent / "docs_master"


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


def test_frontend_module_cards_endpoint_present_and_jwt_scoped() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/module-cards")
    assert response.status_code == 200


def test_frontend_module_cards_get_only_no_idempotency_key_required() -> None:
    client = _client(FakeDb(), _user())
    assert client.get("/api/imperium/frontend/module-cards").status_code == 200


def test_frontend_module_cards_response_shape_and_deterministic_order() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/module-cards")
    assert response.status_code == 200
    body = response.json()

    assert set(body) == {"module_cards_version", "read_only", "items", "safe_explanation"}
    assert body["module_cards_version"] == "v1"
    assert body["read_only"] is True
    assert body["safe_explanation"] == "Frontend module card metadata for Imperium V1."
    assert [item["key"] for item in body["items"]] == [
        "dashboard",
        "daily_plan",
        "mission",
        "vault",
        "path",
        "pulse",
    ]
    assert [item["route"] for item in body["items"]] == [
        "/dashboard",
        "/daily-plan",
        "/missions",
        "/vault",
        "/path",
        "/pulse",
    ]
    assert [item["primary_endpoint"] for item in body["items"]] == [
        "/api/imperium/dashboard",
        "/api/imperium/daily-plan",
        "/api/imperium/missions/active",
        "/api/imperium/vault/summary",
        "/api/imperium/path/today",
        "/api/imperium/pulse/today",
    ]
    assert [item["order"] for item in body["items"]] == [10, 20, 30, 40, 50, 60]
    assert all(item["enabled"] is True for item in body["items"])


def test_frontend_module_cards_has_no_user_or_secret_provider_infra_metadata() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/module-cards")
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
        "openai",
        "anthropic",
        "gemini",
        "claude",
    ):
        assert forbidden not in payload_text


def test_frontend_module_cards_not_health_or_discovery_or_runtime_or_ai_or_business_runtime_state() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/module-cards")
    assert response.status_code == 200
    payload_text = str(response.json()).lower()

    for forbidden in (
        "health",
        "dynamic discovery",
        "runtime audit",
        "feature flag",
        "personalization",
        "recommendation",
        "coaching",
        "scoring",
        "ocr",
        "n8n",
        "status",
        "count",
        "score",
    ):
        assert forbidden not in payload_text


def test_frontend_module_cards_read_only_no_db_write() -> None:
    db = FakeDb()
    response = _client(db, _user()).get("/api/imperium/frontend/module-cards")
    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_frontend_module_cards_docs_metadata_only_static_v1_not_runtime_availability_or_personalization_or_feature_flag() -> None:
    contracts_docs = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8").lower()
    schema_docs = (DOCS_ROOT / "05_DATABASE_SCHEMA.md").read_text(encoding="utf-8").lower()

    for text in (contracts_docs, schema_docs):
        assert "/api/imperium/frontend/module-cards" in text
        assert "metadata only" in text
        assert "static deterministic v1" in text
        assert "not a health check" in text
        assert "not runtime availability" in text
        assert "not personalization" in text
        assert "not feature flag" in text
        assert "no business data read" in text
