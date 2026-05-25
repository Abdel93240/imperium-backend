from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.routing import Match

from app.api.deps import get_current_user, get_db
from app.api.v1.router import api_router
from app.api.v1.routes import imperium_path
from app.schemas.path import PathTodayResponse


class FakeDb:
    def __init__(self, *, scalars_results=None) -> None:
        self.scalars_results = [list(result) for result in scalars_results] if scalars_results is not None else None
        self.queries = []
        self.added = []
        self.flushed = False
        self.committed = False
        self.rolled_back = False

    def add(self, obj) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed = True

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def scalars(self, query):
        self.queries.append(query)
        if self.scalars_results is not None:
            if self.scalars_results:
                return self.scalars_results.pop(0)
            return []
        return []


def _app(db: FakeDb | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid4())
    app.dependency_overrides[get_db] = lambda: db or FakeDb()
    return app


def _resolve_route(app: FastAPI, *, method: str, path: str) -> APIRoute:
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "root_path": "",
        "headers": [],
        "query_string": b"",
    }
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return route
    raise AssertionError(f"No route matched {method} {path}.")


def test_full_api_router_resolves_path_today_to_canonical_path_handler() -> None:
    db = FakeDb(scalars_results=[[]])
    app = _app(db)

    route = _resolve_route(app, method="GET", path="/api/imperium/path/today")

    assert route.endpoint is imperium_path.path_today_route
    assert route.response_model is PathTodayResponse

    response = TestClient(app).get("/api/imperium/path/today?date=2026-05-25")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "date": "2026-05-25",
        "items": [],
        "count": 0,
        "safe_explanation": "Path today view for current user.",
    }
    assert not isinstance(body, list)
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_full_api_router_resolves_static_and_parametric_path_routes_to_canonical_module() -> None:
    app = _app()
    habit_id = "00000000-0000-0000-0000-000000000001"
    check_in_id = "00000000-0000-0000-0000-000000000002"

    expected_routes = {
        ("GET", "/api/imperium/path/stats/summary"): imperium_path.get_path_stats_summary_route,
        ("POST", "/api/imperium/path/habits"): imperium_path.create_path_habit_route,
        ("GET", "/api/imperium/path/habits"): imperium_path.list_path_habits_route,
        ("GET", f"/api/imperium/path/habits/{habit_id}"): imperium_path.get_path_habit_detail_route,
        ("POST", f"/api/imperium/path/habits/{habit_id}/archive"): imperium_path.archive_path_habit_route,
        ("POST", f"/api/imperium/path/habits/{habit_id}/reactivate"): imperium_path.reactivate_path_habit_route,
        ("POST", f"/api/imperium/path/habits/{habit_id}/check-ins"): imperium_path.create_path_check_in_route,
        ("GET", "/api/imperium/path/check-ins"): imperium_path.list_path_check_ins_route,
        ("GET", f"/api/imperium/path/check-ins/{check_in_id}"): imperium_path.get_path_check_in_detail_route,
    }

    for (method, path), endpoint in expected_routes.items():
        route = _resolve_route(app, method=method, path=path)

        assert route.endpoint is endpoint
