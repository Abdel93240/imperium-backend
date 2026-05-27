from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.router import api_router
from app.models.imperium import ImperiumEvent


class FakeDb:
    def __init__(self, *, scalar_results=None, scalars_result=None) -> None:
        self.scalar_results = list(scalar_results or [])
        self.scalars_result = scalars_result or []
        self.added = []
        self.queries = []
        self.committed = False
        self.rolled_back = False

    def add(self, obj) -> None:
        self.added.append(obj)

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
        return self.scalars_result


def _client(db: FakeDb, current_user: SimpleNamespace) -> TestClient:
    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _user(user_id=None) -> SimpleNamespace:
    return SimpleNamespace(id=user_id or uuid4())


def _event(user_id, **overrides) -> ImperiumEvent:
    now = overrides.pop("created_at", datetime(2026, 5, 26, 9, 0, tzinfo=UTC))
    occurred_at = overrides.pop("occurred_at", datetime(2026, 5, 26, 8, 45, tzinfo=UTC))
    event = ImperiumEvent(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        event_type=overrides.pop("event_type", "mission_started"),
        source_module=overrides.pop("source_module", "mission"),
        occurred_at=occurred_at,
        payload_json=overrides.pop("payload_json", {"mission_id": str(uuid4()), "note": "created"}),
        schema_version=overrides.pop("schema_version", "v1"),
        idempotency_key=overrides.pop("idempotency_key", "event-idem-1"),
        created_at=now,
        updated_at=overrides.pop("updated_at", now),
    )
    for key, value in overrides.items():
        setattr(event, key, value)
    return event


def _payload(**overrides) -> dict:
    payload = {
        "event_type": "mission_started",
        "source_module": "mission",
        "occurred_at": datetime(2026, 5, 26, 8, 45, tzinfo=UTC).isoformat(),
        "payload_json": {
            "mission_id": str(uuid4()),
            "note": "optional",
        },
        "schema_version": "v1",
    }
    payload.update(overrides)
    return payload


def _assert_no_user_id(value) -> None:
    if isinstance(value, dict):
        assert "user_id" not in value
        for child in value.values():
            _assert_no_user_id(child)
    elif isinstance(value, list):
        for item in value:
            _assert_no_user_id(item)


def test_create_imperium_event_requires_idempotency_key() -> None:
    response = _client(FakeDb(), _user()).post("/api/imperium/events", json=_payload())

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing Idempotency-Key header."


def test_create_imperium_event_appends_event_for_current_user() -> None:
    current_user = _user()
    db = FakeDb()

    response = _client(db, current_user).post(
        "/api/imperium/events",
        json=_payload(),
        headers={"Idempotency-Key": "imperium-event-1"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["safe_explanation"] == "Imperium event appended for current user."
    assert body["event"]["safe_explanation"] == "Imperium event record for current user."
    assert body["event"]["event_type"] == "mission_started"
    assert body["event"]["source_module"] == "mission"
    assert body["event"]["schema_version"] == "v1"
    assert body["event"]["payload_json"]["note"] == "optional"
    _assert_no_user_id(body)
    assert any(isinstance(item, ImperiumEvent) for item in db.added)
    assert db.committed is True


def test_create_imperium_event_rejects_top_level_user_id() -> None:
    response = _client(FakeDb(), _user()).post(
        "/api/imperium/events",
        json=_payload(user_id=str(uuid4())),
        headers={"Idempotency-Key": "imperium-event-top-user-id"},
    )

    assert response.status_code == 422
    assert "user_id" in response.text


def test_create_imperium_event_rejects_payload_json_containing_user_id() -> None:
    response = _client(FakeDb(), _user()).post(
        "/api/imperium/events",
        json=_payload(payload_json={"user_id": str(uuid4()), "mission_id": str(uuid4())}),
        headers={"Idempotency-Key": "imperium-event-payload-user-id"},
    )

    assert response.status_code == 422
    assert "payload_json" in response.text


def test_create_imperium_event_rejects_empty_event_type() -> None:
    response = _client(FakeDb(), _user()).post(
        "/api/imperium/events",
        json=_payload(event_type="   "),
        headers={"Idempotency-Key": "imperium-event-empty-type"},
    )

    assert response.status_code == 422
    assert "event_type" in response.text


def test_create_imperium_event_rejects_invalid_source_module() -> None:
    response = _client(FakeDb(), _user()).post(
        "/api/imperium/events",
        json=_payload(source_module="bad_module"),
        headers={"Idempotency-Key": "imperium-event-invalid-source"},
    )

    assert response.status_code == 422
    assert "source_module" in response.text


def test_create_imperium_event_rejects_naive_occurred_at() -> None:
    response = _client(FakeDb(), _user()).post(
        "/api/imperium/events",
        json=_payload(occurred_at="2026-05-26T08:45:00"),
        headers={"Idempotency-Key": "imperium-event-naive"},
    )

    assert response.status_code == 422
    assert "occurred_at" in response.text


def test_create_imperium_event_replays_same_payload_for_same_idempotency_key() -> None:
    current_user = _user()
    event = _event(current_user.id)
    db = FakeDb(scalar_results=[event])
    payload = _payload(
        occurred_at=event.occurred_at.isoformat(),
        payload_json=event.payload_json,
    )

    response = _client(db, current_user).post(
        "/api/imperium/events",
        json=payload,
        headers={"Idempotency-Key": event.idempotency_key},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["event"]["id"] == str(event.id)
    assert body["event"]["payload_json"] == event.payload_json
    _assert_no_user_id(body)
    assert db.added == []
    assert db.committed is False


def test_create_imperium_event_rejects_same_idempotency_key_with_different_payload() -> None:
    current_user = _user()
    event = _event(current_user.id)
    db = FakeDb(scalar_results=[event])

    response = _client(db, current_user).post(
        "/api/imperium/events",
        json=_payload(payload_json={"mission_id": str(uuid4()), "note": "changed"}),
        headers={"Idempotency-Key": event.idempotency_key},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Imperium event idempotency key already used with different payload."
    assert db.added == []
    assert db.committed is False
    assert db.rolled_back is True


def test_get_imperium_events_does_not_require_idempotency_key() -> None:
    current_user = _user()
    event = _event(current_user.id)
    db = FakeDb(scalars_result=[event])

    response = _client(db, current_user).get("/api/imperium/events")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == len(body["items"])
    assert "total_count" not in body
    assert body["items"][0]["id"] == str(event.id)
    assert body["items"][0]["created_at"] == body["items"][0]["updated_at"]


def test_list_imperium_events_is_user_scoped() -> None:
    current_user = _user()
    event = _event(current_user.id, event_type="mission_started", source_module="mission")
    db = FakeDb(scalars_result=[event])

    response = _client(db, current_user).get("/api/imperium/events?limit=1&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert body["safe_explanation"] == "Imperium events for current user."
    assert body["count"] == 1
    assert body["limit"] == 1
    assert body["offset"] == 0
    assert body["items"][0]["id"] == str(event.id)
    assert body["items"][0]["created_at"] == body["items"][0]["updated_at"]
    _assert_no_user_id(body)
    query_text = str(db.queries[-1])
    assert "imperium_events.user_id" in query_text
    assert "order by" in query_text.lower()


def test_list_imperium_events_filters_event_type() -> None:
    current_user = _user()
    event = _event(current_user.id, event_type="mission_completed")
    db = FakeDb(scalars_result=[event])

    response = _client(db, current_user).get("/api/imperium/events?event_type=mission_completed")

    assert response.status_code == 200
    assert response.json()["items"][0]["event_type"] == "mission_completed"
    query_text = str(db.queries[-1])
    assert "imperium_events.event_type" in query_text


def test_list_imperium_events_filters_source_module() -> None:
    current_user = _user()
    event = _event(current_user.id, source_module="vault")
    db = FakeDb(scalars_result=[event])

    response = _client(db, current_user).get("/api/imperium/events?source_module=vault")

    assert response.status_code == 200
    assert response.json()["items"][0]["source_module"] == "vault"
    query_text = str(db.queries[-1])
    assert "imperium_events.source_module" in query_text


def test_list_imperium_events_filters_occurred_from() -> None:
    current_user = _user()
    event = _event(current_user.id, occurred_at=datetime(2026, 5, 26, 11, 0, tzinfo=UTC))
    db = FakeDb(scalars_result=[event])

    response = _client(db, current_user).get("/api/imperium/events?occurred_from=2026-05-26T10:00:00Z")

    assert response.status_code == 200
    assert response.json()["items"][0]["occurred_at"] == event.occurred_at.isoformat().replace("+00:00", "Z")
    query_text = str(db.queries[-1])
    assert "imperium_events.occurred_at >=" in query_text


def test_list_imperium_events_filters_occurred_to() -> None:
    current_user = _user()
    event = _event(current_user.id, occurred_at=datetime(2026, 5, 26, 9, 0, tzinfo=UTC))
    db = FakeDb(scalars_result=[event])

    response = _client(db, current_user).get("/api/imperium/events?occurred_to=2026-05-26T10:00:00Z")

    assert response.status_code == 200
    assert response.json()["items"][0]["occurred_at"] == event.occurred_at.isoformat().replace("+00:00", "Z")
    query_text = str(db.queries[-1])
    assert "imperium_events.occurred_at <=" in query_text


def test_get_imperium_event_detail_returns_owned_event() -> None:
    current_user = _user()
    event = _event(current_user.id, event_type="vault_income_recorded", source_module="vault")
    db = FakeDb(scalar_results=[event])

    response = _client(db, current_user).get(f"/api/imperium/events/{event.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["safe_explanation"] == "Imperium event detail for current user."
    assert body["event"]["id"] == str(event.id)
    assert body["event"]["source_module"] == "vault"
    assert body["event"]["safe_explanation"] == "Imperium event record for current user."
    _assert_no_user_id(body)


def test_get_imperium_event_detail_returns_404_for_non_owned_event() -> None:
    current_user = _user()
    db = FakeDb(scalar_results=[None])

    response = _client(db, current_user).get(f"/api/imperium/events/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Imperium event not found."


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("put", "/api/imperium/events"),
        ("patch", f"/api/imperium/events/{uuid4()}"),
        ("delete", f"/api/imperium/events/{uuid4()}"),
    ],
)
def test_imperium_events_have_no_update_or_delete_routes(method: str, path: str) -> None:
    client = _client(FakeDb(), _user())

    response = client.request(method.upper(), path, json=_payload())

    assert response.status_code == 405


def test_get_imperium_event_detail_returns_404_for_missing_event() -> None:
    current_user = _user()
    db = FakeDb(scalar_results=[None])

    response = _client(db, current_user).get(f"/api/imperium/events/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Imperium event not found."
