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


def test_contracts_compliance_endpoint_registered_and_jwt_scoped() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/contracts/compliance")
    assert response.status_code == 200


def test_contracts_compliance_does_not_require_idempotency_key() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/contracts/compliance")
    assert response.status_code == 200


def test_contracts_compliance_contract_shape_and_expected_flags() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/contracts/compliance")
    assert response.status_code == 200
    assert response.json() == {
        "contract_version": "v1",
        "read_only": True,
        "checks": [
            {
                "key": "metadata_only",
                "status": "declared",
                "safe_explanation": "Contracts index is metadata-only.",
            },
            {
                "key": "not_openapi",
                "status": "declared",
                "safe_explanation": "Contracts index is not a generated OpenAPI document.",
            },
            {
                "key": "not_health_check",
                "status": "declared",
                "safe_explanation": "Contracts index is not a runtime health check.",
            },
            {
                "key": "no_business_data_read",
                "status": "declared",
                "safe_explanation": "Contracts index does not read business data.",
            },
            {
                "key": "no_dynamic_discovery",
                "status": "declared",
                "safe_explanation": "Contracts index is static and deterministic in V1.",
            },
        ],
        "safe_explanation": "Frontend contracts compliance metadata.",
    }
    assert set(response.json()) == {"contract_version", "read_only", "checks", "safe_explanation"}


def test_contracts_compliance_read_only_no_db_write_and_no_sensitive_metadata() -> None:
    db = FakeDb()
    response = _client(db, _user()).get("/api/imperium/contracts/compliance")
    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False

    payload_text = str(response.json()).lower()
    assert "user_id" not in payload_text
    assert "secret" not in payload_text
    assert "provider" not in payload_text
    assert "infra" not in payload_text
    assert "passed" not in payload_text
    assert "failed" not in payload_text
