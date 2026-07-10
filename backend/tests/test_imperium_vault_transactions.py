from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import CheckConstraint

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium_vault
from app.models.idempotency import IdempotencyKey
from app.models.vault import ImperiumVaultTransaction
from app.schemas.vault import ImperiumVaultTransactionCreate
from app.services.imperium.vault_transactions import _hash_request


class FakeDb:
    def __init__(self, *, scalar_results=None, scalars_results=None) -> None:
        self.scalar_results = list(scalar_results or [])
        self.scalars_results = [list(result) for result in scalars_results] if scalars_results is not None else None
        self.added = []
        self.queries = []
        self.flushed = False
        self.committed = False
        self.rolled_back = False

    def add(self, obj) -> None:
        self._prepare(obj)
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed = True
        for item in self.added:
            self._prepare(item)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def scalar(self, query):
        self.queries.append(query)
        if self.scalar_results:
            return self.scalar_results.pop(0)
        return None

    def scalars(self, query):
        self.queries.append(query)
        if self.scalars_results is not None:
            if self.scalars_results:
                return self.scalars_results.pop(0)
            return []
        return []

    def _prepare(self, obj) -> None:
        now = datetime.now(UTC)
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()
        if hasattr(obj, "created_at") and getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if hasattr(obj, "updated_at") and getattr(obj, "updated_at", None) is None:
            obj.updated_at = now


def _user(user_id=None) -> SimpleNamespace:
    return SimpleNamespace(id=user_id or uuid4())


def _client(db: FakeDb, current_user: SimpleNamespace) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_vault.router, prefix="/imperium/vault")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _payload(**overrides) -> dict:
    payload = {
        "transaction_type": "income",
        "amount_cents": 123400,
        "currency": "EUR",
        "wallet": "cash",
        "occurred_at": "2026-05-25T09:30:00+00:00",
        "category": "vtc",
        "source": "manual",
        "note": "Monday revenue",
        "external_ref": "bolt-shift-1",
    }
    payload.update(overrides)
    return payload


def _transaction(user_id, **overrides) -> ImperiumVaultTransaction:
    now = datetime.now(UTC)
    occurred_at = overrides.pop("occurred_at", now)
    return ImperiumVaultTransaction(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        transaction_type=overrides.pop("transaction_type", "income"),
        amount_cents=overrides.pop("amount_cents", 123400),
        currency=overrides.pop("currency", "EUR"),
        wallet=overrides.pop("wallet", "cash"),
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


def _idempotency_for(*, current_user, payload: dict, response_body: dict) -> IdempotencyKey:
    request_payload = ImperiumVaultTransactionCreate(**payload)
    return IdempotencyKey(
        id=uuid4(),
        user_id=current_user.id,
        idempotency_key="vault-idem-1",
        request_method="POST",
        request_path="/imperium/vault/transactions",
        request_hash=_hash_request("imperium.vault.transaction.created", request_payload.model_dump(mode="json")),
        status="completed",
        response_status_code=201,
        response_body=response_body,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def test_post_creates_income_transaction() -> None:
    current_user = _user()
    db = FakeDb()

    response = _client(db, current_user).post(
        "/imperium/vault/transactions",
        headers={"Idempotency-Key": "vault-income-1"},
        json=_payload(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["transaction_type"] == "income"
    assert body["amount_cents"] == 123400
    assert body["currency"] == "EUR"
    assert body["wallet"] == "cash"
    assert "user_id" not in body
    transaction = next(item for item in db.added if isinstance(item, ImperiumVaultTransaction))
    assert transaction.user_id == current_user.id
    assert transaction.transaction_type == "income"
    assert transaction.wallet == "cash"
    assert transaction.local_date.isoformat() == "2026-05-25"
    assert transaction.timezone == "UTC"
    assert any(isinstance(item, IdempotencyKey) for item in db.added)
    assert db.committed is True


def test_post_creates_expense_transaction() -> None:
    current_user = _user()
    db = FakeDb()

    response = _client(db, current_user).post(
        "/imperium/vault/transactions",
        headers={"Idempotency-Key": "vault-expense-1"},
        json=_payload(
            transaction_type="expense",
            amount_cents=5490,
            currency="eur",
            wallet=" bank ",
            category=" fuel ",
            note=" diesel ",
        ),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["transaction_type"] == "expense"
    assert body["amount_cents"] == 5490
    assert body["currency"] == "EUR"
    assert body["wallet"] == "bank"
    assert body["category"] == "fuel"
    assert body["note"] == "diesel"


def test_post_persists_local_date_from_submitted_timezone_offset() -> None:
    current_user = _user()
    db = FakeDb()

    response = _client(db, current_user).post(
        "/imperium/vault/transactions",
        headers={"Idempotency-Key": "vault-local-date-1"},
        json=_payload(occurred_at="2026-01-31T23:30:00-05:00"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["occurred_at"] == "2026-01-31T23:30:00-05:00"
    assert body["local_date"] == "2026-01-31"
    assert body["timezone"] == "UTC-05:00"
    transaction = next(item for item in db.added if isinstance(item, ImperiumVaultTransaction))
    assert transaction.local_date.isoformat() == "2026-01-31"
    assert transaction.timezone == "UTC-05:00"


def test_post_requires_idempotency_key() -> None:
    response = _client(FakeDb(), _user()).post(
        "/imperium/vault/transactions",
        json=_payload(),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing Idempotency-Key header."


def test_post_rejects_non_positive_amount_cents() -> None:
    for amount_cents in (0, -1):
        response = _client(FakeDb(), _user()).post(
            "/imperium/vault/transactions",
            headers={"Idempotency-Key": f"vault-amount-{amount_cents}"},
            json=_payload(amount_cents=amount_cents),
        )

        assert response.status_code == 422


def test_post_rejects_invalid_transaction_type() -> None:
    response = _client(FakeDb(), _user()).post(
        "/imperium/vault/transactions",
        headers={"Idempotency-Key": "vault-invalid-type"},
        json=_payload(transaction_type="transfer"),
    )

    assert response.status_code == 422


def test_post_rejects_client_supplied_user_id() -> None:
    response = _client(FakeDb(), _user()).post(
        "/imperium/vault/transactions",
        headers={"Idempotency-Key": "vault-client-user"},
        json=_payload(user_id=str(uuid4())),
    )

    assert response.status_code == 422


def test_post_idempotent_same_key_and_payload_returns_same_response() -> None:
    current_user = _user()
    payload = _payload()
    response_body = {
        "id": str(uuid4()),
        "transaction_type": "income",
        "amount_cents": 123400,
        "currency": "EUR",
        "wallet": "cash",
        "occurred_at": "2026-05-25T09:30:00Z",
        "local_date": "2026-05-25",
        "timezone": "UTC",
        "category": "vtc",
        "source": "manual",
        "note": "Monday revenue",
        "external_ref": "bolt-shift-1",
        "is_reversal": False,
        "reversal_of_transaction_id": None,
        "reversal_reason": None,
        "created_at": "2026-05-25T09:31:00Z",
    }
    existing_key = _idempotency_for(current_user=current_user, payload=payload, response_body=response_body)
    db = FakeDb(scalar_results=[existing_key])

    response = _client(db, current_user).post(
        "/imperium/vault/transactions",
        headers={"Idempotency-Key": "vault-idem-1"},
        json=payload,
    )

    assert response.status_code == 200
    assert response.json() == response_body
    assert not any(isinstance(item, ImperiumVaultTransaction) for item in db.added)
    assert db.committed is False


def test_post_same_key_with_different_payload_returns_conflict() -> None:
    current_user = _user()
    first_payload = _payload(amount_cents=123400)
    existing_key = _idempotency_for(
        current_user=current_user,
        payload=first_payload,
        response_body={
            "id": str(uuid4()),
            "transaction_type": "income",
                "amount_cents": 123400,
                "currency": "EUR",
                "wallet": "cash",
                "occurred_at": "2026-05-25T09:30:00Z",
            "local_date": "2026-05-25",
            "timezone": "UTC",
            "category": "vtc",
            "source": "manual",
            "note": "Monday revenue",
                "external_ref": "bolt-shift-1",
                "is_reversal": False,
                "reversal_of_transaction_id": None,
                "reversal_reason": None,
                "created_at": "2026-05-25T09:31:00Z",
        },
    )
    db = FakeDb(scalar_results=[existing_key])

    response = _client(db, current_user).post(
        "/imperium/vault/transactions",
        headers={"Idempotency-Key": "vault-idem-1"},
        json=_payload(amount_cents=9999),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Idempotency key already used with different payload."
    assert db.rolled_back is True


def test_get_transactions_does_not_require_idempotency_and_is_user_scoped() -> None:
    current_user = _user()
    own = _transaction(
        current_user.id,
        occurred_at=datetime.now(UTC),
        transaction_type="expense",
        category="fuel",
        source="manual",
    )
    db = FakeDb(scalars_results=[[own]])

    response = _client(db, current_user).get(
        "/imperium/vault/transactions?limit=10&offset=0&transaction_type=expense&category=fuel&source=manual"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["id"] == str(own.id)
    assert body["safe_explanation"] == "Vault transactions for current user."
    query_text = str(db.queries[0])
    assert "imperium_vault_transactions.user_id" in query_text
    assert "imperium_vault_transactions.transaction_type" in query_text
    assert "imperium_vault_transactions.category" in query_text
    assert "imperium_vault_transactions.source" in query_text


def test_get_transactions_filters_category_source_and_type_independently() -> None:
    current_user = _user()

    for query_param, expected_column in (
        ("transaction_type=income", "imperium_vault_transactions.transaction_type"),
        ("category=vtc", "imperium_vault_transactions.category"),
        ("source=manual", "imperium_vault_transactions.source"),
    ):
        db = FakeDb(scalars_results=[[_transaction(current_user.id)]])

        response = _client(db, current_user).get(f"/imperium/vault/transactions?{query_param}")

        assert response.status_code == 200
        assert expected_column in str(db.queries[0])


def test_get_transactions_applies_occurred_range_and_stable_sort() -> None:
    current_user = _user()
    own = _transaction(current_user.id)
    db = FakeDb(scalars_results=[[own]])
    occurred_from = (datetime.now(UTC) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
    occurred_to = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    response = _client(db, current_user).get(
        f"/imperium/vault/transactions?occurred_from={occurred_from}&occurred_to={occurred_to}"
    )

    assert response.status_code == 200
    query_text = str(db.queries[0])
    assert "imperium_vault_transactions.occurred_at" in query_text
    assert "ORDER BY imperium_vault_transactions.occurred_at DESC" in query_text
    assert "imperium_vault_transactions.created_at DESC" in query_text
    assert "imperium_vault_transactions.id" in query_text


def test_get_transactions_respects_limit_offset_and_is_read_only() -> None:
    current_user = _user()
    db = FakeDb(scalars_results=[[_transaction(current_user.id)]])

    response = _client(db, current_user).get("/imperium/vault/transactions?limit=1&offset=2")

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 1
    assert body["offset"] == 2
    query_text = str(db.queries[0])
    assert "LIMIT" in query_text
    assert "OFFSET" in query_text
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False
    assert db.rolled_back is False


def test_get_transactions_rejects_naive_occurred_from() -> None:
    response = _client(FakeDb(scalars_results=[[]]), _user()).get(
        "/imperium/vault/transactions?occurred_from=2026-01-01T00:00:00"
    )

    assert response.status_code == 422


def test_imperium_vault_transaction_model_constraints_match_patch_9a() -> None:
    assert ImperiumVaultTransaction.__tablename__ == "imperium_vault_transactions"

    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in ImperiumVaultTransaction.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    amount_constraint = next(
        sql for name, sql in constraints.items() if name.endswith("imperium_vault_transactions_amount_positive")
    )
    type_constraint = next(
        sql
        for name, sql in constraints.items()
        if name.endswith("imperium_vault_transactions_transaction_type_check")
    )
    assert "amount_cents > 0" in amount_constraint
    assert "'income'" in type_constraint
    assert "'expense'" in type_constraint
    assert any(name.endswith("imperium_vault_transactions_currency_length_check") for name in constraints)
    assert "wallet" in ImperiumVaultTransaction.__table__.columns
    assert not any("wallet" in str(sql) for sql in constraints.values())

    index_names = {index.name for index in ImperiumVaultTransaction.__table__.indexes}
    assert "imperium_vault_transactions_user_occurred_at_idx" in index_names
    assert "imperium_vault_transactions_user_local_date_idx" in index_names
    assert "imperium_vault_transactions_user_transaction_type_idx" in index_names
