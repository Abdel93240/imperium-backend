from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.imperium import ImperiumEvent
from app.services.imperium.event_readers import (
    DEFAULT_EVENT_READER_LIMIT,
    MAX_EVENT_READER_LIMIT,
    EventReadFilters,
    list_events_for_user,
    read_imperium_events,
)


class _Db:
    def __init__(self, scalars_result) -> None:
        self.scalars_result = scalars_result
        self.queries = []

    def scalars(self, query):
        self.queries.append(query)
        return self.scalars_result

    def add(self, obj) -> None:  # pragma: no cover - defensive guard
        raise AssertionError("list_events_for_user must not write to the database.")

    def flush(self) -> None:  # pragma: no cover - defensive guard
        raise AssertionError("list_events_for_user must not write to the database.")

    def commit(self) -> None:  # pragma: no cover - defensive guard
        raise AssertionError("list_events_for_user must not write to the database.")


def _query_text(query) -> str:
    return " ".join(str(query).lower().split())


def _query_params(query) -> dict:
    return query.compile().params


def _param_value(query, name_prefix: str):
    for name, value in _query_params(query).items():
        if name.startswith(name_prefix):
            return value
    raise AssertionError(f"Missing query parameter with prefix {name_prefix!r}.")


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


def test_list_events_for_user_requires_user_id() -> None:
    db = _Db([])

    with pytest.raises(ValueError, match="user_id is required"):
        list_events_for_user(db, user_id=None)  # type: ignore[arg-type]

    assert db.queries == []


def test_event_read_filters_requires_user_id() -> None:
    with pytest.raises(ValueError, match="user_id is required"):
        EventReadFilters(user_id=None)  # type: ignore[arg-type]


def test_event_read_filters_rejects_limit_above_max() -> None:
    with pytest.raises(ValueError, match="limit"):
        EventReadFilters(user_id=uuid4(), limit=MAX_EVENT_READER_LIMIT + 1)


def test_event_read_filters_rejects_negative_offset() -> None:
    with pytest.raises(ValueError, match="offset"):
        EventReadFilters(user_id=uuid4(), offset=-1)


def test_event_read_filters_accepts_valid_occurred_range() -> None:
    occurred_from = datetime(2026, 5, 26, 8, 40, tzinfo=UTC)
    occurred_to = datetime(2026, 5, 26, 9, 0, tzinfo=UTC)

    filters = EventReadFilters(
        user_id=uuid4(),
        occurred_from=occurred_from,
        occurred_to=occurred_to,
    )

    assert filters.occurred_from == occurred_from
    assert filters.occurred_to == occurred_to


def test_event_read_filters_accepts_equal_occurred_range() -> None:
    occurred_at = datetime(2026, 5, 26, 9, 0, tzinfo=UTC)

    filters = EventReadFilters(
        user_id=uuid4(),
        occurred_from=occurred_at,
        occurred_to=occurred_at,
    )

    assert filters.occurred_from == occurred_at
    assert filters.occurred_to == occurred_at


def test_event_read_filters_rejects_inverted_occurred_range() -> None:
    occurred_from = datetime(2026, 5, 26, 9, 1, tzinfo=UTC)
    occurred_to = datetime(2026, 5, 26, 9, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="occurred_from must be less than or equal to occurred_to"):
        EventReadFilters(
            user_id=uuid4(),
            occurred_from=occurred_from,
            occurred_to=occurred_to,
        )


@pytest.mark.parametrize(
    ("occurred_from", "occurred_to"),
    [
        (None, None),
        (datetime(2026, 5, 26, 8, 40, tzinfo=UTC), None),
        (None, datetime(2026, 5, 26, 9, 0, tzinfo=UTC)),
    ],
)
def test_event_read_filters_accepts_missing_occurred_bounds(occurred_from, occurred_to) -> None:
    filters = EventReadFilters(
        user_id=uuid4(),
        occurred_from=occurred_from,
        occurred_to=occurred_to,
    )

    assert filters.occurred_from == occurred_from
    assert filters.occurred_to == occurred_to


def test_list_events_for_user_is_always_scoped_to_user_id() -> None:
    user_id = uuid4()
    event = _event(user_id)
    db = _Db([event])

    items = list_events_for_user(db, user_id=user_id)

    assert items == [event]
    assert db.queries, "The helper must issue a read query."
    query = db.queries[0]
    assert "where imperium_events.user_id" in _query_text(query)
    assert _param_value(query, "user_id") == user_id


def test_list_events_for_user_applies_bounded_default_pagination() -> None:
    user_id = uuid4()
    db = _Db([])

    list_events_for_user(db, user_id=user_id)

    params = _query_params(db.queries[0])
    assert DEFAULT_EVENT_READER_LIMIT + 1 in params.values()
    assert 0 in params.values()


def test_list_events_for_user_applies_limit_and_offset() -> None:
    user_id = uuid4()
    db = _Db([])

    list_events_for_user(db, user_id=user_id, limit=25, offset=10)

    params = _query_params(db.queries[0])
    assert 26 in params.values()
    assert 10 in params.values()


def test_read_imperium_events_returns_stable_page_with_next_offset() -> None:
    user_id = uuid4()
    first = _event(user_id, id=uuid4())
    second = _event(user_id, id=uuid4())
    overflow = _event(user_id, id=uuid4())
    db = _Db([first, second, overflow])

    page = read_imperium_events(db, EventReadFilters(user_id=user_id, limit=2, offset=4))

    assert page.items == [first, second]
    assert page.limit == 2
    assert page.offset == 4
    assert page.has_more is True
    assert page.next_offset == 6
    assert (
        "order by imperium_events.occurred_at desc, "
        "imperium_events.created_at desc, imperium_events.id desc"
    ) in _query_text(db.queries[0])


def test_read_imperium_events_returns_no_next_offset_on_final_page() -> None:
    user_id = uuid4()
    event = _event(user_id)
    db = _Db([event])

    page = read_imperium_events(db, EventReadFilters(user_id=user_id, limit=2))

    assert page.items == [event]
    assert page.has_more is False
    assert page.next_offset is None


@pytest.mark.parametrize("limit", [0, -1, MAX_EVENT_READER_LIMIT + 1, True, 10.5, "10"])
def test_list_events_for_user_rejects_unsafe_limits(limit) -> None:
    db = _Db([])

    with pytest.raises(ValueError, match="limit"):
        list_events_for_user(db, user_id=uuid4(), limit=limit)

    assert db.queries == []


@pytest.mark.parametrize("offset", [-1, True, 1.5, "1"])
def test_list_events_for_user_rejects_unsafe_offsets(offset) -> None:
    db = _Db([])

    with pytest.raises(ValueError, match="offset"):
        list_events_for_user(db, user_id=uuid4(), offset=offset)

    assert db.queries == []


def test_list_events_for_user_filters_event_type() -> None:
    user_id = uuid4()
    db = _Db([])

    list_events_for_user(db, user_id=user_id, event_type="mission_started")

    query = db.queries[0]
    assert "imperium_events.event_type" in _query_text(query)
    assert _param_value(query, "event_type") == "mission_started"


def test_list_events_for_user_filters_source_module() -> None:
    user_id = uuid4()
    db = _Db([])

    list_events_for_user(db, user_id=user_id, source_module="mission")

    query = db.queries[0]
    assert "imperium_events.source_module" in _query_text(query)
    assert _param_value(query, "source_module") == "mission"


def test_list_events_for_user_filters_occurred_from_and_to() -> None:
    user_id = uuid4()
    occurred_from = datetime(2026, 5, 26, 8, 40, tzinfo=UTC)
    occurred_to = datetime(2026, 5, 26, 9, 0, tzinfo=UTC)
    db = _Db([])

    list_events_for_user(
        db,
        user_id=user_id,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
    )

    query = db.queries[0]
    query_text = _query_text(query)
    assert "imperium_events.occurred_at >=" in query_text
    assert "imperium_events.occurred_at <=" in query_text
    assert _param_value(query, "occurred_at") == occurred_from
    assert occurred_to in _query_params(query).values()


def test_list_events_for_user_uses_deterministic_order() -> None:
    user_id = uuid4()
    db = _Db([])

    list_events_for_user(db, user_id=user_id)

    assert (
        "order by imperium_events.occurred_at desc, "
        "imperium_events.created_at desc, imperium_events.id desc"
    ) in _query_text(db.queries[0])


def test_list_events_for_user_does_not_write_to_db() -> None:
    user_id = uuid4()
    event = _event(user_id)
    db = _Db([event])

    items = list_events_for_user(db, user_id=user_id)

    assert items == [event]
    assert len(db.queries) == 1


def test_list_events_for_user_keeps_two_users_strictly_isolated() -> None:
    first_user_id = uuid4()
    second_user_id = uuid4()
    first_db = _Db([_event(first_user_id)])
    second_db = _Db([_event(second_user_id)])

    list_events_for_user(first_db, user_id=first_user_id)
    list_events_for_user(second_db, user_id=second_user_id)

    assert _param_value(first_db.queries[0], "user_id") == first_user_id
    assert _param_value(second_db.queries[0], "user_id") == second_user_id
    assert _param_value(first_db.queries[0], "user_id") != _param_value(second_db.queries[0], "user_id")
