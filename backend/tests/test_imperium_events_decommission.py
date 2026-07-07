from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.router import api_router


BACKEND_ROOT = Path(__file__).resolve().parents[1]


class _Db:
    pass


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: object()
    app.dependency_overrides[get_db] = lambda: _Db()
    return TestClient(app)


def test_imperium_events_routes_are_not_mounted() -> None:
    app = FastAPI()
    app.include_router(api_router, prefix="/api")

    routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/imperium/events")
    ]

    assert routes == []
    assert _client().get("/api/imperium/events").status_code == 404
    assert _client().post("/api/imperium/events", json={}).status_code == 404


def test_imperium_events_router_and_orphan_services_are_removed() -> None:
    assert not (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_events.py").exists()
    assert not (BACKEND_ROOT / "app" / "services" / "imperium" / "event_readers.py").exists()
    assert not (BACKEND_ROOT / "app" / "services" / "imperium" / "events.py").exists()

    router_text = (BACKEND_ROOT / "app" / "api" / "v1" / "router.py").read_text(encoding="utf-8")
    assert "imperium_events" not in router_text


def test_imperium_events_capability_is_removed_from_contract_index() -> None:
    response = _client().get("/api/imperium/contracts/index")

    assert response.status_code == 200
    groups = response.json()["groups"]
    assert "events" not in {group["name"] for group in groups}
    assert all(
        "/api/imperium/events" not in endpoint["path"]
        for group in groups
        for endpoint in group["endpoints"]
    )
