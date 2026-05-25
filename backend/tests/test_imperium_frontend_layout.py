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


def test_frontend_layout_endpoint_present_and_jwt_scoped() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/layout")
    assert response.status_code == 200


def test_frontend_layout_get_only_no_idempotency_key_required() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/layout")
    assert response.status_code == 200


def test_frontend_layout_response_shape_and_deterministic_order() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/layout")
    assert response.status_code == 200
    body = response.json()

    assert set(body) == {"layout_version", "read_only", "shell", "regions", "safe_explanation"}
    assert body["layout_version"] == "v1"
    assert body["read_only"] is True
    assert body["safe_explanation"] == "Frontend layout metadata for Imperium V1."

    assert set(body["shell"]) == {"style", "density", "navigation_position", "primary_surface"}
    assert body["shell"] == {
        "style": "imperium_luxury",
        "density": "compact",
        "navigation_position": "bottom",
        "primary_surface": "dashboard",
    }

    expected = [
        ("hero", "Primary daily focus area.", 10, True),
        ("mission", "Active mission overview.", 20, True),
        ("daily_plan", "Daily plan snapshot.", 30, True),
        ("path", "Path today status.", 40, True),
        ("pulse", "Pulse today status.", 50, True),
        ("vault", "Vault summary.", 60, True),
    ]
    assert [(r["key"], r["purpose"], r["order"], r["enabled"]) for r in body["regions"]] == expected


def test_frontend_layout_has_no_user_or_secret_provider_infra_metadata() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/layout")
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


def test_frontend_layout_contains_no_business_payload_keys() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/layout")
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


def test_frontend_layout_read_only_no_db_write() -> None:
    db = FakeDb()
    response = _client(db, _user()).get("/api/imperium/frontend/layout")
    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_frontend_layout_docs_metadata_only_static_v1_not_theme_not_health_not_discovery() -> None:
    contracts_docs = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8").lower()
    schema_docs = (DOCS_ROOT / "05_DATABASE_SCHEMA.md").read_text(encoding="utf-8").lower()

    for text in (contracts_docs, schema_docs):
        assert "/api/imperium/frontend/layout" in text
        assert "metadata only" in text
        assert "static deterministic v1" in text
        assert "not a dynamic theme" in text
        assert "not a health check" in text
        assert "not a dynamic discovery" in text
        assert "no business data read" in text
        assert "no secrets/providers/infra metadata" in text
