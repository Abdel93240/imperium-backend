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


def test_frontend_empty_states_endpoint_present_and_jwt_scoped() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/empty-states")
    assert response.status_code == 200


def test_frontend_empty_states_get_only_no_idempotency_key_required() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/empty-states")
    assert response.status_code == 200


def test_frontend_empty_states_response_shape_and_deterministic_order() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/empty-states")
    assert response.status_code == 200
    body = response.json()

    assert set(body) == {"empty_states_version", "read_only", "items", "safe_explanation"}
    assert body["empty_states_version"] == "v1"
    assert body["read_only"] is True
    assert body["safe_explanation"] == "Frontend empty state metadata for Imperium V1."

    expected = [
        ("no_active_mission", "mission", "Open missions", "/missions"),
        ("no_vault_transactions", "vault", "Open Vault", "/vault"),
        ("no_path_habits", "path", "Open The Path", "/path"),
        ("no_pulse_entry", "pulse", "Open Pulse", "/pulse"),
    ]
    assert [
        (item["key"], item["module"], item["primary_action_label"], item["primary_route"]) for item in body["items"]
    ] == expected

    for item in body["items"]:
        assert set(item) == {
            "key",
            "module",
            "title",
            "message",
            "primary_action_label",
            "primary_route",
        }


def test_frontend_empty_states_has_no_user_or_secret_provider_infra_metadata() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/empty-states")
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
    ):
        assert forbidden not in payload_text


def test_frontend_empty_states_read_only_no_db_write() -> None:
    db = FakeDb()
    response = _client(db, _user()).get("/api/imperium/frontend/empty-states")
    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_frontend_empty_states_not_ai_not_recommendation_not_coaching_not_health_check() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/empty-states")
    assert response.status_code == 200
    payload_text = str(response.json()).lower()
    for forbidden in ("openai", "anthropic", "gemini", "claude", "n8n", "ocr", "scoring", "coaching", "health"):
        assert forbidden not in payload_text


def test_frontend_empty_states_docs_static_ui_copy_not_personalized_recommendation() -> None:
    contracts_docs = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8").lower()
    schema_docs = (DOCS_ROOT / "05_DATABASE_SCHEMA.md").read_text(encoding="utf-8").lower()

    for text in (contracts_docs, schema_docs):
        assert "/api/imperium/frontend/empty-states" in text
        assert "static ui copy metadata" in text
        assert "not personalized recommendation" in text
        assert "not coaching" in text
        assert "not ai decision" in text
        assert "not a health check" in text
        assert "no business data read" in text
        assert "removed from the active v1 contract" in text
        assert "/api/imperium/frontend/static-copy" not in text
