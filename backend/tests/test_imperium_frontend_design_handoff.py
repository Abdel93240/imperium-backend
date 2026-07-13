import re
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.router import api_router


DESIGN_HANDOFF_PATH = "/api/imperium/frontend/design-handoff"

EXPECTED_FRONTEND_METADATA_ENDPOINTS = [
    "/api/imperium/frontend/navigation",
    "/api/imperium/frontend/layout",
    "/api/imperium/frontend/theme-tokens",
    "/api/imperium/frontend/empty-states",
    "/api/imperium/frontend/actions",
    "/api/imperium/frontend/module-cards",
    "/api/imperium/frontend/asset-registry",
    "/api/imperium/frontend/app-manifest",
    "/api/imperium/frontend/design-handoff",
]

EXPECTED_ASSET_GROUPS = [
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
]

EXPECTED_DESIGN_RULES = [
    "design_handoff_only",
    "metadata_only_frontend_contracts",
    "static_deterministic_v1",
    "declared_metadata_no_runtime_discovery",
    "declared_asset_groups_no_runtime_inventory",
    "no_frontend_rendering",
    "no_generated_frontend_code",
    "placeholders_allowed",
    "final_assets_can_be_provided_later",
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
        "frontend_metadata_endpoints": EXPECTED_FRONTEND_METADATA_ENDPOINTS,
        "asset_groups": EXPECTED_ASSET_GROUPS,
        "design_rules": EXPECTED_DESIGN_RULES,
        "safe_explanation": "Design handoff metadata only for Imperium V1.",
    }
    assert body["design_handoff_version"] == "v1"
    assert body["frontend_metadata_layer_version"] == "v6"
    assert body["supported_modules"] == [
        "dashboard",
        "daily_plan",
        "mission",
        "vault",
        "path",
        "pulse",
        "vector",
        "weekly_review",
    ]
    assert body["asset_groups"] == [
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
    ]
    assert body["design_rules"] == [
        "design_handoff_only",
        "metadata_only_frontend_contracts",
        "static_deterministic_v1",
        "declared_metadata_no_runtime_discovery",
        "declared_asset_groups_no_runtime_inventory",
        "no_frontend_rendering",
        "no_generated_frontend_code",
        "placeholders_allowed",
        "final_assets_can_be_provided_later",
    ]


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
        "font_file",
        "react",
        "html",
        "css",
        "screenshot",
        "blob",
        "image",
        "figma",
        "claude",
        "upload",
        "filesystem scan",
        "filesystem_scan",
        "asset existence check",
        "asset_existence_check",
        "openapi scan",
        "openapi_scan",
        "runtime audit",
        "runtime_audit",
        "business data",
        "business_data",
        "dynamic rendering",
        "dynamic_rendering",
        "layout runtime",
        "n8n",
        "ocr",
        "scoring",
        "coaching",
        "recommendation",
        "cross-module write",
        "cross_module_write",
    ):
        assert forbidden not in payload_text
    assert re.search(r"\bai\b", payload_text) is None


def test_frontend_design_handoff_exact_fields_contain_no_remote_or_embedded_assets() -> None:
    response = _client(FakeDb(), _user()).get(DESIGN_HANDOFF_PATH)
    assert response.status_code == 200
    body = response.json()

    assert body["frontend_metadata_endpoints"] == EXPECTED_FRONTEND_METADATA_ENDPOINTS
    assert all(endpoint.startswith("/api/imperium/frontend/") for endpoint in body["frontend_metadata_endpoints"])
    assert body["asset_groups"] == EXPECTED_ASSET_GROUPS
    assert body["design_rules"] == EXPECTED_DESIGN_RULES

    payload_text = str(body).lower()
    assert "http://" not in payload_text
    assert "https://" not in payload_text
    assert "data:" not in payload_text
    assert ";base64," not in payload_text
    assert ".ttf" not in payload_text
    assert ".otf" not in payload_text
    assert ".woff" not in payload_text
    assert ".woff2" not in payload_text
    assert "<html" not in payload_text
    assert "<script" not in payload_text
    assert "function " not in payload_text
    assert "const " not in payload_text
    assert "export default" not in payload_text
    assert "runtime rendering" not in payload_text
    assert "generated ui" not in payload_text
    assert "react" not in payload_text
    assert "html" not in payload_text
    assert "css" not in payload_text
    assert "screenshot" not in payload_text
    assert "blob" not in payload_text
    assert "image payload" not in payload_text
    assert "asset existence check" not in payload_text
    assert "filesystem scan" not in payload_text


def test_frontend_design_handoff_is_declared_in_contracts_index() -> None:
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
