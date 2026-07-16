from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import vault
from app.models.event import Event
from app.models.toolbox import SignalValue
from app.models.vault import ImperiumVaultTransaction, PressureSnapshot, UpcomingExpense
from app.services.vault import pressure as pressure_service


class FakeDb:
    def __init__(self, *, scalars_results) -> None:
        self.scalars_results = [list(result) for result in scalars_results]
        self.added = []
        self.committed = False

    def add(self, obj) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()
        if hasattr(obj, "created_at") and getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(UTC)
        self.added.append(obj)

    def flush(self) -> None:
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = uuid4()

    def commit(self) -> None:
        self.committed = True

    def scalar(self, query):
        return None

    def scalars(self, query):
        if self.scalars_results:
            return self.scalars_results.pop(0)
        return []


def _client(db: FakeDb, current_user: SimpleNamespace) -> TestClient:
    app = FastAPI()
    app.include_router(vault.router, prefix="/vault")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def test_pressure_api_loads_db_inputs_and_publishes_snapshot_signal_event(monkeypatch) -> None:
    current_user = SimpleNamespace(id=uuid4())
    now = datetime(2026, 7, 16, 10, 0, tzinfo=UTC)
    transactions = [
        _transaction(current_user.id, amount_cents=50000, occurred_at=now),
        _transaction(
            current_user.id,
            transaction_type="expense",
            amount_cents=10000,
            wallet="bank",
            occurred_at=now,
        ),
    ]
    expenses = [
        UpcomingExpense(
            id=uuid4(),
            user_id=current_user.id,
            label_fr="Fuel",
            amount=Decimal("100.00"),
            due_date=date(2026, 7, 17),
            recurrence=None,
            category="fuel",
            wallet="bank",
            mandatory=True,
            active=True,
        )
    ]
    db = FakeDb(scalars_results=[transactions, expenses])
    monkeypatch.setattr(pressure_service, "get_parameter", lambda *_args, default=None: default)
    monkeypatch.setattr(pressure_service, "_recent_daily_capacity", lambda *_args, **_kwargs: Decimal("220.00"))

    response = _client(db, current_user).get("/vault/pressure")

    assert response.status_code == 200
    assert response.json()["score"] == 0
    assert response.json()["label"] == "safe"
    snapshot = next(item for item in db.added if isinstance(item, PressureSnapshot))
    assert snapshot.user_id == current_user.id
    assert snapshot.inputs_snapshot["fuel_required_next_days"] == "100.00"
    assert any(isinstance(item, SignalValue) and item.signal_code == "vault.pressure" for item in db.added)
    event = next(item for item in db.added if isinstance(item, Event))
    assert event.event_type == "finance.pressure.updated"
    assert event.payload == {"snapshot_id": str(snapshot.id), "score": 0, "label": "safe"}
    assert db.committed is True


def _transaction(user_id, **overrides) -> ImperiumVaultTransaction:
    occurred_at = overrides.pop("occurred_at", datetime(2026, 7, 16, 10, 0, tzinfo=UTC))
    return ImperiumVaultTransaction(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        transaction_type=overrides.pop("transaction_type", "income"),
        amount_cents=overrides.pop("amount_cents", 10000),
        currency=overrides.pop("currency", "EUR"),
        wallet=overrides.pop("wallet", "cash"),
        occurred_at=occurred_at,
        local_date=overrides.pop("local_date", occurred_at.date()),
        timezone=overrides.pop("timezone", "UTC"),
        category=overrides.pop("category", "vtc"),
        source=overrides.pop("source", "manual"),
        note=overrides.pop("note", None),
        external_ref=overrides.pop("external_ref", None),
        is_reversal=overrides.pop("is_reversal", False),
        reversal_of_transaction_id=overrides.pop("reversal_of_transaction_id", None),
        reversal_reason=overrides.pop("reversal_reason", None),
        created_at=overrides.pop("created_at", occurred_at),
        updated_at=overrides.pop("updated_at", occurred_at),
    )
