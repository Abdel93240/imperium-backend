from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium
from app.models.event import Event
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumCalendarEvent
from app.schemas.imperium import CalendarEventCreate, CalendarEventRead, CalendarEventType
from app.services.imperium.calendar import create_calendar_event, list_calendar_events


class FakeDb:
    def __init__(self, *, scalar_results=None, scalars_result=None) -> None:
        self.scalar_results = list(scalar_results or [])
        self.scalars_result = scalars_result or []
        self.added = []
        self.deleted = []
        self.queries = []
        self.committed = False
        self.flushed = False
        self.rolled_back = False

    def add(self, obj) -> None:
        self._prepare(obj)
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed = True
        for obj in self.added:
            self._prepare(obj)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def delete(self, obj) -> None:
        self.deleted.append(obj)

    def scalar(self, query):
        self.queries.append(query)
        if self.scalar_results:
            return self.scalar_results.pop(0)
        return None

    def scalars(self, query):
        self.queries.append(query)
        return self.scalars_result

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
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _payload(**overrides) -> dict:
    starts_at = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)
    payload = {
        "event_type": "event",
        "title": "Doctor appointment",
        "starts_at": starts_at.isoformat(),
        "ends_at": (starts_at + timedelta(hours=1)).isoformat(),
        "blocks_time": True,
        "location": "Paris",
        "notes": "Bring documents",
    }
    payload.update(overrides)
    return payload


def _calendar_event(user_id, **overrides) -> ImperiumCalendarEvent:
    now = datetime.now(UTC)
    starts_at = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)
    event = ImperiumCalendarEvent(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        event_type=overrides.pop("event_type", "event"),
        title=overrides.pop("title", "Doctor appointment"),
        starts_at=overrides.pop("starts_at", starts_at),
        ends_at=overrides.pop("ends_at", starts_at + timedelta(hours=1)),
        blocks_time=overrides.pop("blocks_time", True),
        location=overrides.pop("location", "Paris"),
        notes=overrides.pop("notes", None),
        created_at=now,
        updated_at=now,
    )
    for key, value in overrides.items():
        setattr(event, key, value)
    return event


def test_create_calendar_event() -> None:
    db = FakeDb()
    current_user = _user()
    client = _client(db, current_user)

    response = client.post(
        "/imperium/calendar/events",
        json=_payload(),
        headers={"Idempotency-Key": "calendar-create-1"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["event_type"] == "event"
    assert data["title"] == "Doctor appointment"
    assert data["user_id"] == str(current_user.id)
    assert any(isinstance(item, ImperiumCalendarEvent) for item in db.added)
    assert any(isinstance(item, Event) and item.event_type == "calendar.event.created" for item in db.added)
    assert any(isinstance(item, IdempotencyKey) for item in db.added)
    assert db.committed is True


def test_create_calendar_event_requires_idempotency() -> None:
    db = FakeDb()
    response = _client(db, _user()).post("/imperium/calendar/events", json=_payload())

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing Idempotency-Key header."


def test_calendar_event_validation_invalid_dates() -> None:
    starts_at = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)
    response = _client(FakeDb(), _user()).post(
        "/imperium/calendar/events",
        json=_payload(
            starts_at=starts_at.isoformat(),
            ends_at=(starts_at - timedelta(minutes=1)).isoformat(),
        ),
        headers={"Idempotency-Key": "calendar-invalid-dates"},
    )

    assert response.status_code == 422
    assert "ends_at" in response.text


def test_calendar_event_validation_invalid_type() -> None:
    response = _client(FakeDb(), _user()).post(
        "/imperium/calendar/events",
        json=_payload(event_type="blocked_period"),
        headers={"Idempotency-Key": "calendar-invalid-type"},
    )

    assert response.status_code == 422
    assert "event_type" in response.text


def test_calendar_event_list_user_scoped() -> None:
    current_user = _user()
    event = _calendar_event(current_user.id, event_type="deadline")
    db = FakeDb(scalars_result=[event])

    result = list_calendar_events(
        db,
        current_user=current_user,
        starts_from=datetime(2026, 6, 1, tzinfo=UTC),
        starts_to=datetime(2026, 6, 2, tzinfo=UTC),
        event_type=CalendarEventType.deadline,
    )

    assert result == [event]
    query_text = str(db.queries[-1])
    assert "imperium_calendar_events.user_id" in query_text
    assert "imperium_calendar_events.starts_at >=" in query_text
    assert "imperium_calendar_events.starts_at <=" in query_text
    assert "imperium_calendar_events.event_type" in query_text


def test_delete_calendar_event() -> None:
    current_user = _user()
    event = _calendar_event(current_user.id)
    db = FakeDb(scalar_results=[event])
    client = _client(db, current_user)

    response = client.delete(f"/imperium/calendar/events/{event.id}")

    assert response.status_code == 200
    assert response.json() == {"id": str(event.id), "status": "deleted"}
    assert db.deleted == [event]
    assert db.committed is True


def test_delete_calendar_event_other_user_not_found() -> None:
    response = _client(FakeDb(scalar_results=[None]), _user()).delete(f"/imperium/calendar/events/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Calendar event not found."


def test_calendar_event_create_idempotent_replay() -> None:
    current_user = _user()
    event = _calendar_event(current_user.id)
    response_body = CalendarEventRead.model_validate(event).model_dump(mode="json")
    existing_key = IdempotencyKey(
        user_id=current_user.id,
        idempotency_key="calendar-replay-1",
        request_method="POST",
        request_path="/imperium/calendar/events",
        request_hash="",
        response_status_code=201,
        response_body=response_body,
    )
    payload = _payload()
    normalized_payload = CalendarEventCreate.model_validate(payload).model_dump(mode="json")
    request_hash = create_calendar_event.__globals__["_hash_request"]("calendar.event.created", normalized_payload)
    existing_key.request_hash = request_hash
    db = FakeDb(scalar_results=[existing_key])

    response = _client(db, current_user).post(
        "/imperium/calendar/events",
        json=payload,
        headers={"Idempotency-Key": "calendar-replay-1"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(event.id)
    assert db.added == []
    assert db.committed is False
