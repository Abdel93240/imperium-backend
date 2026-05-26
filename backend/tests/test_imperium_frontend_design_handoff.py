from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.router import api_router


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = BACKEND_ROOT.parent / "docs_master"

DESIGN_HANDOFF_PATH = "/api/imperium/frontend/design-handoff"

EXPECTED_EXISTING_FRONTEND_METADATA_ENDPOINTS = [
    "/api/imperium/home/bootstrap",
    "/api/imperium/contracts/index",
    "/api/imperium/contracts/compliance",
    "/api/imperium/frontend/navigation",
    "/api/imperium/frontend/layout",
    "/api/imperium/frontend/theme-tokens",
    "/api/imperium/frontend/empty-states",
    "/api/imperium/frontend/actions",
    "/api/imperium/frontend/app-manifest",
    "/api/imperium/frontend/module-cards",
    "/api/imperium/frontend/asset-registry",
]


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


def _app(db: FakeDb, current_user: SimpleNamespace | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    if current_user is not None:
        app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return app


def _client(db: FakeDb, current_user: SimpleNamespace) -> TestClient:
    return TestClient(_app(db, current_user))


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4())


def test_frontend_design_handoff_endpoint_present_get_only_and_jwt_scoped() -> None:
    app = _app(FakeDb(), _user())
    client = TestClient(app)

    response = client.get(DESIGN_HANDOFF_PATH)
    assert response.status_code == 200

    matching_routes = [route for route in app.routes if isinstance(route, APIRoute) and route.path == DESIGN_HANDOFF_PATH]
    assert len(matching_routes) == 1
    assert matching_routes[0].methods == {"GET"}

    unauthenticated_client = TestClient(_app(FakeDb()))
    assert unauthenticated_client.get(DESIGN_HANDOFF_PATH).status_code == 401


def test_frontend_design_handoff_does_not_require_idempotency_key() -> None:
    response = _client(FakeDb(), _user()).get(DESIGN_HANDOFF_PATH)
    assert response.status_code == 200
    assert "idempotency-key" not in {key.lower() for key in response.request.headers}


def test_frontend_design_handoff_complete_shape_and_deterministic_order() -> None:
    response = _client(FakeDb(), _user()).get(DESIGN_HANDOFF_PATH)
    assert response.status_code == 200
    body = response.json()

    assert body == {
        "design_handoff_version": "v1",
        "read_only": True,
        "frontend_metadata_layer_version": "v6",
        "design_direction": {
            "style": "luxury_minimal_executive",
            "visual_language": "premium_dashboard",
            "mood": "focused_calm_powerful",
            "ui_philosophy": "clarity_before_density",
            "safe_explanation": "Imperium frontend design direction metadata.",
        },
        "supported_modules": [
            "dashboard",
            "daily_plan",
            "mission",
            "vault",
            "path",
            "pulse",
            "vector",
            "weekly_review",
        ],
        "frontend_metadata_endpoints": EXPECTED_EXISTING_FRONTEND_METADATA_ENDPOINTS,
        "asset_groups": [
            "core",
            "navigation",
            "dashboard",
            "modules",
            "vault",
            "path",
            "pulse",
            "vector",
            "weekly_review",
            "states",
            "backgrounds",
            "overlays",
        ],
        "design_rules": [
            "metadata_only_frontend_contracts",
            "static_deterministic_v1",
            "no_runtime_discovery",
            "no_business_logic_in_metadata",
            "placeholders_allowed",
            "final_assets_can_be_provided_later",
            "claude_code_design_ready",
        ],
        "safe_explanation": "Frontend design handoff metadata for Imperium V1.",
    }


def test_frontend_design_handoff_metadata_only_no_business_or_runtime_payload() -> None:
    db = FakeDb()
    response = _client(db, _user()).get(DESIGN_HANDOFF_PATH)
    assert response.status_code == 200

    assert db.added == []
    assert db.flushed is False
    assert db.committed is False

    payload_text = str(response.json()).lower()
    for forbidden in (
        "user_id",
        "secret",
        "provider",
        "infra",
        "remote url",
        "cdn",
        "base64",
        "font file",
        "react",
        "html",
        "css",
        "screenshot",
        "blob",
        "figma",
        "upload",
        "filesystem scan",
        "asset existence check",
        "openapi scan",
        "runtime audit",
        "business data",
        "dynamic rendering",
        "layout runtime",
    ):
        assert forbidden not in payload_text


def test_frontend_design_handoff_is_declared_in_contracts_index_and_docs() -> None:
    client = _client(FakeDb(), _user())
    contracts_index = client.get("/api/imperium/contracts/index").json()
    frontend_group = next(group for group in contracts_index["groups"] if group["name"] == "frontend")

    design_handoff_entry = next(endpoint for endpoint in frontend_group["endpoints"] if endpoint["path"] == DESIGN_HANDOFF_PATH)
    assert design_handoff_entry == {
        "method": "GET",
        "path": DESIGN_HANDOFF_PATH,
        "purpose": "Frontend design handoff metadata.",
        "read_only": True,
        "idempotency_key_required": False,
    }

    contracts_docs = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8").lower()
    schema_docs = (DOCS_ROOT / "05_DATABASE_SCHEMA.md").read_text(encoding="utf-8").lower()
    for text in (contracts_docs, schema_docs):
        assert DESIGN_HANDOFF_PATH in text
        assert "frontend design handoff metadata" in text
        assert "claude code design" in text
        assert "metadata only" in text
        assert "static deterministic v1" in text
        assert "no filesystem scan" in text
        assert "no asset existence check" in text
        assert "no remote url" in text
        assert "no base64" in text
        assert "no code frontend" in text
