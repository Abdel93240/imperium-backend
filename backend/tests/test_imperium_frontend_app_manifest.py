from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.router import api_router


FRONTEND_METADATA_ENDPOINTS = (
    "/api/imperium/home/bootstrap",
    "/api/imperium/contracts/index",
    "/api/imperium/contracts/compliance",
    "/api/imperium/frontend/navigation",
    "/api/imperium/frontend/layout",
    "/api/imperium/frontend/theme-tokens",
    "/api/imperium/frontend/empty-states",
    "/api/imperium/frontend/actions",
    "/api/imperium/frontend/module-cards",
    "/api/imperium/frontend/asset-registry",
    "/api/imperium/frontend/app-manifest",
    "/api/imperium/frontend/design-handoff",
)
FRONTEND_METADATA_ENDPOINT_SET = set(FRONTEND_METADATA_ENDPOINTS)


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


def test_frontend_app_manifest_endpoint_present_and_jwt_scoped() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/app-manifest")
    assert response.status_code == 200


def test_frontend_app_manifest_get_only_no_idempotency_key_required() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/app-manifest")
    assert response.status_code == 200


def test_frontend_app_manifest_response_shape_and_deterministic_order() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/app-manifest")
    assert response.status_code == 200
    body = response.json()

    assert set(body) == {"manifest_version", "read_only", "application", "frontend_metadata_endpoints", "safe_explanation"}
    assert body["manifest_version"] == "v1"
    assert body["read_only"] is True
    assert body["application"] == {
        "name": "Imperium",
        "tagline": "Personal command center.",
        "default_route": "/dashboard",
        "default_locale": "fr-FR",
        "default_timezone": "Europe/Paris",
    }
    assert body["frontend_metadata_endpoints"] == [
        *FRONTEND_METADATA_ENDPOINTS,
    ]
    assert body["safe_explanation"] == "Frontend application manifest metadata for Imperium V1."
    assert len(body["frontend_metadata_endpoints"]) == 12
    assert body["frontend_metadata_endpoints"] == list(FRONTEND_METADATA_ENDPOINTS)
    assert set(body["frontend_metadata_endpoints"]) == FRONTEND_METADATA_ENDPOINT_SET
    assert body["frontend_metadata_endpoints"][0] == "/api/imperium/home/bootstrap"
    assert body["frontend_metadata_endpoints"][-1] == "/api/imperium/frontend/design-handoff"
    assert "/api/imperium/frontend/static-copy" not in body["frontend_metadata_endpoints"]
    assert body["frontend_metadata_endpoints"].index("/api/imperium/frontend/asset-registry") == 9
    assert body["frontend_metadata_endpoints"].index("/api/imperium/frontend/design-handoff") == 11


def test_frontend_app_manifest_has_no_user_or_secret_provider_infra_metadata() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/app-manifest")
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
    assert "frontend_metadata_endpoints" in payload_text
    assert "openapi" not in payload_text
    assert "runtime discovery" not in payload_text
    assert "runtime audit" not in payload_text
    assert "feature flag" not in payload_text
    assert "personalization" not in payload_text
    assert "filesystem scan" not in payload_text
    assert "asset existence check" not in payload_text
    assert "react" not in payload_text
    assert "html" not in payload_text
    assert "css" not in payload_text
    assert "screenshot" not in payload_text
    assert "blob" not in payload_text
    assert "image payload" not in payload_text
    assert "upload" not in payload_text
    assert "cdn" not in payload_text
    assert "runtime rendering" not in payload_text


def test_frontend_app_manifest_contains_no_business_payload_keys() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/app-manifest")
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
        "ai",
        "n8n",
        "count",
        "score",
    ):
        assert forbidden not in payload_text
    assert "business data" not in payload_text


def test_frontend_app_manifest_read_only_no_db_write() -> None:
    db = FakeDb()
    response = _client(db, _user()).get("/api/imperium/frontend/app-manifest")
    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_frontend_app_manifest_docs_metadata_only_static_v1_not_discovery_not_health() -> None:
    contracts_docs = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8").lower()
    schema_docs = (DOCS_ROOT / "05_DATABASE_SCHEMA.md").read_text(encoding="utf-8").lower()

    for text in (contracts_docs, schema_docs):
        assert "/api/imperium/frontend/app-manifest" in text
        assert "/api/imperium/frontend/design-handoff" in text
        assert "metadata only" in text
        assert "static deterministic v1" in text
        assert "declarative endpoint list only" in text
        assert "not runtime discovery" in text
        assert "not openapi" in text
        assert "not a health check" in text
        assert "no business data read" in text
        assert "no secrets/providers/infra metadata" in text
        assert "/api/imperium/frontend/asset-registry" in text
