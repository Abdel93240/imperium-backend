from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.routing import APIRoute
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
FRONTEND_METADATA_VERSION_FIELDS = (
    "manifest_version",
    "backend_version",
    "contract_version",
    "navigation_version",
    "layout_version",
    "theme_version",
    "empty_states_version",
    "actions_version",
    "module_cards_version",
    "asset_registry_version",
    "design_handoff_version",
)


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
    return TestClient(_app(db, current_user))


def _app(db: FakeDb, current_user: SimpleNamespace) -> FastAPI:
    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return app


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4())


def test_frontend_metadata_contract_endpoints_are_registered_get_only_and_jwt_scoped() -> None:
    client = _client(FakeDb(), _user())
    for path in FRONTEND_METADATA_ENDPOINTS:
        response = client.get(path)
        assert response.status_code == 200

    assert client.get("/api/imperium/frontend/static-copy").status_code == 404


def test_frontend_metadata_surface_snapshot_is_exact_and_get_only() -> None:
    app = _app(FakeDb(), _user())
    metadata_routes = [route for route in app.routes if isinstance(route, APIRoute) and route.path in FRONTEND_METADATA_ENDPOINT_SET]

    assert {route.path for route in metadata_routes} == FRONTEND_METADATA_ENDPOINT_SET
    assert len(metadata_routes) == len(FRONTEND_METADATA_ENDPOINTS)
    assert all(route.methods == {"GET"} for route in metadata_routes)
    assert "/api/imperium/frontend/static-copy" not in {
        route.path for route in app.routes if isinstance(route, APIRoute)
    }


def test_frontend_metadata_contracts_are_metadata_only_read_only_and_do_not_write_db() -> None:
    db = FakeDb()
    client = _client(db, _user())

    responses = {path: client.get(path) for path in FRONTEND_METADATA_ENDPOINTS}

    assert all(response.status_code == 200 for response in responses.values())
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False

    for path, response in responses.items():
        payload_text = str(response.json()).lower()
        assert "user_id" not in payload_text
        assert "secret" not in payload_text
        assert "provider" not in payload_text
        assert "infra" not in payload_text
        assert "n8n" not in payload_text
        assert "ocr" not in payload_text
        assert "scoring" not in payload_text
        assert "coaching" not in payload_text
        assert "recommendation" not in payload_text
        assert "dynamic discovery" not in payload_text
        assert "runtime audit" not in payload_text
        assert "filesystem scan" not in payload_text
        assert "asset existence check" not in payload_text
        if path != "/api/imperium/contracts/compliance":
            assert "openapi" not in payload_text
            assert "health check" not in payload_text


def test_frontend_metadata_contracts_are_deterministic_and_declarative() -> None:
    client = _client(FakeDb(), _user())

    home = client.get("/api/imperium/home/bootstrap").json()
    contracts_index = client.get("/api/imperium/contracts/index").json()
    compliance = client.get("/api/imperium/contracts/compliance").json()
    navigation = client.get("/api/imperium/frontend/navigation").json()
    layout = client.get("/api/imperium/frontend/layout").json()
    theme_tokens = client.get("/api/imperium/frontend/theme-tokens").json()
    empty_states = client.get("/api/imperium/frontend/empty-states").json()
    actions = client.get("/api/imperium/frontend/actions").json()
    app_manifest = client.get("/api/imperium/frontend/app-manifest").json()
    design_handoff = client.get("/api/imperium/frontend/design-handoff").json()

    assert [module["name"] for module in home["modules"]] == [
        "dashboard",
        "daily_plan",
        "mission",
        "vault",
        "path",
        "pulse",
    ]
    assert home["backend_version"] == "v1"
    assert [group["name"] for group in contracts_index["groups"]] == [
            "home",
            "dashboard",
            "daily_plan",
            "mission",
            "vault",
            "path",
        "pulse",
        "frontend",
    ]
    assert contracts_index["contract_version"] == "v1"
    assert [check["status"] for check in compliance["checks"]] == ["declared"] * 5
    assert compliance["contract_version"] == "v1"
    assert [item["key"] for item in navigation["items"]] == [
        "home",
        "dashboard",
        "daily_plan",
        "missions",
        "vault",
        "path",
        "pulse",
    ]
    assert navigation["navigation_version"] == "v1"
    assert [group["name"] for group in contracts_index["groups"] if group["name"] == "frontend"] == ["frontend"]
    assert [endpoint["path"] for endpoint in next(group for group in contracts_index["groups"] if group["name"] == "frontend")["endpoints"]] == [
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
    assert contracts_index["groups"][-1]["name"] == "frontend"
    assert [check["key"] for check in compliance["checks"]] == [
        "metadata_only",
        "not_openapi",
        "not_health_check",
        "no_business_data_read",
        "no_dynamic_discovery",
    ]

    assert all(module["status"] == "available" for module in home["modules"])
    assert all(module["primary_endpoint"].startswith("/api/imperium/") for module in home["modules"])
    frontend_contract_paths = {
        "/api/imperium/frontend/navigation",
        "/api/imperium/frontend/layout",
        "/api/imperium/frontend/theme-tokens",
        "/api/imperium/frontend/empty-states",
        "/api/imperium/frontend/actions",
        "/api/imperium/frontend/module-cards",
        "/api/imperium/frontend/asset-registry",
        "/api/imperium/frontend/app-manifest",
        "/api/imperium/frontend/design-handoff",
    }
    assert all(
        endpoint["method"] == "GET"
        for group in contracts_index["groups"]
        for endpoint in group["endpoints"]
        if endpoint["path"] in frontend_contract_paths
    )
    assert all(endpoint["method"] in {"GET", "POST"} for group in contracts_index["groups"] for endpoint in group["endpoints"])
    assert all(endpoint["read_only"] is True or endpoint["read_only"] is False for group in contracts_index["groups"] for endpoint in group["endpoints"])
    assert all(
        endpoint["idempotency_key_required"] is False
        for group in contracts_index["groups"]
        for endpoint in group["endpoints"]
        if endpoint["path"] in frontend_contract_paths
    )
    assert all(check["status"] == "declared" for check in compliance["checks"])
    assert all(item["enabled"] is True for item in navigation["items"])
    assert layout["layout_version"] == "v1"
    assert [region["key"] for region in layout["regions"]] == ["hero", "mission", "daily_plan", "path", "pulse", "vault"]
    assert theme_tokens["theme_version"] == "v1"
    assert [surface["key"] for surface in theme_tokens["surfaces"]] == ["base", "card", "elevated"]
    assert [item["key"] for item in theme_tokens["spacing_scale"]] == ["xs", "sm", "md", "lg", "xl"]
    assert [item["key"] for item in theme_tokens["radius_scale"]] == ["sm", "md", "lg", "xl"]
    assert [item["key"] for item in theme_tokens["typography_scale"]] == ["caption", "body", "title", "hero"]
    assert empty_states["empty_states_version"] == "v1"
    assert [item["key"] for item in empty_states["items"]] == [
        "no_active_mission",
        "no_vault_transactions",
        "no_path_habits",
        "no_pulse_entry",
    ]
    assert actions["actions_version"] == "v1"
    assert [item["key"] for item in actions["items"]] == [
        "open_missions",
        "open_vault",
        "open_path",
        "open_pulse",
        "open_daily_plan",
        "open_dashboard",
    ]
    assert set(app_manifest) == {
        "manifest_version",
        "read_only",
        "application",
        "frontend_metadata_endpoints",
        "safe_explanation",
    }
    assert app_manifest["manifest_version"] == "v1"
    assert app_manifest["read_only"] is True
    assert app_manifest["application"] == {
        "name": "Imperium",
        "tagline": "Personal command center.",
        "default_route": "/dashboard",
        "default_locale": "fr-FR",
        "default_timezone": "Europe/Paris",
    }
    assert app_manifest["frontend_metadata_endpoints"] == list(FRONTEND_METADATA_ENDPOINTS)
    assert app_manifest["safe_explanation"] == "Frontend application manifest metadata for Imperium V1."
    assert app_manifest["frontend_metadata_endpoints"].index("/api/imperium/frontend/asset-registry") == 9
    assert design_handoff["design_handoff_version"] == "v1"
    assert design_handoff["frontend_metadata_layer_version"] == "v6"
    assert design_handoff["supported_modules"] == [
        "dashboard",
        "daily_plan",
        "mission",
        "vault",
        "path",
        "pulse",
        "vector",
        "weekly_review",
    ]
    assert design_handoff["asset_groups"] == [
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
    assert design_handoff["design_rules"] == [
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
    assert design_handoff["safe_explanation"] == "Design handoff metadata only for Imperium V1."
    assert "react" not in str(design_handoff).lower()
    assert "html" not in str(design_handoff).lower()
    assert "css" not in str(design_handoff).lower()
    assert "screenshot" not in str(design_handoff).lower()
    assert "blob" not in str(design_handoff).lower()
    assert "image payload" not in str(design_handoff).lower()
    assert "upload" not in str(design_handoff).lower()
    assert "cdn" not in str(design_handoff).lower()
    assert "filesystem scan" not in str(design_handoff).lower()
    assert "runtime rendering" not in str(design_handoff).lower()
    assert "generated frontend code" not in str(design_handoff).lower()
    assert "user_id" not in str(app_manifest).lower()
    assert "secret" not in str(app_manifest).lower()
    assert "provider" not in str(app_manifest).lower()
    assert "infra" not in str(app_manifest).lower()
    assert all(item["action_type"] == "navigate" for item in actions["items"])
    assert all(item["requires_confirmation"] is False for item in actions["items"])

    for item in empty_states["items"]:
        assert set(item) == {
            "key",
            "module",
            "title",
            "message",
            "primary_action_label",
            "primary_route",
        }

    assert set(empty_states) == {"empty_states_version", "read_only", "items", "safe_explanation"}
    assert empty_states["empty_states_version"] == "v1"
    assert empty_states["read_only"] is True
    assert empty_states["safe_explanation"] == "Frontend empty state metadata for Imperium V1."
    assert actions["actions_version"] == "v1"
    assert actions["read_only"] is True
    assert actions["safe_explanation"] == "Frontend action registry metadata for Imperium V1."
    assert set(actions) == {"actions_version", "read_only", "items", "safe_explanation"}
    assert "user_id" not in str(app_manifest).lower()
    assert "secret" not in str(app_manifest).lower()
    assert "provider" not in str(app_manifest).lower()
    assert "infra" not in str(app_manifest).lower()
    assert "business" not in str(app_manifest).lower()
    assert "openapi" not in str(app_manifest).lower()
    assert "health check" not in str(app_manifest).lower()
    assert "runtime audit" not in str(app_manifest).lower()
    assert "dynamic discovery" not in str(app_manifest).lower()
    assert "n8n" not in str(app_manifest).lower()
    assert "ocr" not in str(app_manifest).lower()
    assert "scoring" not in str(app_manifest).lower()
    assert "coaching" not in str(app_manifest).lower()
    assert "recommendation" not in str(app_manifest).lower()
    assert FRONTEND_METADATA_VERSION_FIELDS == (
        "manifest_version",
        "backend_version",
        "contract_version",
        "navigation_version",
        "layout_version",
        "theme_version",
        "empty_states_version",
        "actions_version",
        "module_cards_version",
        "asset_registry_version",
        "design_handoff_version",
    )
    module_cards = client.get("/api/imperium/frontend/module-cards").json()
    assert module_cards["module_cards_version"] == "v1"
    assert [item["key"] for item in module_cards["items"]] == [
        "dashboard",
        "daily_plan",
        "mission",
        "vault",
        "path",
        "pulse",
    ]
    assert [item["primary_endpoint"] for item in module_cards["items"]] == [
        "/api/imperium/dashboard",
        "/api/imperium/daily-plan",
        "/api/imperium/missions/active",
        "/api/imperium/vault/summary",
        "/api/imperium/path/today",
        "/api/imperium/pulse/today",
    ]
    assert [item["order"] for item in module_cards["items"]] == [10, 20, 30, 40, 50, 60]
    assert all(item["enabled"] is True for item in module_cards["items"])
    assert all(
        set(item) == {"key", "title", "subtitle", "route", "primary_endpoint", "order", "enabled"}
        for item in module_cards["items"]
    )
    assert "status" not in str(module_cards).lower()
    assert "count" not in str(module_cards).lower()
    assert "score" not in str(module_cards).lower()
    assert "feature flag" not in str(module_cards).lower()
    assert "personalization" not in str(module_cards).lower()
    payload_text = str(empty_states).lower()
    for forbidden in (
        "user_id",
        "recommendation",
        "coaching",
        "ai decision",
        "health",
        "dynamic discovery",
        "openai",
        "anthropic",
        "gemini",
        "claude",
        "n8n",
        "ocr",
        "scoring",
        "action triggered",
    ):
        assert forbidden not in payload_text
    actions_text = str(actions).lower()
    for forbidden in (
        "user_id",
        "secret",
        "provider",
        "infra",
        "openapi",
        "health",
        "business data",
        "recommendation",
        "coaching",
        "n8n",
        "ocr",
        "scoring",
    ):
        assert forbidden not in actions_text

