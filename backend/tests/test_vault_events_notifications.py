from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.models.enums import PrivacyLevel, SourceApp
from app.models.event import Event
from app.models.toolbox import SignalValue
from app.models.vault import PressureSnapshot, UpcomingExpense
from app.services.vault import upcoming as upcoming_service
from app.services.vault.pressure import PressureInputs, compute_pressure, publish_pressure_result


class FakeDb:
    def __init__(self, scalar_result=None, scalars_results=None):
        self.scalar_result = scalar_result
        self.scalars_results = [list(result) for result in (scalars_results or [])]
        self.added = []
        self.committed = False

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()
        if hasattr(obj, "created_at") and getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(UTC)
        self.added.append(obj)

    def flush(self):
        pass

    def commit(self):
        self.committed = True

    def scalar(self, query):
        return self.scalar_result

    def scalars(self, query):
        if self.scalars_results:
            return self.scalars_results.pop(0)
        return []


def test_pressure_publication_writes_snapshot_signal_and_e2_event() -> None:
    user = SimpleNamespace(id=uuid4())
    parent = Event(
        id=uuid4(),
        event_id="evt_parent",
        event_type="finance.transaction.created",
        schema_version="1.0",
        occurred_at=datetime.now(UTC),
        received_at=datetime.now(UTC),
        source_app=SourceApp.vault,
        user_id=user.id,
        idempotency_key="parent",
        correlation_id="corr_parent",
        causation_id=None,
        depth=1,
        privacy_level=PrivacyLevel.high,
        payload={},
    )
    db = FakeDb(scalar_result=parent)
    result = compute_pressure(PressureInputs(upcoming_required_expenses=Decimal("200"), number_of_remaining_work_days=2))

    publish_pressure_result(db, current_user=user, result=result, causation_event_id="evt_parent")

    assert any(isinstance(item, PressureSnapshot) for item in db.added)
    assert any(isinstance(item, SignalValue) and item.signal_code == "vault.pressure" for item in db.added)
    event = next(item for item in db.added if isinstance(item, Event))
    assert event.event_type == "finance.pressure.updated"
    assert event.causation_id == "evt_parent"
    assert event.correlation_id == "corr_parent"
    assert event.depth == 2
    assert db.committed is True


def test_expenses_horizon_notifications_j7_and_j1_red_are_emitted(monkeypatch) -> None:
    sent = []

    def fake_notify(db, *, severity, domain, message_fr, ref=None):
        sent.append((severity, domain, ref))
        return object()

    monkeypatch.setattr(upcoming_service, "notify", fake_notify)
    today = date(2026, 7, 16)
    j7 = UpcomingExpense(
        id=uuid4(),
        label_fr="Assurance",
        amount=Decimal("120.00"),
        due_date=today + timedelta(days=7),
        recurrence=None,
        category="assurance pro",
        wallet="bank",
        mandatory=True,
        active=True,
    )
    j1 = UpcomingExpense(
        id=uuid4(),
        label_fr="Loyer",
        amount=Decimal("900.00"),
        due_date=today + timedelta(days=1),
        recurrence=None,
        category="loyer",
        wallet="bank",
        mandatory=True,
        active=True,
    )
    db = FakeDb(scalars_results=[[j7, j1], []])
    ctx = SimpleNamespace(db=db, items_in=None, items_out=None, detail=None, cursor_ts=None)
    window = SimpleNamespace(to_ts=datetime(2026, 7, 16, 6, 0, tzinfo=UTC))

    upcoming_service.expenses_horizon_job(ctx, window)

    assert ("normal", "vault", ("upcoming_expense", j7.id)) in sent
    assert ("red", "vault", ("upcoming_expense", j1.id)) in sent
    assert ctx.items_out == 2
