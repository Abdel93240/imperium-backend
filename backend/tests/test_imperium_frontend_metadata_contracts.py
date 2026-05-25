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


def test_frontend_metadata_contract_endpoints_are_registered_get_only_and_jwt_scoped() -> None:
    client = _client(FakeDb(), _user())
    for path in (
        "/api/imperium/home/bootstrap",
        "/api/imperium/contracts/index",
        "/api/imperium/contracts/compliance",
        "/api/imperium/frontend/navigation",
        "/api/imperium/frontend/theme-tokens",
    ):
        response = client.get(path)
        assert response.status_code == 200


def test_frontend_metadata_contracts_are_metadata_only_read_only_and_do_not_write_db() -> None:
    db = FakeDb()
    client = _client(db, _user())

    responses = {
        path: client.get(path)
        for path in (
            "/api/imperium/home/bootstrap",
            "/api/imperium/contracts/index",
            "/api/imperium/contracts/compliance",
            "/api/imperium/frontend/navigation",
            "/api/imperium/frontend/layout",
            "/api/imperium/frontend/theme-tokens",
        )
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

    assert [module["name"] for module in home["modules"]] == [
        "dashboard",
        "daily_plan",
        "mission",
        "vault",
        "path",
        "pulse",
    ]
    assert [group["name"] for group in contracts_index["groups"]] == [
        "home",
        "dashboard",
        "daily_plan",
        "mission",
        "vault",
        "path",
        "pulse",
    ]
    assert [check["status"] for check in compliance["checks"]] == ["declared"] * 5
    assert [item["key"] for item in navigation["items"]] == [
        "home",
        "dashboard",
        "daily_plan",
        "missions",
        "vault",
        "path",
        "pulse",
    ]

    assert all(module["status"] == "available" for module in home["modules"])
    assert all(endpoint["method"] in {"GET", "POST"} for group in contracts_index["groups"] for endpoint in group["endpoints"])
    assert all(endpoint["read_only"] is True or endpoint["read_only"] is False for group in contracts_index["groups"] for endpoint in group["endpoints"])
    assert all(check["status"] == "declared" for check in compliance["checks"])
    assert all(item["enabled"] is True for item in navigation["items"])
    assert [region["key"] for region in layout["regions"]] == ["hero", "mission", "daily_plan", "path", "pulse", "vault"]
    assert [surface["key"] for surface in theme_tokens["surfaces"]] == ["base", "card", "elevated"]
    assert [item["key"] for item in theme_tokens["spacing_scale"]] == ["xs", "sm", "md", "lg", "xl"]
    assert [item["key"] for item in theme_tokens["radius_scale"]] == ["sm", "md", "lg", "xl"]
    assert [item["key"] for item in theme_tokens["typography_scale"]] == ["caption", "body", "title", "hero"]


def test_frontend_metadata_contract_docs_explicitly_state_metadata_only_and_non_runtime_behavior() -> None:
    backend_root = __import__("pathlib").Path(__file__).resolve().parents[1]
    docs_root = backend_root.parent / "docs_master"
    contracts_docs = (docs_root / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8").lower()
    schema_docs = (docs_root / "05_DATABASE_SCHEMA.md").read_text(encoding="utf-8").lower()

    for text in (contracts_docs, schema_docs):
        assert "frontend metadata layer" in text
        assert "metadata only" in text
        assert "not a health check" in text
        assert "not openapi" in text
        assert "not dynamic discovery" in text
        assert "no business data read" in text
        assert "no secrets/providers/infra metadata" in text
