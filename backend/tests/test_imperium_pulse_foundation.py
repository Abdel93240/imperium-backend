import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.router import api_router
from app.api.v1.routes import imperium_pulse
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumPulseEntry
from app.schemas.pulse import PulseEntryCreate
from app.services.pulse.entries import _hash_request


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
    app.include_router(imperium_pulse.router, prefix="/imperium/pulse")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _entry(user_id, **overrides) -> ImperiumPulseEntry:
    now = datetime.now(UTC)
    return ImperiumPulseEntry(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        entry_date=overrides.pop("entry_date", date(2026, 5, 25)),
        sleep_hours=overrides.pop("sleep_hours", Decimal("7.50")),
        energy_level=overrides.pop("energy_level", 8),
        fatigue_level=overrides.pop("fatigue_level", 3),
        weight_kg=overrides.pop("weight_kg", Decimal("92.40")),
        workout_done=overrides.pop("workout_done", True),
        workout_type=overrides.pop("workout_type", "street_workout"),
        notes=overrides.pop("notes", "Good baseline day"),
        created_at=overrides.pop("created_at", now),
        updated_at=overrides.pop("updated_at", now),
    )


def _valid_payload(**overrides) -> dict:
    payload = {
        "entry_date": "2026-05-25",
        "sleep_hours": 7.5,
        "energy_level": 8,
        "fatigue_level": 3,
        "weight_kg": 92.4,
        "workout_done": True,
        "workout_type": "street_workout",
        "notes": "  Good baseline day  ",
    }
    payload.update(overrides)
    return payload


def test_create_pulse_entry_ok() -> None:
    current_user = _user()
    db = FakeDb()

    response = _client(db, current_user).post(
        "/imperium/pulse/entries",
        headers={"Idempotency-Key": "pulse-entry-create-1"},
        json=_valid_payload(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["entry_date"] == "2026-05-25"
    assert body["sleep_hours"] == 7.5
    assert body["energy_level"] == 8
    assert body["fatigue_level"] == 3
    assert body["weight_kg"] == 92.4
    assert body["workout_done"] is True
    assert body["workout_type"] == "street_workout"
    assert body["notes"] == "Good baseline day"
    assert "user_id" not in body
    entry = next(item for item in db.added if isinstance(item, ImperiumPulseEntry))
    assert entry.user_id == current_user.id
    assert entry.notes == "Good baseline day"
    assert any(isinstance(item, IdempotencyKey) for item in db.added)
    assert db.committed is True


def test_create_pulse_entry_requires_idempotency_key() -> None:
    response = _client(FakeDb(), _user()).post("/imperium/pulse/entries", json=_valid_payload())

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing Idempotency-Key header."


def test_create_pulse_entry_replays_same_key_and_payload() -> None:
    current_user = _user()
    created_at = datetime.now(UTC)
    payload = PulseEntryCreate.model_validate(_valid_payload())
    response_body = {
        "id": str(uuid4()),
        "entry_date": "2026-05-25",
        "sleep_hours": "7.50",
        "energy_level": 8,
        "fatigue_level": 3,
        "weight_kg": "92.40",
        "workout_done": True,
        "workout_type": "street_workout",
        "notes": "Good baseline day",
        "created_at": created_at.isoformat(),
        "updated_at": created_at.isoformat(),
    }
    db = FakeDb(
        scalar_results=[
            IdempotencyKey(
                id=uuid4(),
                user_id=current_user.id,
                idempotency_key="pulse-replay",
                request_method="POST",
                request_path="/imperium/pulse/entries",
                request_hash=_hash_request("pulse.entry.created", payload.model_dump(mode="json")),
                status="completed",
                response_status_code=201,
                response_body=response_body,
                created_at=created_at,
                updated_at=created_at,
            )
        ]
    )

    response = _client(db, current_user).post(
        "/imperium/pulse/entries",
        headers={"Idempotency-Key": "pulse-replay"},
        json=_valid_payload(),
    )

    assert response.status_code == 200
    assert response.json()["id"] == response_body["id"]
    assert not any(isinstance(item, ImperiumPulseEntry) for item in db.added)
    assert db.committed is False


def test_create_pulse_entry_same_key_different_payload_returns_409() -> None:
    current_user = _user()
    created_at = datetime.now(UTC)
    original_payload = PulseEntryCreate.model_validate(_valid_payload(energy_level=8))
    db = FakeDb(
        scalar_results=[
            IdempotencyKey(
                id=uuid4(),
                user_id=current_user.id,
                idempotency_key="pulse-conflict-key",
                request_method="POST",
                request_path="/imperium/pulse/entries",
                request_hash=_hash_request("pulse.entry.created", original_payload.model_dump(mode="json")),
                status="completed",
                response_status_code=201,
                response_body={},
                created_at=created_at,
                updated_at=created_at,
            )
        ]
    )

    response = _client(db, current_user).post(
        "/imperium/pulse/entries",
        headers={"Idempotency-Key": "pulse-conflict-key"},
        json=_valid_payload(energy_level=9),
    )

    assert response.status_code == 409
    assert "different payload" in response.json()["detail"]
    assert db.rolled_back is True
    assert not any(isinstance(item, ImperiumPulseEntry) for item in db.added)


def test_create_pulse_entry_duplicate_entry_date_other_key_returns_409() -> None:
    current_user = _user()
    existing = _entry(current_user.id)
    db = FakeDb(scalar_results=[None, existing])

    response = _client(db, current_user).post(
        "/imperium/pulse/entries",
        headers={"Idempotency-Key": "pulse-duplicate-date"},
        json=_valid_payload(),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Pulse entry already exists for this date."
    assert db.rolled_back is True
    assert not any(isinstance(item, ImperiumPulseEntry) for item in db.added)


def test_create_pulse_entry_rejects_missing_business_field() -> None:
    db = FakeDb()

    response = _client(db, _user()).post(
        "/imperium/pulse/entries",
        headers={"Idempotency-Key": "pulse-no-business-field"},
        json={"entry_date": "2026-05-25"},
    )

    assert response.status_code == 422
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_create_pulse_entry_rejects_client_user_id() -> None:
    db = FakeDb()

    response = _client(db, _user()).post(
        "/imperium/pulse/entries",
        headers={"Idempotency-Key": "pulse-client-user-id"},
        json={**_valid_payload(), "user_id": str(uuid4())},
    )

    assert response.status_code == 422
    assert db.added == []


def test_create_pulse_entry_validates_energy_and_fatigue() -> None:
    db = FakeDb()
    client = _client(db, _user())

    low_energy = client.post(
        "/imperium/pulse/entries",
        headers={"Idempotency-Key": "pulse-low-energy"},
        json=_valid_payload(energy_level=0),
    )
    high_fatigue = client.post(
        "/imperium/pulse/entries",
        headers={"Idempotency-Key": "pulse-high-fatigue"},
        json=_valid_payload(fatigue_level=11),
    )

    assert low_energy.status_code == 422
    assert high_fatigue.status_code == 422
    assert db.added == []


def test_create_pulse_entry_validates_sleep_hours() -> None:
    db = FakeDb()
    response = _client(db, _user()).post(
        "/imperium/pulse/entries",
        headers={"Idempotency-Key": "pulse-invalid-sleep"},
        json=_valid_payload(sleep_hours=24.25),
    )

    assert response.status_code == 422
    assert db.added == []


def test_create_pulse_entry_validates_weight_kg() -> None:
    db = FakeDb()
    response = _client(db, _user()).post(
        "/imperium/pulse/entries",
        headers={"Idempotency-Key": "pulse-invalid-weight"},
        json=_valid_payload(weight_kg=0),
    )

    assert response.status_code == 422
    assert db.added == []


def test_create_pulse_entry_rejects_workout_type_when_workout_done_false() -> None:
    db = FakeDb()
    response = _client(db, _user()).post(
        "/imperium/pulse/entries",
        headers={"Idempotency-Key": "pulse-workout-type-conflict"},
        json=_valid_payload(workout_done=False, workout_type="street_workout"),
    )

    assert response.status_code == 422
    assert db.added == []


def test_list_pulse_entries_user_scoped() -> None:
    current_user = _user()
    entry = _entry(current_user.id)
    db = FakeDb(scalars_results=[[entry]])

    response = _client(db, current_user).get(
        "/imperium/pulse/entries?date_from=2026-05-01&date_to=2026-05-31&limit=50&offset=0"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert body["safe_explanation"] == "Pulse entries for current user."
    assert body["items"][0]["id"] == str(entry.id)
    query_text = "\n".join(str(query) for query in db.queries)
    assert "imperium_pulse_entries.user_id" in query_text
    assert "imperium_pulse_entries.entry_date" in query_text
    assert db.flushed is False
    assert db.committed is False


def test_get_pulse_entry_detail_non_owned_returns_404() -> None:
    db = FakeDb()
    entry_id = uuid4()

    response = _client(db, _user()).get(f"/imperium/pulse/entries/{entry_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Pulse entry not found."
    query_text = "\n".join(str(query) for query in db.queries)
    assert "imperium_pulse_entries.id" in query_text
    assert "imperium_pulse_entries.user_id" in query_text
    assert db.flushed is False
    assert db.committed is False


def test_pulse_get_routes_are_read_only_and_do_not_require_idempotency_key() -> None:
    route_text = Path(str(imperium_pulse.__file__)).read_text(encoding="utf-8")
    list_section = route_text.split("def list_pulse_entries_route", 1)[1].split("def get_pulse_entry_route", 1)[0]
    detail_section = route_text.split("def get_pulse_entry_route", 1)[1].split("def _validate_date_range", 1)[0]

    assert "Idempotency-Key" not in list_section
    assert "Idempotency-Key" not in detail_section
    assert ".add(" not in list_section
    assert ".flush(" not in list_section
    assert ".commit(" not in list_section
    assert ".add(" not in detail_section
    assert ".flush(" not in detail_section
    assert ".commit(" not in detail_section


def test_pulse_router_is_mounted_under_api_imperium_pulse() -> None:
    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    paths = {getattr(route, "path", None): route for route in app.routes}

    assert "/api/imperium/pulse/entries" in paths


def test_pulse_foundation_introduces_no_ai_n8n_pgvector_embedding_memory_calendar_scoring_or_coaching() -> None:
    files = [
        "app/api/v1/routes/imperium_pulse.py",
        "app/schemas/pulse.py",
        "app/services/pulse/entries.py",
    ]
    forbidden_patterns = [
        r"\bai\b",
        r"app\.services\.ai",
        r"app\.models\.ai",
        "n8n",
        "pgvector",
        "embedding",
        "memory",
        "calendar",
        "score",
        "scoring",
        "coach",
        "coaching",
        "mission",
        "vault",
        "imperium_path",
        r"app\.services\.path",
        r"app\.models\.path",
    ]
    combined = "\n".join(Path(file_path).read_text(encoding="utf-8").lower() for file_path in files)

    for pattern in forbidden_patterns:
        assert re.search(pattern, combined) is None
