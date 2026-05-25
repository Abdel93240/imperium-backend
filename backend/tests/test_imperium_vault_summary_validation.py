from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium_vault


class FakeDb:
    def __init__(self) -> None:
        self.queries = []

    def scalars(self, query):
        self.queries.append(query)
        return []


def _user(user_id=None) -> SimpleNamespace:
    return SimpleNamespace(id=user_id or uuid4())


def _client(db: FakeDb, current_user: SimpleNamespace) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_vault.router, prefix="/imperium/vault")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.mark.parametrize(
    "endpoint",
    [
        "/imperium/vault/summary",
        "/imperium/vault/summary/categories",
        "/imperium/vault/summary/monthly",
    ],
)
def test_vault_summary_endpoints_accept_lowercase_currency_and_normalize(endpoint: str) -> None:
    response = _client(FakeDb(), _user()).get(f"{endpoint}?currency=usd")

    assert response.status_code == 200
    assert response.json()["currency"] == "USD"


@pytest.mark.parametrize(
    ("endpoint", "currency"),
    [
        ("/imperium/vault/summary", "US1"),
        ("/imperium/vault/summary", "EURO"),
        ("/imperium/vault/summary/categories", "US1"),
        ("/imperium/vault/summary/categories", "EURO"),
        ("/imperium/vault/summary/monthly", "US1"),
        ("/imperium/vault/summary/monthly", "EURO"),
    ],
)
def test_vault_summary_endpoints_reject_invalid_currency(endpoint: str, currency: str) -> None:
    response = _client(FakeDb(), _user()).get(f"{endpoint}?currency={currency}")

    assert response.status_code == 422


@pytest.mark.parametrize(
    "endpoint",
    [
        "/imperium/vault/summary",
        "/imperium/vault/summary/categories",
        "/imperium/vault/summary/monthly",
    ],
)
def test_vault_summary_endpoints_reject_naive_occurred_from_without_500(endpoint: str) -> None:
    db = FakeDb()

    response = _client(db, _user()).get(f"{endpoint}?occurred_from=2026-01-01T00:00:00")

    assert response.status_code == 422
    assert db.queries == []
