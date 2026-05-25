from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium_vault
from app.models.vault import ImperiumVaultTransaction


class FakeDb:
    def __init__(self, *, scalar_results=None, scalars_results=None) -> None:
        self.scalar_results = list(scalar_results or [])
        self.scalars_results = [list(result) for result in scalars_results] if scalars_results is not None else None

    def scalar(self, query):
        if self.scalar_results:
            return self.scalar_results.pop(0)
        return None

    def scalars(self, query):
        if self.scalars_results is not None:
            if self.scalars_results:
                return self.scalars_results.pop(0)
            return []
        return []

    def add(self, obj) -> None:  # pragma: no cover - defensive no-op for route contract tests
        pass

    def flush(self) -> None:  # pragma: no cover - defensive no-op for route contract tests
        pass

    def commit(self) -> None:  # pragma: no cover - defensive no-op for route contract tests
        pass

    def rollback(self) -> None:  # pragma: no cover - defensive no-op for route contract tests
        pass


def _user(user_id=None) -> SimpleNamespace:
    return SimpleNamespace(id=user_id or uuid4())


def _client(db: FakeDb, current_user: SimpleNamespace) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_vault.router, prefix="/imperium/vault")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _transaction(user_id, **overrides) -> ImperiumVaultTransaction:
    now = datetime.now(UTC)
    occurred_at = overrides.pop("occurred_at", now)
    return ImperiumVaultTransaction(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        transaction_type=overrides.pop("transaction_type", "income"),
        amount_cents=overrides.pop("amount_cents", 1000),
        currency=overrides.pop("currency", "EUR"),
        occurred_at=occurred_at,
        local_date=overrides.pop("local_date", occurred_at.date()),
        timezone=overrides.pop("timezone", "UTC"),
        category=overrides.pop("category", "vtc"),
        source=overrides.pop("source", "manual"),
        note=overrides.pop("note", None),
        external_ref=overrides.pop("external_ref", None),
        created_at=overrides.pop("created_at", now),
        updated_at=overrides.pop("updated_at", now),
    )


def test_imperium_vault_routes_are_registered_in_a_safe_order() -> None:
    vault_routes = [
        (route.path, tuple(sorted(route.methods)))
        for route in imperium_vault.router.routes
        if isinstance(route, APIRoute)
    ]

    assert vault_routes == [
        ("/summary", ("GET",)),
        ("/summary/categories", ("GET",)),
        ("/summary/monthly", ("GET",)),
        ("/transactions", ("GET",)),
        ("/transactions/{transaction_id}", ("GET",)),
        ("/transactions", ("POST",)),
        ("/transactions/{transaction_id}/reverse", ("POST",)),
    ]


def test_imperium_vault_read_paths_do_not_require_idempotency_key() -> None:
    current_user = _user()
    own_transaction = _transaction(current_user.id)

    scenarios = (
        ("/imperium/vault/summary", FakeDb(scalars_results=[[]]), 200),
        ("/imperium/vault/summary/categories", FakeDb(scalars_results=[[]]), 200),
        ("/imperium/vault/summary/monthly", FakeDb(scalars_results=[[]]), 200),
        ("/imperium/vault/transactions?limit=1", FakeDb(scalars_results=[[]]), 200),
        (f"/imperium/vault/transactions/{own_transaction.id}", FakeDb(scalar_results=[own_transaction]), 200),
    )

    for path, db, expected_status in scenarios:
        response = _client(db, current_user).get(path)

        assert response.status_code == expected_status
        assert response.status_code != 400


def test_imperium_vault_write_paths_require_idempotency_key() -> None:
    current_user = _user()
    client = _client(FakeDb(), current_user)

    create_response = client.post(
        "/imperium/vault/transactions",
        json={
            "transaction_type": "income",
            "amount_cents": 1000,
            "currency": "EUR",
            "occurred_at": "2026-05-25T09:30:00+00:00",
            "category": "vtc",
            "source": "manual",
            "note": "Test",
            "external_ref": "ref-1",
        },
    )
    reverse_response = client.post(
        f"/imperium/vault/transactions/{uuid4()}/reverse",
        json={"reason": "Fixing a mistake"},
    )

    assert create_response.status_code == 400
    assert create_response.json()["detail"] == "Missing Idempotency-Key header."
    assert reverse_response.status_code == 400
    assert reverse_response.json()["detail"] == "Missing Idempotency-Key header."
