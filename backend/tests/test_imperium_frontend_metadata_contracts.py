from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.router import api_router


FRONTEND_METADATA_ENDPOINTS = {
    "/api/imperium/home/bootstrap",
    "/api/imperium/contracts/index",
    "/api/imperium/contracts/compliance",
    "/api/imperium/frontend/navigation",
    "/api/imperium/frontend/layout",
    "/api/imperium/frontend/theme-tokens",
    "/api/imperium/frontend/empty-states",
    "/api/imperium/frontend/actions",
}


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
    metadata_routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path in FRONTEND_METADATA_ENDPOINTS
    ]

    assert {route.path for route in metadata_routes} == FRONTEND_METADATA_ENDPOINTS
    assert len(metadata_routes) == len(FRONTEND_METADATA_ENDPOINTS)
    assert all(route.methods == {"GET"} for route in metadata_routes)
    assert "/api/imperium/frontend/static-copy" not in {
        route.path for route in app.routes if isinstance(route, APIRoute)
    }


def test_frontend_metadata_contracts_are_metadata_only_read_only_and_do_not_write_db() -> None:
    db = FakeDb()
    client = _client(db, _user())

    responses = {
        path: client.get(path)
        for path in FRONTEND_METADATA_ENDPOINTS
    }

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


def test_frontend_metadata_contract_docs_explicitly_state_metadata_only_and_non_runtime_behavior() -> None:
    backend_root = __import__("pathlib").Path(__file__).resolve().parents[1]
    docs_root = backend_root.parent / "docs_master"
    contracts_docs = (docs_root / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8").lower()
    schema_docs = (docs_root / "05_DATABASE_SCHEMA.md").read_text(encoding="utf-8").lower()

    expected_paths = (
        "/api/imperium/home/bootstrap",
        "/api/imperium/contracts/index",
        "/api/imperium/contracts/compliance",
        "/api/imperium/frontend/navigation",
        "/api/imperium/frontend/layout",
        "/api/imperium/frontend/theme-tokens",
        "/api/imperium/frontend/empty-states",
        "/api/imperium/frontend/actions",
    )
    assert "frontend metadata layer v3" in contracts_docs
    assert "stable and locked" in contracts_docs
    assert "metadata only" in contracts_docs
    assert "explicitly documented" in contracts_docs
    assert "no business data read" in contracts_docs
    assert "not a health check" in contracts_docs
    assert "not openapi" in contracts_docs
    assert "not dynamic discovery" in contracts_docs
    assert "no action triggered" in contracts_docs
    assert "jwt-scoped" in contracts_docs
    assert "idempotency-key not required" in contracts_docs
    for path in expected_paths:
        assert path in contracts_docs

    assert "frontend metadata layer v3" in schema_docs
    assert "metadata only" in schema_docs
    assert "no business data read" in schema_docs
    assert "not a health check" in schema_docs
    assert "not openapi" in schema_docs
    assert "not dynamic discovery" in schema_docs
    assert "no action triggered" in schema_docs
    assert "jwt-scoped" in schema_docs
    assert "idempotency-key not required" in schema_docs
    for path in expected_paths:
        assert path in schema_docs
