from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.router import api_router


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


def test_contracts_index_endpoint_registered_and_jwt_scoped() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/contracts/index")
    assert response.status_code == 200


def test_contracts_index_does_not_require_idempotency_key() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/contracts/index")
    assert response.status_code == 200


def test_contracts_index_contract_shape_and_exact_groups() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/contracts/index")
    assert response.status_code == 200

    assert response.json() == {
        "contract_version": "v1",
        "read_only": True,
        "groups": [
            {
                "name": "home",
                "endpoints": [
                    {
                        "method": "GET",
                        "path": "/api/imperium/home/bootstrap",
                        "purpose": "Frontend bootstrap metadata.",
                        "read_only": True,
                        "idempotency_key_required": False,
                    }
                ],
            },
            {
                "name": "dashboard",
                "endpoints": [
                    {
                        "method": "GET",
                        "path": "/api/imperium/dashboard",
                        "purpose": "Dashboard read-only snapshot.",
                        "read_only": True,
                        "idempotency_key_required": False,
                    }
                ],
            },
            {
                "name": "daily_plan",
                "endpoints": [
                    {
                        "method": "GET",
                        "path": "/api/imperium/daily-plan",
                        "purpose": "Daily plan read-only snapshot.",
                        "read_only": True,
                        "idempotency_key_required": False,
                    }
                ],
            },
            {
                "name": "mission",
                "endpoints": [
                    {
                        "method": "GET",
                        "path": "/api/imperium/missions/active",
                        "purpose": "Read active mission.",
                        "read_only": True,
                        "idempotency_key_required": False,
                    },
                    {
                        "method": "GET",
                        "path": "/api/imperium/missions/history",
                        "purpose": "Read mission history.",
                        "read_only": True,
                        "idempotency_key_required": False,
                    },
                    {
                        "method": "POST",
                        "path": "/api/imperium/missions/backlog",
                        "purpose": "Create backlog mission.",
                        "read_only": False,
                        "idempotency_key_required": True,
                    },
                ],
            },
            {
                "name": "vault",
                "endpoints": [
                    {
                        "method": "GET",
                        "path": "/api/imperium/vault/transactions",
                        "purpose": "Read ledger transactions.",
                        "read_only": True,
                        "idempotency_key_required": False,
                    },
                    {
                        "method": "POST",
                        "path": "/api/imperium/vault/transactions",
                        "purpose": "Create ledger transaction.",
                        "read_only": False,
                        "idempotency_key_required": True,
                    },
                    {
                        "method": "GET",
                        "path": "/api/imperium/vault/summary",
                        "purpose": "Read vault summary.",
                        "read_only": True,
                        "idempotency_key_required": False,
                    },
                ],
            },
            {
                "name": "path",
                "endpoints": [
                    {
                        "method": "GET",
                        "path": "/api/imperium/path/today",
                        "purpose": "Read Path today view.",
                        "read_only": True,
                        "idempotency_key_required": False,
                    },
                    {
                        "method": "GET",
                        "path": "/api/imperium/path/habits",
                        "purpose": "Read Path habits.",
                        "read_only": True,
                        "idempotency_key_required": False,
                    },
                    {
                        "method": "POST",
                        "path": "/api/imperium/path/habits",
                        "purpose": "Create Path habit.",
                        "read_only": False,
                        "idempotency_key_required": True,
                    },
                ],
            },
                {
                    "name": "pulse",
                    "endpoints": [
                        {
                            "method": "GET",
                        "path": "/api/imperium/pulse/today",
                        "purpose": "Read Pulse today entry.",
                        "read_only": True,
                        "idempotency_key_required": False,
                    },
                    {
                        "method": "GET",
                        "path": "/api/imperium/pulse/stats/summary",
                        "purpose": "Read Pulse summary stats.",
                        "read_only": True,
                        "idempotency_key_required": False,
                    },
                    {
                        "method": "POST",
                        "path": "/api/imperium/pulse/entries",
                        "purpose": "Create Pulse daily entry.",
                        "read_only": False,
                        "idempotency_key_required": True,
                        },
                    ],
                },
                {
                    "name": "frontend",
                    "endpoints": [
                        {
                            "method": "GET",
                            "path": "/api/imperium/frontend/navigation",
                            "purpose": "Frontend navigation metadata.",
                            "read_only": True,
                            "idempotency_key_required": False,
                        },
                        {
                            "method": "GET",
                            "path": "/api/imperium/frontend/layout",
                            "purpose": "Frontend layout metadata.",
                            "read_only": True,
                            "idempotency_key_required": False,
                        },
                        {
                            "method": "GET",
                            "path": "/api/imperium/frontend/theme-tokens",
                            "purpose": "Frontend theme token metadata.",
                            "read_only": True,
                            "idempotency_key_required": False,
                        },
                        {
                            "method": "GET",
                            "path": "/api/imperium/frontend/empty-states",
                            "purpose": "Frontend empty state metadata.",
                            "read_only": True,
                            "idempotency_key_required": False,
                        },
                        {
                            "method": "GET",
                            "path": "/api/imperium/frontend/actions",
                            "purpose": "Frontend action metadata.",
                            "read_only": True,
                            "idempotency_key_required": False,
                        },
                        {
                            "method": "GET",
                            "path": "/api/imperium/frontend/module-cards",
                            "purpose": "Frontend module cards metadata.",
                            "read_only": True,
                            "idempotency_key_required": False,
                        },
                        {
                            "method": "GET",
                            "path": "/api/imperium/frontend/asset-registry",
                            "purpose": "Frontend asset registry metadata.",
                            "read_only": True,
                            "idempotency_key_required": False,
                        },
                        {
                            "method": "GET",
                            "path": "/api/imperium/frontend/app-manifest",
                            "purpose": "Frontend application manifest metadata.",
                            "read_only": True,
                            "idempotency_key_required": False,
                        },
                        {
                            "method": "GET",
                            "path": "/api/imperium/frontend/design-handoff",
                            "purpose": "Frontend design handoff metadata.",
                            "read_only": True,
                            "idempotency_key_required": False,
                        },
                    ],
                },
            ],
            "safe_explanation": "Frontend API contract index metadata.",
        }


def test_contracts_index_read_only_no_db_write_and_no_sensitive_metadata() -> None:
    db = FakeDb()
    response = _client(db, _user()).get("/api/imperium/contracts/index")

    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False

    payload_text = str(response.json()).lower()
    assert "user_id" not in payload_text
    assert "secret" not in payload_text
    assert "provider" not in payload_text
    assert "infra" not in payload_text
    assert "health check runtime" not in payload_text
    assert "internal" not in payload_text


def test_contracts_index_get_and_post_idempotency_flags_are_consistent() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/contracts/index")
    assert response.status_code == 200
    for group in response.json()["groups"]:
        for endpoint in group["endpoints"]:
            if endpoint["method"] == "POST":
                assert endpoint["idempotency_key_required"] is True
            if endpoint["method"] == "GET":
                assert endpoint["idempotency_key_required"] is False


def test_contracts_index_excludes_openapi_health_and_internal_admin_paths() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/contracts/index")
    assert response.status_code == 200
    all_paths = [e["path"] for g in response.json()["groups"] for e in g["endpoints"]]
    forbidden_substrings = ("/openapi", "/docs", "/redoc", "/health", "/internal", "/admin")
    for path in all_paths:
        assert not any(token in path for token in forbidden_substrings)


def test_contracts_index_route_has_single_canonical_owner_file() -> None:
    backend_root = __import__("pathlib").Path(__file__).resolve().parents[1]
    contracts_route_text = (backend_root / "app" / "api" / "v1" / "routes" / "imperium_contracts.py").read_text(
        encoding="utf-8"
    )
    home_route_text = (backend_root / "app" / "api" / "v1" / "routes" / "imperium_home.py").read_text(
        encoding="utf-8"
    )

    assert contracts_route_text.count('@router.get("/contracts/index"') == 1
    assert '@router.get("/contracts/index"' not in home_route_text


def test_contracts_index_groups_order_is_deterministic() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/contracts/index")
    assert response.status_code == 200
    group_names = [group["name"] for group in response.json()["groups"]]
    assert group_names == ["home", "dashboard", "daily_plan", "mission", "vault", "path", "pulse", "frontend"]
    frontend_group = next(group for group in response.json()["groups"] if group["name"] == "frontend")
    assert [endpoint["path"] for endpoint in frontend_group["endpoints"]] == [
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
    assert len(frontend_group["endpoints"]) == 9


def test_contracts_index_frontend_group_is_metadata_only_and_no_runtime_assets() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/contracts/index")
    assert response.status_code == 200
    payload_text = str(response.json()).lower()

    for forbidden in (
        "react",
        "html",
        "css",
        "screenshot",
        "blob",
        "image payload",
        "upload",
        "cdn",
        "filesystem scan",
        "runtime rendering",
        "generated frontend code",
    ):
        assert forbidden not in payload_text
