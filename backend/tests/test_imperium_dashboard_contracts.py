from datetime import date
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.router import api_router


class FakeDb:
    def __init__(self, *, scalar_results=None, scalars_results=None) -> None:
        self.scalar_results = list(scalar_results or [])
        self.scalars_results = [list(result) for result in scalars_results] if scalars_results is not None else []
        self.added = []
        self.flushed = False
        self.committed = False

    def add(self, obj) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed = True

    def commit(self) -> None:
        self.committed = True

    def scalar(self, query):
        if self.scalar_results:
            return self.scalar_results.pop(0)
        return None

    def scalars(self, query):
        if self.scalars_results:
            return self.scalars_results.pop(0)
        return []


def _client(db: FakeDb, current_user: SimpleNamespace) -> TestClient:
    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4())


def test_dashboard_route_is_registered_before_legacy_imperium_routes() -> None:
    api_router_text = (Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "router.py").read_text(
        encoding="utf-8"
    )
    dashboard_route_text = (
        Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "routes" / "imperium_dashboard.py"
    ).read_text(encoding="utf-8")
    legacy_route_text = (Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "routes" / "imperium.py").read_text(
        encoding="utf-8"
    )

    assert api_router_text.index("imperium_dashboard.router") < api_router_text.index("imperium.router")
    assert '@router.get("/dashboard"' in dashboard_route_text
    assert '@router.get("/dashboard"' not in legacy_route_text
    assert 'api_router.include_router(imperium_dashboard.router, prefix="/imperium", tags=["imperium-dashboard"])' in api_router_text


def test_dashboard_contract_shape_and_query_params() -> None:
    response = _client(FakeDb(scalar_results=[None], scalars_results=[[], [], []]), _user()).get(
        "/api/imperium/dashboard"
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "date",
        "currency",
        "mission",
        "vault",
        "path",
        "pulse",
        "readiness",
        "meta",
        "safe_explanation",
    }
    assert body["currency"] == "EUR"
    assert body["mission"]["active_mission"] is None
    assert set(body["readiness"]) == {
        "mission_available",
        "vault_available",
        "path_available",
        "pulse_available",
        "active_mission_present",
        "vault_transaction_count",
        "path_today_count",
        "pulse_entry_present",
        "safe_explanation",
    }
    assert body["readiness"]["mission_available"] is True
    assert body["readiness"]["vault_available"] is True
    assert body["readiness"]["path_available"] is True
    assert body["readiness"]["pulse_available"] is True
    assert body["meta"]["dashboard_version"] == "v1"
    assert body["meta"]["included_modules"] == ["mission", "vault", "path", "pulse"]
    assert body["meta"]["read_only"] is True
    assert body["safe_explanation"] == "Imperium dashboard snapshot for current user."


def test_dashboard_currency_is_normalized_and_invalid_currency_rejected() -> None:
    response = _client(FakeDb(scalar_results=[None], scalars_results=[[], [], []]), _user()).get(
        "/api/imperium/dashboard?currency=usd"
    )
    assert response.status_code == 200
    assert response.json()["currency"] == "USD"

    invalid_response = _client(FakeDb(scalar_results=[None], scalars_results=[[], [], []]), _user()).get(
        "/api/imperium/dashboard?currency=EU1"
    )
    assert invalid_response.status_code == 422


def test_dashboard_does_not_require_idempotency_key_and_stays_read_only() -> None:
    db = FakeDb(scalar_results=[None], scalars_results=[[], [], []])
    response = _client(db, _user()).get("/api/imperium/dashboard")

    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_dashboard_readiness_is_read_only_and_not_a_score() -> None:
    db = FakeDb(scalar_results=[None], scalars_results=[[], [], []])
    response = _client(db, _user()).get("/api/imperium/dashboard")

    assert response.status_code == 200
    readiness = response.json()["readiness"]
    assert readiness["safe_explanation"] == "Dashboard readiness snapshot computed from read-only module data."
    assert readiness["active_mission_present"] is False
    assert readiness["vault_transaction_count"] == 0
    assert readiness["path_today_count"] == 0
    assert readiness["pulse_entry_present"] is False
    assert "score" not in readiness
    assert "recommendation" not in readiness
    assert "health_score" not in readiness
    assert "coach" not in readiness


def test_dashboard_meta_is_read_only_metadata_only() -> None:
    response = _client(FakeDb(scalar_results=[None], scalars_results=[[], [], []]), _user()).get(
        "/api/imperium/dashboard"
    )

    assert response.status_code == 200
    meta = response.json()["meta"]
    assert meta["dashboard_version"] == "v1"
    assert meta["included_modules"] == ["mission", "vault", "path", "pulse"]
    assert meta["read_only"] is True
    assert meta["safe_explanation"] == "Dashboard metadata for current snapshot."
    assert "analytics" not in meta
    assert "telemetry" not in meta
    assert "score" not in meta
    assert "recommendation" not in meta


def test_dashboard_route_keeps_module_routes_available() -> None:
    app_text = (Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "router.py").read_text(encoding="utf-8")

    for route in (
        "imperium.router",
        "imperium_path.router",
        "imperium_pulse.router",
        "imperium_vault.router",
    ):
        assert route in app_text


def test_dashboard_query_date_reaches_response_shape() -> None:
    target_date = date(2026, 5, 24)
    response = _client(FakeDb(scalar_results=[None], scalars_results=[[], [], []]), _user()).get(
        f"/api/imperium/dashboard?date={target_date.isoformat()}"
    )

    assert response.status_code == 200
    assert response.json()["date"] == target_date.isoformat()
