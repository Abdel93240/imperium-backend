from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.router import api_router
from app.models.imperium import ImperiumMission, ImperiumPathCheckIn, ImperiumPathHabit, ImperiumPulseEntry
from app.models.vault import ImperiumVaultTransaction


class FakeDb:
    def __init__(self, *, scalar_results=None, scalars_results=None) -> None:
        self.scalar_results = list(scalar_results or [])
        self.scalars_results = [list(result) for result in scalars_results] if scalars_results is not None else []
        self.added = []
        self.queries = []
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

    def scalar(self, query):
        self.queries.append(query)
        if self.scalar_results:
            return self.scalar_results.pop(0)
        return None

    def scalars(self, query):
        self.queries.append(query)
        if self.scalars_results:
            return self.scalars_results.pop(0)
        return []


def _user(user_id=None) -> SimpleNamespace:
    return SimpleNamespace(id=user_id or uuid4())


def _client(db: FakeDb, current_user: SimpleNamespace) -> TestClient:
    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _mission(user_id, **overrides) -> ImperiumMission:
    now = overrides.pop("created_at", datetime(2026, 5, 25, 8, 0, tzinfo=UTC))
    return ImperiumMission(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        title=overrides.pop("title", "Drive focused VTC block"),
        category=overrides.pop("category", "vtc"),
        domain=overrides.pop("domain", "business"),
        priority_level=overrides.pop("priority_level", 2),
        mission_type_category=overrides.pop("mission_type_category", "cat_a"),
        status=overrides.pop("status", "active"),
        planned_start_at=overrides.pop("planned_start_at", None),
        planned_end_at=overrides.pop("planned_end_at", None),
        started_at=overrides.pop("started_at", now),
        ended_at=overrides.pop("ended_at", None),
        created_at=now,
        updated_at=overrides.pop("updated_at", now),
    )


def _transaction(user_id, **overrides) -> ImperiumVaultTransaction:
    now = overrides.pop("occurred_at", datetime(2026, 5, 25, 10, 0, tzinfo=UTC))
    return ImperiumVaultTransaction(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        transaction_type=overrides.pop("transaction_type", "income"),
        amount_cents=overrides.pop("amount_cents", 1000),
        currency=overrides.pop("currency", "EUR"),
        occurred_at=now,
        local_date=overrides.pop("local_date", now.date()),
        timezone=overrides.pop("timezone", "UTC"),
        category=overrides.pop("category", "vtc"),
        source=overrides.pop("source", "manual"),
        note=overrides.pop("note", None),
        external_ref=overrides.pop("external_ref", None),
        created_at=overrides.pop("created_at", now),
        updated_at=overrides.pop("updated_at", now),
    )


def _habit(user_id, **overrides) -> ImperiumPathHabit:
    now = overrides.pop("created_at", datetime(2026, 5, 25, 6, 0, tzinfo=UTC))
    return ImperiumPathHabit(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        title=overrides.pop("title", "Fajr on time"),
        description=overrides.pop("description", None),
        domain=overrides.pop("domain", "worship"),
        frequency=overrides.pop("frequency", "daily"),
        is_active=overrides.pop("is_active", True),
        created_at=now,
        updated_at=overrides.pop("updated_at", now),
    )


def _check_in(user_id, habit_id, **overrides) -> ImperiumPathCheckIn:
    now = overrides.pop("created_at", datetime(2026, 5, 25, 6, 30, tzinfo=UTC))
    return ImperiumPathCheckIn(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        habit_id=habit_id,
        check_date=overrides.pop("check_date", date(2026, 5, 25)),
        status=overrides.pop("status", "done"),
        reason=overrides.pop("reason", None),
        note=overrides.pop("note", "Done"),
        created_at=now,
        updated_at=overrides.pop("updated_at", now),
    )


def _pulse_entry(user_id, **overrides) -> ImperiumPulseEntry:
    now = overrides.pop("created_at", datetime(2026, 5, 25, 7, 0, tzinfo=UTC))
    return ImperiumPulseEntry(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        entry_date=overrides.pop("entry_date", date(2026, 5, 25)),
        sleep_hours=overrides.pop("sleep_hours", Decimal("7.50")),
        energy_level=overrides.pop("energy_level", 8),
        fatigue_level=overrides.pop("fatigue_level", 3),
        weight_kg=overrides.pop("weight_kg", Decimal("91.20")),
        workout_done=overrides.pop("workout_done", True),
        workout_type=overrides.pop("workout_type", "street_workout"),
        notes=overrides.pop("notes", "Clean day"),
        created_at=now,
        updated_at=overrides.pop("updated_at", now),
    )


def _empty_dashboard_db() -> FakeDb:
    return FakeDb(scalar_results=[None], scalars_results=[[], [], []])


def _assert_no_user_id(value) -> None:
    if isinstance(value, dict):
        assert "user_id" not in value
        for child in value.values():
            _assert_no_user_id(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_user_id(child)


def test_dashboard_empty_returns_nulls_and_zero_sections() -> None:
    response = _client(_empty_dashboard_db(), _user()).get("/api/imperium/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["currency"] == "EUR"
    assert body["mission"] == {
        "active_mission": None,
        "safe_explanation": "No active mission found for current user.",
    }
    assert body["vault"] == {
        "currency": "EUR",
        "total_income_cents": 0,
        "total_expense_cents": 0,
        "net_cents": 0,
        "transaction_count": 0,
        "income_count": 0,
        "expense_count": 0,
        "safe_explanation": "Vault summary computed from current user's ledger transactions.",
    }
    assert body["path"]["items"] == []
    assert body["path"]["count"] == 0
    assert body["pulse"]["entry"] is None
    assert body["safe_explanation"] == "Imperium dashboard snapshot for current user."
    assert "current_mission" not in body
    assert "vault_week" not in body


def test_dashboard_returns_active_mission_for_current_user() -> None:
    current_user = _user()
    mission = _mission(current_user.id)
    db = FakeDb(scalar_results=[None], scalars_results=[[mission], [], []])

    response = _client(db, current_user).get("/api/imperium/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["mission"]["active_mission"]["id"] == str(mission.id)
    assert body["mission"]["active_mission"]["title"] == "Drive focused VTC block"
    assert "user_id" not in body["mission"]["active_mission"]
    assert "imperium_missions.user_id" in "\n".join(str(query) for query in db.queries)


def test_dashboard_returns_vault_summary_for_current_user_only() -> None:
    current_user = _user()
    other_user = _user()
    own_income = _transaction(current_user.id, transaction_type="income", amount_cents=9000)
    own_expense = _transaction(current_user.id, transaction_type="expense", amount_cents=2500)
    foreign = _transaction(other_user.id, transaction_type="income", amount_cents=999999)
    db = FakeDb(scalar_results=[None], scalars_results=[[], [own_income, own_expense], []])

    response = _client(db, current_user).get("/api/imperium/dashboard")

    assert response.status_code == 200
    body = response.json()["vault"]
    assert body["total_income_cents"] == 9000
    assert body["total_expense_cents"] == 2500
    assert body["net_cents"] == 6500
    assert body["transaction_count"] == 2
    assert foreign.amount_cents != body["total_income_cents"]
    assert "imperium_vault_transactions.user_id" in "\n".join(str(query) for query in db.queries)


def test_dashboard_returns_path_today_for_current_user_only() -> None:
    current_user = _user()
    other_user = _user()
    habit = _habit(current_user.id)
    check_in = _check_in(current_user.id, habit.id)
    foreign_habit = _habit(other_user.id, title="Foreign habit")
    db = FakeDb(scalar_results=[None], scalars_results=[[], [], [habit], [check_in]])

    response = _client(db, current_user).get("/api/imperium/dashboard")

    assert response.status_code == 200
    body = response.json()["path"]
    assert body["count"] == 1
    assert body["items"][0]["habit"]["title"] == "Fajr on time"
    assert body["items"][0]["check_in"]["status"] == "done"
    assert foreign_habit.title != body["items"][0]["habit"]["title"]
    query_text = "\n".join(str(query) for query in db.queries)
    assert "imperium_path_habits.user_id" in query_text
    assert "imperium_path_check_ins.user_id" in query_text


def test_dashboard_returns_pulse_today_for_current_user_only() -> None:
    current_user = _user()
    other_user = _user()
    entry = _pulse_entry(current_user.id, notes="Own pulse")
    foreign_entry = _pulse_entry(other_user.id, notes="Foreign pulse")
    db = FakeDb(scalar_results=[entry], scalars_results=[[], [], []])

    response = _client(db, current_user).get("/api/imperium/dashboard")

    assert response.status_code == 200
    body = response.json()["pulse"]
    assert body["entry"]["id"] == str(entry.id)
    assert body["entry"]["notes"] == "Own pulse"
    assert body["entry"]["notes"] != foreign_entry.notes
    assert "imperium_pulse_entries.user_id" in "\n".join(str(query) for query in db.queries)


def test_dashboard_date_query_param_is_propagated_to_path_and_pulse() -> None:
    current_user = _user()
    target_date = date(2026, 5, 24)
    habit = _habit(current_user.id)
    check_in = _check_in(current_user.id, habit.id, check_date=target_date)
    entry = _pulse_entry(current_user.id, entry_date=target_date)
    db = FakeDb(scalar_results=[entry], scalars_results=[[], [], [habit], [check_in]])

    response = _client(db, current_user).get("/api/imperium/dashboard?date=2026-05-24")

    assert response.status_code == 200
    body = response.json()
    assert body["date"] == "2026-05-24"
    assert body["path"]["date"] == "2026-05-24"
    assert body["path"]["items"][0]["check_in"]["check_date"] == "2026-05-24"
    assert body["pulse"]["date"] == "2026-05-24"
    assert body["pulse"]["entry"]["entry_date"] == "2026-05-24"


def test_dashboard_currency_query_param_is_propagated_to_vault_and_normalized_uppercase() -> None:
    current_user = _user()
    tx = _transaction(current_user.id, transaction_type="income", amount_cents=12000, currency="USD")
    db = FakeDb(scalar_results=[None], scalars_results=[[], [tx], []])

    response = _client(db, current_user).get("/api/imperium/dashboard?currency=usd")

    assert response.status_code == 200
    body = response.json()
    assert body["currency"] == "USD"
    assert body["vault"]["currency"] == "USD"
    assert body["vault"]["total_income_cents"] == 12000
    assert "imperium_vault_transactions.currency" in "\n".join(str(query) for query in db.queries)


def test_dashboard_invalid_currency_returns_422() -> None:
    response = _client(_empty_dashboard_db(), _user()).get("/api/imperium/dashboard?currency=EU1")

    assert response.status_code == 422


def test_dashboard_does_not_require_idempotency_key() -> None:
    response = _client(_empty_dashboard_db(), _user()).get("/api/imperium/dashboard")

    assert response.status_code == 200


def test_dashboard_is_read_only_and_creates_no_path_or_pulse_rows() -> None:
    current_user = _user()
    habit = _habit(current_user.id)
    db = FakeDb(scalar_results=[None], scalars_results=[[], [], [habit], []])

    response = _client(db, current_user).get("/api/imperium/dashboard")

    assert response.status_code == 200
    assert response.json()["path"]["items"][0]["check_in"] is None
    assert response.json()["pulse"]["entry"] is None
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False
    assert db.rolled_back is False


def test_dashboard_does_not_expose_user_id() -> None:
    current_user = _user()
    mission = _mission(current_user.id)
    tx = _transaction(current_user.id)
    habit = _habit(current_user.id)
    check_in = _check_in(current_user.id, habit.id)
    entry = _pulse_entry(current_user.id)
    db = FakeDb(scalar_results=[entry], scalars_results=[[mission], [tx], [habit], [check_in]])

    response = _client(db, current_user).get("/api/imperium/dashboard")

    assert response.status_code == 200
    _assert_no_user_id(response.json())
