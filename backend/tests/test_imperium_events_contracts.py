from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.router import api_router


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
DOCS_CONTRACTS = REPO_ROOT / "docs_master" / "04_MVP_BACKEND_CONTRACTS.md"
DOCS_SCHEMA = REPO_ROOT / "docs_master" / "05_DATABASE_SCHEMA.md"
ROUTE_PATH = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_events.py"
SERVICE_PATH = BACKEND_ROOT / "app" / "services" / "imperium" / "events.py"


class _Db:
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


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: object()
    app.dependency_overrides[get_db] = lambda: _Db()
    return TestClient(app)


def test_imperium_events_route_owner_is_canonical() -> None:
    route_text = ROUTE_PATH.read_text(encoding="utf-8")
    router_text = (BACKEND_ROOT / "app" / "api" / "v1" / "router.py").read_text(encoding="utf-8")

    assert "imperium_events.py" in str(ROUTE_PATH)
    assert "imperium_events" in router_text
    assert "@router.post(\"/events\"" in route_text
    assert "@router.get(\"/events\"," in route_text
    assert "@router.get(\"/events/{event_id}\"" in route_text


def test_imperium_events_routes_are_exact_and_ordered_safely() -> None:
    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    paths = [
        (route.methods, route.path)
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/imperium/events")
    ]

    assert paths == [
        ({"POST"}, "/api/imperium/events"),
        ({"GET"}, "/api/imperium/events"),
        ({"GET"}, "/api/imperium/events/{event_id}"),
    ]
    assert not any(route.path == "/api/imperium/events/" and "POST" in route.methods for route in app.routes if isinstance(route, APIRoute))
    assert not any(
        route.path.startswith("/api/imperium/events") and route.methods.intersection({"PUT", "PATCH", "DELETE"})
        for route in app.routes
        if isinstance(route, APIRoute)
    )


def test_imperium_events_contracts_enforce_idempotency_and_scope() -> None:
    client = _client()
    response = client.get("/api/imperium/contracts/index")

    assert response.status_code == 200
    body = response.json()
    events_group = next(group for group in body["groups"] if group["name"] == "events")

    assert events_group["endpoints"] == [
        {
            "method": "GET",
            "path": "/api/imperium/events",
            "purpose": "Read Imperium events.",
            "read_only": True,
            "idempotency_key_required": False,
        },
        {
            "method": "POST",
            "path": "/api/imperium/events",
            "purpose": "Append Imperium event.",
            "read_only": False,
            "idempotency_key_required": True,
        },
        {
            "method": "GET",
            "path": "/api/imperium/events/{event_id}",
            "purpose": "Read Imperium event detail.",
            "read_only": True,
            "idempotency_key_required": False,
        },
    ]


def test_imperium_events_public_shape_excludes_user_id_and_supports_documented_source_modules() -> None:
    docs_contracts = DOCS_CONTRACTS.read_text(encoding="utf-8").lower()
    docs_schema = DOCS_SCHEMA.read_text(encoding="utf-8").lower()
    model_text = (BACKEND_ROOT / "app" / "models" / "imperium.py").read_text(encoding="utf-8")

    assert "append-only" in docs_contracts
    assert "append-only" in docs_schema
    assert "no projections" in docs_contracts
    assert "no projections" in docs_schema
    assert "no cross-module writes" in docs_contracts
    assert "no cross-module writes" in docs_schema
    assert "strict currentuserdep" in docs_contracts
    assert "strict currentuserdep" in docs_schema
    assert "no user_id exposed" in docs_contracts
    assert "no user_id exposed" in docs_schema
    assert "source_module IN ('mission', 'vault', 'path', 'pulse', 'vector'," in model_text
    assert "'dashboard', 'daily_plan', 'system', 'manual')" in model_text
