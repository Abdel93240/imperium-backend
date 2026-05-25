from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium_vault
from app.models.vault import ImperiumVaultTransaction


class FakeDb:
    def __init__(self) -> None:
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
    return ImperiumVaultTransaction(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        transaction_type=overrides.pop("transaction_type", "income"),
        amount_cents=overrides.pop("amount_cents", 123400),
        currency=overrides.pop("currency", "EUR"),
        occurred_at=overrides.pop("occurred_at", now),
        category=overrides.pop("category", "vtc"),
        source=overrides.pop("source", "manual"),
        note=overrides.pop("note", "original note"),
        external_ref=overrides.pop("external_ref", "ext-1"),
        is_reversal=overrides.pop("is_reversal", False),
        reversal_of_transaction_id=overrides.pop("reversal_of_transaction_id", None),
        reversal_reason=overrides.pop("reversal_reason", None),
        created_at=overrides.pop("created_at", now),
        updated_at=overrides.pop("updated_at", now),
    )


def test_transaction_put_patch_delete_are_not_implemented_and_do_not_mutate_the_ledger() -> None:
    current_user = _user()
    original = _transaction(current_user.id)
    original_snapshot = {
        "id": original.id,
        "user_id": original.user_id,
        "transaction_type": original.transaction_type,
        "amount_cents": original.amount_cents,
        "currency": original.currency,
        "occurred_at": original.occurred_at,
        "category": original.category,
        "source": original.source,
        "note": original.note,
        "external_ref": original.external_ref,
        "is_reversal": original.is_reversal,
        "reversal_of_transaction_id": original.reversal_of_transaction_id,
        "reversal_reason": original.reversal_reason,
        "created_at": original.created_at,
        "updated_at": original.updated_at,
    }
    db = FakeDb()
    client = _client(db, current_user)

    for method in ("PUT", "PATCH", "DELETE"):
        response = client.request(method, f"/imperium/vault/transactions/{original.id}")

        assert response.status_code in {404, 405}
        assert response.status_code != 422
        assert {
            "id": original.id,
            "user_id": original.user_id,
            "transaction_type": original.transaction_type,
            "amount_cents": original.amount_cents,
            "currency": original.currency,
            "occurred_at": original.occurred_at,
            "category": original.category,
            "source": original.source,
            "note": original.note,
            "external_ref": original.external_ref,
            "is_reversal": original.is_reversal,
            "reversal_of_transaction_id": original.reversal_of_transaction_id,
            "reversal_reason": original.reversal_reason,
            "created_at": original.created_at,
            "updated_at": original.updated_at,
        } == original_snapshot
        assert db.added == []
        assert db.flushed is False
        assert db.committed is False
        assert db.rolled_back is False

    assert original.is_reversal is False
    assert original.reversal_of_transaction_id is None
    assert original.reversal_reason is None
