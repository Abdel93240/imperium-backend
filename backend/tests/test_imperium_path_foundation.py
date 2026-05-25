from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium_path
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumPathCheckIn, ImperiumPathHabit
from app.schemas.path import PathHabitCreate
from app.services.path.habits import _hash_request


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
    app.include_router(imperium_path.router, prefix="/imperium/path")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _habit(user_id, **overrides) -> ImperiumPathHabit:
    now = datetime.now(UTC)
    return ImperiumPathHabit(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        title=overrides.pop("title", "Fajr on time"),
        description=overrides.pop("description", None),
        domain=overrides.pop("domain", "worship"),
        frequency=overrides.pop("frequency", "daily"),
        is_active=overrides.pop("is_active", True),
        created_at=overrides.pop("created_at", now),
        updated_at=overrides.pop("updated_at", now),
    )


def _check_in(user_id, habit_id, **overrides) -> ImperiumPathCheckIn:
    now = datetime.now(UTC)
    return ImperiumPathCheckIn(
        id=overrides.pop("id", uuid4()),
        user_id=user_id,
        habit_id=habit_id,
        check_date=overrides.pop("check_date", date(2026, 5, 25)),
        status=overrides.pop("status", "done"),
        reason=overrides.pop("reason", None),
        note=overrides.pop("note", "Completed after prayer"),
        created_at=overrides.pop("created_at", now),
        updated_at=overrides.pop("updated_at", now),
    )


def test_create_path_habit_ok() -> None:
    current_user = _user()
    db = FakeDb()

    response = _client(db, current_user).post(
        "/imperium/path/habits",
        headers={"Idempotency-Key": "path-habit-create-1"},
        json={
            "title": "  Fajr on time  ",
            "description": " Wake before Fajr ",
            "domain": "worship",
            "frequency": "daily",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Fajr on time"
    assert body["description"] == "Wake before Fajr"
    assert body["domain"] == "worship"
    assert body["frequency"] == "daily"
    assert body["is_active"] is True
    assert "user_id" not in body
    habit = next(item for item in db.added if isinstance(item, ImperiumPathHabit))
    assert habit.user_id == current_user.id
    assert habit.title == "Fajr on time"
    assert any(isinstance(item, IdempotencyKey) for item in db.added)
    assert db.committed is True


def test_create_path_habit_requires_idempotency_key() -> None:
    response = _client(FakeDb(), _user()).post(
        "/imperium/path/habits",
        json={"title": "Fajr on time", "domain": "worship", "frequency": "daily"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing Idempotency-Key header."


def test_create_path_habit_rejects_empty_title() -> None:
    db = FakeDb()

    response = _client(db, _user()).post(
        "/imperium/path/habits",
        headers={"Idempotency-Key": "path-habit-empty-title"},
        json={"title": "   ", "domain": "worship", "frequency": "daily"},
    )

    assert response.status_code == 422
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_create_path_habit_rejects_client_user_id() -> None:
    db = FakeDb()

    response = _client(db, _user()).post(
        "/imperium/path/habits",
        headers={"Idempotency-Key": "path-habit-client-user-id"},
        json={
            "user_id": str(uuid4()),
            "title": "Fajr on time",
            "domain": "worship",
            "frequency": "daily",
        },
    )

    assert response.status_code == 422
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_create_path_habit_replays_same_idempotency_key() -> None:
    current_user = _user()
    created_at = datetime.now(UTC)
    response_body = {
        "id": str(uuid4()),
        "title": "Fajr on time",
        "description": None,
        "domain": "worship",
        "frequency": "daily",
        "is_active": True,
        "created_at": created_at.isoformat(),
        "updated_at": created_at.isoformat(),
    }
    payload = PathHabitCreate(title="Fajr on time", domain="worship", frequency="daily")
    db = FakeDb(
        scalar_results=[
            IdempotencyKey(
                id=uuid4(),
                user_id=current_user.id,
                idempotency_key="path-habit-replay",
                request_method="POST",
                request_path="/imperium/path/habits",
                request_hash=_hash_request("path.habit.created", payload.model_dump(mode="json")),
                status="completed",
                response_status_code=201,
                response_body=response_body,
                created_at=created_at,
                updated_at=created_at,
            )
        ]
    )

    response = _client(db, current_user).post(
        "/imperium/path/habits",
        headers={"Idempotency-Key": "path-habit-replay"},
        json={"title": "Fajr on time", "domain": "worship", "frequency": "daily"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == response_body["id"]
    assert not any(isinstance(item, ImperiumPathHabit) for item in db.added)


def test_archive_path_habit_active_ok_and_keeps_check_ins() -> None:
    current_user = _user()
    habit = _habit(current_user.id, is_active=True)
    check_in = _check_in(current_user.id, habit.id)
    db = FakeDb(scalar_results=[None, habit, check_in], scalars_results=[[check_in]])

    response = _client(db, current_user).post(
        f"/imperium/path/habits/{habit.id}/archive",
        headers={"Idempotency-Key": "path-habit-archive-1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["habit"]["id"] == str(habit.id)
    assert body["habit"]["is_active"] is False
    assert body["lifecycle_summary"]["status"] == "archived"
    assert body["lifecycle_summary"]["guardrails_checked"] == [
        "OWNERSHIP_CONFIRMED",
        "IDEMPOTENCY_KEY_ACCEPTED",
    ]
    assert body["lifecycle_summary"]["safe_explanation"] == "Path habit lifecycle updated without deleting history."
    assert habit.is_active is False
    assert any(isinstance(item, IdempotencyKey) for item in db.added)
    assert not any(isinstance(item, ImperiumPathCheckIn) for item in db.added)
    assert db.scalar_results == [check_in]
    assert db.scalars_results == [[check_in]]
    assert db.committed is True


def test_archive_path_habit_already_inactive_safe() -> None:
    current_user = _user()
    habit = _habit(current_user.id, is_active=False)
    db = FakeDb(scalar_results=[None, habit])

    response = _client(db, current_user).post(
        f"/imperium/path/habits/{habit.id}/archive",
        headers={"Idempotency-Key": "path-habit-archive-already-inactive"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["habit"]["is_active"] is False
    assert body["lifecycle_summary"]["status"] == "already_archived"
    assert habit.is_active is False
    assert db.committed is True


def test_reactivate_path_habit_inactive_ok() -> None:
    current_user = _user()
    habit = _habit(current_user.id, is_active=False)
    db = FakeDb(scalar_results=[None, habit])

    response = _client(db, current_user).post(
        f"/imperium/path/habits/{habit.id}/reactivate",
        headers={"Idempotency-Key": "path-habit-reactivate-1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["habit"]["is_active"] is True
    assert body["lifecycle_summary"]["status"] == "reactivated"
    assert habit.is_active is True
    assert db.committed is True


def test_reactivate_path_habit_already_active_safe() -> None:
    current_user = _user()
    habit = _habit(current_user.id, is_active=True)
    db = FakeDb(scalar_results=[None, habit])

    response = _client(db, current_user).post(
        f"/imperium/path/habits/{habit.id}/reactivate",
        headers={"Idempotency-Key": "path-habit-reactivate-already-active"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["habit"]["is_active"] is True
    assert body["lifecycle_summary"]["status"] == "already_active"
    assert habit.is_active is True


def test_path_habit_lifecycle_requires_idempotency_key() -> None:
    current_user = _user()
    habit = _habit(current_user.id)

    for path in (f"/imperium/path/habits/{habit.id}/archive", f"/imperium/path/habits/{habit.id}/reactivate"):
        response = _client(FakeDb(), current_user).post(path)

        assert response.status_code == 400
        assert response.json()["detail"] == "Missing Idempotency-Key header."


def test_path_habit_lifecycle_returns_404_for_missing_or_non_owned_habit() -> None:
    current_user = _user()
    missing_habit_id = uuid4()
    foreign_habit_id = uuid4()

    missing_response = _client(FakeDb(scalar_results=[None, None]), current_user).post(
        f"/imperium/path/habits/{missing_habit_id}/archive",
        headers={"Idempotency-Key": "path-habit-archive-missing"},
    )
    foreign_response = _client(FakeDb(scalar_results=[None, None]), current_user).post(
        f"/imperium/path/habits/{foreign_habit_id}/reactivate",
        headers={"Idempotency-Key": "path-habit-reactivate-foreign"},
    )

    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == "Path habit not found."
    assert foreign_response.status_code == 404
    assert foreign_response.json()["detail"] == "Path habit not found."


def test_path_habit_archive_replays_same_idempotency_key_and_conflicts_on_different_payload() -> None:
    current_user = _user()
    archived_habit = _habit(current_user.id, is_active=False)
    other_habit = _habit(current_user.id, is_active=True)
    created_at = datetime.now(UTC)
    archive_request_hash = _hash_request("path.habit.archived", {"habit_id": str(archived_habit.id)})
    archived_response_body = {
        "habit": {
            "id": str(archived_habit.id),
            "title": archived_habit.title,
            "description": archived_habit.description,
            "domain": archived_habit.domain,
            "frequency": archived_habit.frequency,
            "is_active": False,
            "created_at": archived_habit.created_at.isoformat().replace("+00:00", "Z"),
            "updated_at": archived_habit.updated_at.isoformat().replace("+00:00", "Z"),
        },
        "lifecycle_summary": {
            "status": "archived",
            "guardrails_checked": ["OWNERSHIP_CONFIRMED", "IDEMPOTENCY_KEY_ACCEPTED"],
            "safe_explanation": "Path habit lifecycle updated without deleting history.",
        },
    }
    existing_key = IdempotencyKey(
        id=uuid4(),
        user_id=current_user.id,
        idempotency_key="path-habit-archive-replay",
        request_method="POST",
        request_path=f"/imperium/path/habits/{archived_habit.id}/archive",
        request_hash=archive_request_hash,
        status="completed",
        response_status_code=200,
        response_body=archived_response_body,
        created_at=created_at,
        updated_at=created_at,
    )

    replay_db = FakeDb(scalar_results=[existing_key, archived_habit], scalars_results=[[other_habit]])
    replay_response = _client(replay_db, current_user).post(
        f"/imperium/path/habits/{archived_habit.id}/archive",
        headers={"Idempotency-Key": "path-habit-archive-replay"},
    )

    assert replay_response.status_code == 200
    assert replay_response.json() == archived_response_body
    assert replay_db.scalar_results == [archived_habit]
    assert replay_db.scalars_results == [[other_habit]]
    assert replay_db.added == []
    assert replay_db.committed is False

    conflict_db = FakeDb(scalar_results=[existing_key, other_habit], scalars_results=[[archived_habit]])
    conflict_response = _client(conflict_db, current_user).post(
        f"/imperium/path/habits/{other_habit.id}/archive",
        headers={"Idempotency-Key": "path-habit-archive-replay"},
    )

    assert conflict_response.status_code == 409
    assert conflict_response.json()["detail"] == "Idempotency key already used with different payload."
    assert conflict_db.scalar_results == [other_habit]
    assert conflict_db.scalars_results == [[archived_habit]]
    assert conflict_db.added == []
    assert conflict_db.rolled_back is True


def test_archive_then_reactivate_updates_today_view_visibility() -> None:
    current_user = _user()
    habit = _habit(current_user.id, is_active=True)

    archive_db = FakeDb(scalar_results=[None, habit])
    archive_response = _client(archive_db, current_user).post(
        f"/imperium/path/habits/{habit.id}/archive",
        headers={"Idempotency-Key": "path-habit-archive-today"},
    )
    assert archive_response.status_code == 200
    assert habit.is_active is False

    today_after_archive = _client(FakeDb(scalars_results=[[]]), current_user).get("/imperium/path/today")
    assert today_after_archive.status_code == 200
    assert today_after_archive.json()["count"] == 0

    reactivate_db = FakeDb(scalar_results=[None, habit])
    reactivate_response = _client(reactivate_db, current_user).post(
        f"/imperium/path/habits/{habit.id}/reactivate",
        headers={"Idempotency-Key": "path-habit-reactivate-today"},
    )
    assert reactivate_response.status_code == 200
    assert habit.is_active is True

    today_after_reactivate = _client(FakeDb(scalars_results=[[habit], []]), current_user).get("/imperium/path/today")
    assert today_after_reactivate.status_code == 200
    assert today_after_reactivate.json()["count"] == 1
    assert today_after_reactivate.json()["items"][0]["habit"]["id"] == str(habit.id)


def test_create_path_habit_conflicts_when_same_key_has_different_payload() -> None:
    current_user = _user()
    created_at = datetime.now(UTC)
    original_payload = PathHabitCreate(title="Fajr on time", domain="worship", frequency="daily")
    db = FakeDb(
        scalar_results=[
            IdempotencyKey(
                id=uuid4(),
                user_id=current_user.id,
                idempotency_key="path-habit-conflict",
                request_method="POST",
                request_path="/imperium/path/habits",
                request_hash=_hash_request("path.habit.created", original_payload.model_dump(mode="json")),
                status="completed",
                response_status_code=201,
                response_body={"id": str(uuid4())},
                created_at=created_at,
                updated_at=created_at,
            )
        ]
    )

    response = _client(db, current_user).post(
        "/imperium/path/habits",
        headers={"Idempotency-Key": "path-habit-conflict"},
        json={"title": "Isha on time", "domain": "worship", "frequency": "daily"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Idempotency key already used with different payload."
    assert not any(isinstance(item, ImperiumPathHabit) for item in db.added)
    assert db.rolled_back is True


def test_list_path_habits_user_scoped_and_no_idempotency_required() -> None:
    current_user = _user()
    habit = _habit(current_user.id)
    db = FakeDb(scalars_results=[[habit]])

    response = _client(db, current_user).get("/imperium/path/habits?is_active=true&domain=worship")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["title"] == "Fajr on time"
    assert body["safe_explanation"] == "Path habits/check-ins for current user."
    query_text = str(db.queries[0])
    assert "imperium_path_habits.user_id" in query_text
    assert "imperium_path_habits.is_active" in query_text
    assert "imperium_path_habits.domain" in query_text
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_create_path_check_in_ok() -> None:
    current_user = _user()
    habit = _habit(current_user.id)
    db = FakeDb(scalar_results=[None, habit, None])

    response = _client(db, current_user).post(
        f"/imperium/path/habits/{habit.id}/check-ins",
        headers={"Idempotency-Key": "path-check-in-1"},
        json={"check_date": "2026-05-25", "status": "done", "note": "Completed after prayer"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["habit_id"] == str(habit.id)
    assert body["check_date"] == "2026-05-25"
    assert body["status"] == "done"
    assert body["reason"] is None
    assert body["note"] == "Completed after prayer"
    check_in = next(item for item in db.added if isinstance(item, ImperiumPathCheckIn))
    assert check_in.user_id == current_user.id
    assert check_in.habit_id == habit.id
    assert db.committed is True


def test_create_path_check_in_rejects_inactive_habit() -> None:
    current_user = _user()
    habit = _habit(current_user.id, is_active=False)
    db = FakeDb(scalar_results=[None, habit])

    response = _client(db, current_user).post(
        f"/imperium/path/habits/{habit.id}/check-ins",
        headers={"Idempotency-Key": "path-check-in-inactive"},
        json={"check_date": "2026-05-25", "status": "done"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Path habit is inactive."
    assert not any(isinstance(item, ImperiumPathCheckIn) for item in db.added)


def test_create_path_check_in_returns_404_for_non_owned_habit() -> None:
    current_user = _user()
    habit_id = uuid4()
    db = FakeDb(scalar_results=[None, None])

    response = _client(db, current_user).post(
        f"/imperium/path/habits/{habit_id}/check-ins",
        headers={"Idempotency-Key": "path-check-in-non-owned"},
        json={"check_date": "2026-05-25", "status": "done"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Path habit not found."
    assert not any(isinstance(item, ImperiumPathCheckIn) for item in db.added)
    assert db.rolled_back is True


def test_create_path_check_in_requires_reason_when_missed() -> None:
    current_user = _user()
    habit = _habit(current_user.id)
    db = FakeDb(scalar_results=[None, habit])

    response = _client(db, current_user).post(
        f"/imperium/path/habits/{habit.id}/check-ins",
        headers={"Idempotency-Key": "path-check-in-missed"},
        json={"check_date": "2026-05-25", "status": "missed"},
    )

    assert response.status_code == 422
    assert "reason is required when status is missed" in response.text
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_create_path_check_in_rejects_done_with_reason() -> None:
    current_user = _user()
    habit = _habit(current_user.id)
    db = FakeDb(scalar_results=[None, habit])

    response = _client(db, current_user).post(
        f"/imperium/path/habits/{habit.id}/check-ins",
        headers={"Idempotency-Key": "path-check-in-done-with-reason"},
        json={"check_date": "2026-05-25", "status": "done", "reason": "No issue"},
    )

    assert response.status_code == 422
    assert "reason must be null when status is done" in response.text
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_create_path_check_in_rejects_invalid_reason_status_payloads_before_service() -> None:
    current_user = _user()
    habit = _habit(current_user.id)
    invalid_payloads = [
        (
            "path-check-in-invalid-done-reason",
            {"check_date": "2026-05-25", "status": "done", "reason": "Traffic delay"},
            "reason must be null when status is done",
        ),
        (
            "path-check-in-invalid-missed-no-reason",
            {"check_date": "2026-05-25", "status": "missed"},
            "reason is required when status is missed",
        ),
    ]

    for idempotency_key, payload, expected_error in invalid_payloads:
        db = FakeDb(scalar_results=[None, habit])

        response = _client(db, current_user).post(
            f"/imperium/path/habits/{habit.id}/check-ins",
            headers={"Idempotency-Key": idempotency_key},
            json=payload,
        )

        assert response.status_code == 422
        assert expected_error in response.text
        assert db.added == []
        assert db.flushed is False
        assert db.committed is False


def test_create_path_check_in_missed_with_reason_ok() -> None:
    current_user = _user()
    habit = _habit(current_user.id)
    db = FakeDb(scalar_results=[None, habit, None])

    response = _client(db, current_user).post(
        f"/imperium/path/habits/{habit.id}/check-ins",
        headers={"Idempotency-Key": "path-check-in-missed-with-reason"},
        json={"check_date": "2026-05-25", "status": "missed", "reason": "Driving shift overran"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "missed"
    assert body["reason"] == "Driving shift overran"
    check_in = next(item for item in db.added if isinstance(item, ImperiumPathCheckIn))
    assert check_in.user_id == current_user.id
    assert check_in.habit_id == habit.id


def test_create_path_check_in_conflicts_when_date_already_checked_with_other_key() -> None:
    current_user = _user()
    habit = _habit(current_user.id)
    existing = _check_in(current_user.id, habit.id)
    db = FakeDb(scalar_results=[None, habit, existing])

    response = _client(db, current_user).post(
        f"/imperium/path/habits/{habit.id}/check-ins",
        headers={"Idempotency-Key": "path-check-in-duplicate-date"},
        json={"check_date": "2026-05-25", "status": "done"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Path check-in already exists for this habit and date."


def test_create_path_check_in_replays_same_idempotency_key() -> None:
    current_user = _user()
    habit_id = uuid4()
    created_at = datetime.now(UTC)
    response_body = {
        "id": str(uuid4()),
        "habit_id": str(habit_id),
        "check_date": "2026-05-25",
        "status": "done",
        "reason": None,
        "note": "Completed after prayer",
        "created_at": created_at.isoformat(),
        "updated_at": created_at.isoformat(),
    }
    db = FakeDb(
        scalar_results=[
            IdempotencyKey(
                id=uuid4(),
                user_id=current_user.id,
                idempotency_key="path-check-in-replay",
                request_method="POST",
                request_path=f"/imperium/path/habits/{habit_id}/check-ins",
                request_hash=_hash_request(
                    "path.check_in.created",
                    {
                        "habit_id": str(habit_id),
                        "check_date": "2026-05-25",
                        "status": "done",
                        "reason": None,
                        "note": "Completed after prayer",
                    },
                ),
                status="completed",
                response_status_code=201,
                response_body=response_body,
                created_at=created_at,
                updated_at=created_at,
            )
        ]
    )

    response = _client(db, current_user).post(
        f"/imperium/path/habits/{habit_id}/check-ins",
        headers={"Idempotency-Key": "path-check-in-replay"},
        json={"check_date": "2026-05-25", "status": "done", "note": "Completed after prayer"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == response_body["id"]
    assert not any(isinstance(item, ImperiumPathCheckIn) for item in db.added)


def test_create_path_check_in_conflicts_when_same_key_has_different_payload() -> None:
    current_user = _user()
    habit_id = uuid4()
    created_at = datetime.now(UTC)
    db = FakeDb(
        scalar_results=[
            IdempotencyKey(
                id=uuid4(),
                user_id=current_user.id,
                idempotency_key="path-check-in-conflict",
                request_method="POST",
                request_path=f"/imperium/path/habits/{habit_id}/check-ins",
                request_hash=_hash_request(
                    "path.check_in.created",
                    {
                        "habit_id": str(habit_id),
                        "check_date": "2026-05-25",
                        "status": "done",
                        "reason": None,
                        "note": None,
                    },
                ),
                status="completed",
                response_status_code=201,
                response_body={"id": str(uuid4())},
                created_at=created_at,
                updated_at=created_at,
            )
        ]
    )

    response = _client(db, current_user).post(
        f"/imperium/path/habits/{habit_id}/check-ins",
        headers={"Idempotency-Key": "path-check-in-conflict"},
        json={"check_date": "2026-05-25", "status": "missed", "reason": "Driving shift overran"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Idempotency key already used with different payload."
    assert not any(isinstance(item, ImperiumPathCheckIn) for item in db.added)
    assert db.rolled_back is True


def test_list_path_check_ins_user_scoped_and_no_idempotency_required() -> None:
    current_user = _user()
    habit_id = uuid4()
    check_in = _check_in(current_user.id, habit_id)
    db = FakeDb(scalars_results=[[check_in]])

    response = _client(db, current_user).get(
        f"/imperium/path/check-ins?habit_id={habit_id}&status=done&date_from=2026-05-01&date_to=2026-05-31"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["habit_id"] == str(habit_id)
    assert body["safe_explanation"] == "Path habits/check-ins for current user."
    query_text = str(db.queries[0])
    assert "imperium_path_check_ins.user_id" in query_text
    assert "imperium_path_check_ins.habit_id" in query_text
    assert "imperium_path_check_ins.status" in query_text
    assert "imperium_path_check_ins.check_date" in query_text
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False
