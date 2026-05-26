from datetime import UTC, datetime
from uuid import uuid4

from app.models.imperium import ImperiumEvent
from app.services.imperium.event_readers import list_events_for_user


class _Db:
    def __init__(self, scalars_result) -> None:
        self.scalars_result = scalars_result
        self.queries = []
        self.added = []
        self.flushed = False
        self.committed = False

    def scalars(self, query):
        self.queries.append(query)
        return self.scalars_result

    def add(self, obj) -> None:  # pragma: no cover - defensive guard
        raise AssertionError("list_events_for_user must not write to the database.")

    def flush(self) -> None:  # pragma: no cover - defensive guard
        raise AssertionError("list_events_for_user must not write to the database.")

    def commit(self) -> None:  # pragma: no cover - defensive guard
        raise AssertionError("list_events_for_user must not write to the database.")


def _event(user_id, **overrides) -> ImperiumEvent:
    occurred_at = overrides.pop("occurred_at", datetime(2026, 5, 26, 8, 45, tzinfo=UTC))
    created_at = overrides.pop("created_at", datetime(2026, 5, 26, 9, 0, tzinfo=UTC))
    event = ImperiumEvent(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        event_type=overrides.pop("event_type", "mission_started"),
        source_module=overrides.pop("source_module", "mission"),
        occurred_at=occurred_at,
        payload_json=overrides.pop("payload_json", {"mission_id": str(uuid4())}),
        schema_version=overrides.pop("schema_version", "v1"),
        idempotency_key=overrides.pop("idempotency_key", "event-idem-1"),
        created_at=created_at,
        updated_at=overrides.pop("updated_at", created_at),
    )
    for key, value in overrides.items():
        setattr(event, key, value)
    return event


def test_list_events_for_user_filters_and_orders_without_writing() -> None:
    user_id = uuid4()
    first = _event(
        user_id,
        id=uuid4(),
        event_type="mission_started",
        source_module="mission",
        occurred_at=datetime(2026, 5, 26, 8, 45, tzinfo=UTC),
        created_at=datetime(2026, 5, 26, 9, 0, tzinfo=UTC),
    )
    second = _event(
        user_id,
        id=uuid4(),
        event_type="mission_started",
        source_module="mission",
        occurred_at=datetime(2026, 5, 26, 8, 50, tzinfo=UTC),
        created_at=datetime(2026, 5, 26, 9, 5, tzinfo=UTC),
    )
    db = _Db([second, first])

    items = list_events_for_user(
        db,
        user_id=user_id,
        event_type="mission_started",
        source_module="mission",
        occurred_from=datetime(2026, 5, 26, 8, 40, tzinfo=UTC),
        occurred_to=datetime(2026, 5, 26, 9, 0, tzinfo=UTC),
        limit=25,
        offset=10,
    )

    assert items == [second, first]
    assert db.queries, "The helper must issue a read query."
    query_text = str(db.queries[0]).lower()
    assert "imperium_events.user_id" in query_text
    assert "imperium_events.event_type" in query_text
    assert "imperium_events.source_module" in query_text
    assert "imperium_events.occurred_at >= " in query_text
    assert "imperium_events.occurred_at <= " in query_text
    assert "order by" in query_text
