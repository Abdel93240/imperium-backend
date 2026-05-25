from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium_vault
from app.models.idempotency import IdempotencyKey
from app.models.vault import ImperiumVaultTransaction
from app.schemas.vault import ImperiumVaultTransactionReverseRequest
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


def _transaction(user_id, **overrides) -> ImperiumVaultTransaction:
    now = datetime.now(UTC)
    occurred_at = overrides.pop("occurred_at", now)
    return ImperiumVaultTransaction(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        transaction_type=overrides.pop("transaction_type", "income"),
        amount_cents=overrides.pop("amount_cents", 123400),
        currency=overrides.pop("currency", "EUR"),
        occurred_at=occurred_at,
        local_date=overrides.pop("local_date", occurred_at.date()),
        timezone=overrides.pop("timezone", "UTC"),
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


def _reverse_payload(**overrides) -> dict:
    payload = {"reason": "Wrong amount entered"}
    payload.update(overrides)
    return payload


def _idempotency_for(*, current_user, transaction_id, payload: dict, response_body: dict) -> IdempotencyKey:
    request_payload = ImperiumVaultTransactionReverseRequest(**payload)
    return IdempotencyKey(
        id=uuid4(),
        user_id=current_user.id,
        idempotency_key="reverse-idem-1",
        request_method="POST",
        request_path=f"/imperium/vault/transactions/{transaction_id}/reverse",
        request_hash=_hash_request(
            "imperium.vault.transaction.reversed",
            {"transaction_id": str(transaction_id), "payload": request_payload.model_dump(mode="json")},
        ),
        status="completed",
        response_status_code=201,
        response_body=response_body,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def test_reverse_income_creates_expense_same_amount_and_currency() -> None:
    current_user = _user()
    original = _transaction(current_user.id, transaction_type="income", amount_cents=100000, currency="EUR")
    db = FakeDb(scalar_results=[None, original, None])

    response = _client(db, current_user).post(
        f"/imperium/vault/transactions/{original.id}/reverse",
        headers={"Idempotency-Key": "reverse-income-1"},
        json=_reverse_payload(reason=" duplicate revenue "),
    )

    assert response.status_code == 201
    body = response.json()
    reversal = next(item for item in db.added if isinstance(item, ImperiumVaultTransaction))
    assert reversal.transaction_type == "expense"
    assert reversal.amount_cents == original.amount_cents
    assert reversal.currency == original.currency
    assert reversal.category == original.category
    assert reversal.source == "reversal"
    assert reversal.external_ref is None
    assert reversal.is_reversal is True
    assert reversal.local_date == reversal.occurred_at.date()
    assert reversal.timezone == "UTC"
    assert reversal.reversal_of_transaction_id == original.id
    assert reversal.reversal_reason == "duplicate revenue"
    assert body["transaction"]["transaction_type"] == "expense"
    assert body["transaction"]["is_reversal"] is True
    assert body["transaction"]["reversal_of_transaction_id"] == str(original.id)
    assert body["reversal_summary"]["status"] == "reversed"
    assert body["reversal_summary"]["guardrails_checked"] == [
        "OWNERSHIP_CONFIRMED",
        "ORIGINAL_TRANSACTION_FOUND",
        "ORIGINAL_NOT_ALREADY_REVERSED",
        "IDEMPOTENCY_KEY_ACCEPTED",
    ]


def test_reverse_expense_creates_income_same_amount_and_currency() -> None:
    current_user = _user()
    original = _transaction(current_user.id, transaction_type="expense", amount_cents=5490, currency="EUR")
    db = FakeDb(scalar_results=[None, original, None])

    response = _client(db, current_user).post(
        f"/imperium/vault/transactions/{original.id}/reverse",
        headers={"Idempotency-Key": "reverse-expense-1"},
        json=_reverse_payload(),
    )

    assert response.status_code == 201
    reversal = next(item for item in db.added if isinstance(item, ImperiumVaultTransaction))
    assert reversal.transaction_type == "income"
    assert reversal.amount_cents == 5490
    assert reversal.currency == "EUR"


def test_reverse_reason_is_required_non_empty_and_rejects_unknown_fields() -> None:
    current_user = _user()
    transaction_id = uuid4()

    for payload in ({}, {"reason": ""}, {"reason": "   "}, {"reason": "ok", "amount_cents": 1}):
        response = _client(FakeDb(), current_user).post(
            f"/imperium/vault/transactions/{transaction_id}/reverse",
            headers={"Idempotency-Key": f"reverse-validation-{len(payload)}"},
            json=payload,
        )

        assert response.status_code == 422


def test_reverse_transaction_not_found_returns_404() -> None:
    current_user = _user()
    response = _client(FakeDb(scalar_results=[None, None]), current_user).post(
        f"/imperium/vault/transactions/{uuid4()}/reverse",
        headers={"Idempotency-Key": "reverse-missing-1"},
        json=_reverse_payload(),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Vault transaction not found."


def test_reverse_non_owned_transaction_returns_404() -> None:
    current_user = _user()
    foreign = _transaction(_user().id)
    response = _client(FakeDb(scalar_results=[None, None]), current_user).post(
        f"/imperium/vault/transactions/{foreign.id}/reverse",
        headers={"Idempotency-Key": "reverse-foreign-1"},
        json=_reverse_payload(),
    )

    assert response.status_code == 404


def test_reverse_requires_idempotency_key() -> None:
    response = _client(FakeDb(), _user()).post(
        f"/imperium/vault/transactions/{uuid4()}/reverse",
        json=_reverse_payload(),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing Idempotency-Key header."


def test_reverse_idempotent_same_key_and_payload_returns_same_response() -> None:
    current_user = _user()
    original_id = uuid4()
    response_body = {
        "transaction": {
            "id": str(uuid4()),
            "transaction_type": "expense",
            "amount_cents": 100000,
            "currency": "EUR",
            "occurred_at": "2026-05-25T10:00:00Z",
            "local_date": "2026-05-25",
            "timezone": "UTC",
            "category": "vtc",
            "source": "reversal",
            "note": f"Reversal of transaction {original_id}",
            "external_ref": None,
            "is_reversal": True,
            "reversal_of_transaction_id": str(original_id),
            "reversal_reason": "Wrong amount entered",
            "created_at": "2026-05-25T10:00:00Z",
        },
        "reversal_summary": {
            "status": "reversed",
            "original_transaction_id": str(original_id),
            "guardrails_checked": [
                "OWNERSHIP_CONFIRMED",
                "ORIGINAL_TRANSACTION_FOUND",
                "ORIGINAL_NOT_ALREADY_REVERSED",
                "IDEMPOTENCY_KEY_ACCEPTED",
            ],
            "safe_explanation": "Transaction reversed by appending an opposite ledger transaction.",
        },
    }
    existing_key = _idempotency_for(
        current_user=current_user,
        transaction_id=original_id,
        payload=_reverse_payload(),
        response_body=response_body,
    )
    db = FakeDb(scalar_results=[existing_key])

    response = _client(db, current_user).post(
        f"/imperium/vault/transactions/{original_id}/reverse",
        headers={"Idempotency-Key": "reverse-idem-1"},
        json=_reverse_payload(),
    )

    assert response.status_code == 200
    assert response.json() == response_body
    assert not any(isinstance(item, ImperiumVaultTransaction) for item in db.added)
    assert db.committed is False


def test_reverse_same_key_with_different_payload_returns_conflict() -> None:
    current_user = _user()
    original_id = uuid4()
    existing_key = _idempotency_for(
        current_user=current_user,
        transaction_id=original_id,
        payload=_reverse_payload(reason="first reason"),
        response_body={
            "transaction": {
                "id": str(uuid4()),
                "transaction_type": "expense",
                "amount_cents": 100000,
                "currency": "EUR",
                "occurred_at": "2026-05-25T10:00:00Z",
                "local_date": "2026-05-25",
                "timezone": "UTC",
                "category": "vtc",
                "source": "reversal",
                "note": f"Reversal of transaction {original_id}",
                "external_ref": None,
                "is_reversal": True,
                "reversal_of_transaction_id": str(original_id),
                "reversal_reason": "first reason",
                "created_at": "2026-05-25T10:00:00Z",
            },
            "reversal_summary": {
                "status": "reversed",
                "original_transaction_id": str(original_id),
                "guardrails_checked": [],
                "safe_explanation": "Transaction reversed by appending an opposite ledger transaction.",
            },
        },
    )
    db = FakeDb(scalar_results=[existing_key])

    response = _client(db, current_user).post(
        f"/imperium/vault/transactions/{original_id}/reverse",
        headers={"Idempotency-Key": "reverse-idem-1"},
        json=_reverse_payload(reason="second reason"),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Idempotency key already used with different payload."
    assert db.rolled_back is True


def test_reverse_new_key_on_already_reversed_transaction_returns_409() -> None:
    current_user = _user()
    original = _transaction(current_user.id)
    existing_reversal = _transaction(
        current_user.id,
        transaction_type="expense",
        is_reversal=True,
        reversal_of_transaction_id=original.id,
    )
    db = FakeDb(scalar_results=[None, original, existing_reversal])

    response = _client(db, current_user).post(
        f"/imperium/vault/transactions/{original.id}/reverse",
        headers={"Idempotency-Key": "reverse-again-1"},
        json=_reverse_payload(),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Vault transaction already has a reversal."
    assert not any(item is not existing_reversal and isinstance(item, ImperiumVaultTransaction) for item in db.added)


def test_reverse_original_transaction_is_not_modified() -> None:
    current_user = _user()
    original = _transaction(current_user.id, transaction_type="income", amount_cents=7777, source="manual")
    original_snapshot = {
        "transaction_type": original.transaction_type,
        "amount_cents": original.amount_cents,
        "currency": original.currency,
        "occurred_at": original.occurred_at,
        "local_date": original.local_date,
        "timezone": original.timezone,
        "category": original.category,
        "source": original.source,
        "note": original.note,
        "external_ref": original.external_ref,
        "is_reversal": original.is_reversal,
        "reversal_of_transaction_id": original.reversal_of_transaction_id,
        "reversal_reason": original.reversal_reason,
    }
    db = FakeDb(scalar_results=[None, original, None])

    response = _client(db, current_user).post(
        f"/imperium/vault/transactions/{original.id}/reverse",
        headers={"Idempotency-Key": "reverse-no-mutate-1"},
        json=_reverse_payload(),
    )

    assert response.status_code == 201
    assert {
        "transaction_type": original.transaction_type,
        "amount_cents": original.amount_cents,
        "currency": original.currency,
        "occurred_at": original.occurred_at,
        "local_date": original.local_date,
        "timezone": original.timezone,
        "category": original.category,
        "source": original.source,
        "note": original.note,
        "external_ref": original.external_ref,
        "is_reversal": original.is_reversal,
        "reversal_of_transaction_id": original.reversal_of_transaction_id,
        "reversal_reason": original.reversal_reason,
    } == original_snapshot


def test_reverse_reversal_transaction_returns_409() -> None:
    current_user = _user()
    reversal = _transaction(current_user.id, is_reversal=True, reversal_of_transaction_id=uuid4())
    db = FakeDb(scalar_results=[None, reversal])

    response = _client(db, current_user).post(
        f"/imperium/vault/transactions/{reversal.id}/reverse",
        headers={"Idempotency-Key": "reverse-a-reversal-1"},
        json=_reverse_payload(),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Vault reversal transactions cannot be reversed."


def test_get_list_and_detail_show_reversal_fields_without_user_id() -> None:
    current_user = _user()
    original_id = uuid4()
    reversal = _transaction(
        current_user.id,
        transaction_type="expense",
        is_reversal=True,
        reversal_of_transaction_id=original_id,
        reversal_reason="duplicate",
    )

    list_response = _client(FakeDb(scalars_results=[[reversal]]), current_user).get("/imperium/vault/transactions")
    detail_response = _client(FakeDb(scalar_results=[reversal]), current_user).get(
        f"/imperium/vault/transactions/{reversal.id}"
    )

    assert list_response.status_code == 200
    listed = list_response.json()["items"][0]
    assert listed["is_reversal"] is True
    assert listed["reversal_of_transaction_id"] == str(original_id)
    assert listed["reversal_reason"] == "duplicate"
    assert "user_id" not in listed

    assert detail_response.status_code == 200
    detailed = detail_response.json()["transaction"]
    assert detailed["is_reversal"] is True
    assert detailed["reversal_of_transaction_id"] == str(original_id)
    assert detailed["reversal_reason"] == "duplicate"
    assert "user_id" not in detailed
