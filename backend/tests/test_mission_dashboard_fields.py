"""Champs mission V1 du Dashboard (décisions 2026-10-16/17).

- estimated_minutes (doc 43 §5.2) ;
- failure_reason_code (doc 52 §10) : no_time | too_tired | not_relevant | impediment ;
- completed_annex_mission_ids sur la complétion (doc 53 §3.1).
"""
from uuid import uuid4

from app.schemas.imperium import BacklogMissionCreateRequest, CompleteMissionRequest, FailMissionRequest, StartMissionRequest
from app.services.imperium.missions import _stable_dump

from test_mission_completion_guardrails import (
    FakeDb,
    _client,
    _mission,
    _post_complete,
    _post_fail,
    _post_start,
    _user,
)


def test_start_stores_and_exposes_estimated_minutes() -> None:
    current_user = _user()
    db = FakeDb(scalar_results=[None, None])

    response = _post_start(
        _client(db, current_user),
        key="start-estimated",
        payload={"title": "Réviser le vocabulaire", "estimated_minutes": 15},
    )

    assert response.status_code == 201
    assert response.json()["mission"]["estimated_minutes"] == 15


def test_start_rejects_non_positive_or_absurd_estimated_minutes() -> None:
    for value in (0, -5, 1441):
        response = _post_start(
            _client(FakeDb(scalar_results=[None, None]), _user()),
            key=f"start-bad-{value}",
            payload={"title": "Mission", "estimated_minutes": value},
        )
        assert response.status_code == 422, value


def test_backlog_create_accepts_estimated_minutes() -> None:
    current_user = _user()
    db = FakeDb(scalar_results=[None])

    response = _client(db, current_user).post(
        "/imperium/missions/backlog",
        headers={"Idempotency-Key": "backlog-estimated"},
        json={"title": "Appeler Yacine", "estimated_minutes": 10},
    )

    assert response.status_code == 201
    assert response.json()["mission"]["estimated_minutes"] == 10


def test_fail_with_reason_code_only_stores_code() -> None:
    current_user = _user()
    mission = _mission(current_user.id)
    db = FakeDb(scalar_results=[None, mission])

    response = _post_fail(
        _client(db, current_user),
        mission.id,
        key="fail-code-only",
        payload={"failure_reason_code": "too_tired"},
    )

    assert response.status_code == 200
    body = response.json()["mission"]
    assert body["failure_reason_code"] == "too_tired"
    assert body["failure_reason"] is None
    assert mission.failure_reason_code == "too_tired"


def test_fail_with_code_and_details_stores_both() -> None:
    current_user = _user()
    mission = _mission(current_user.id)
    db = FakeDb(scalar_results=[None, mission])

    response = _post_fail(
        _client(db, current_user),
        mission.id,
        key="fail-code-details",
        payload={"failure_reason_code": "impediment", "failure_reason": "Voiture en panne"},
    )

    assert response.status_code == 200
    assert mission.failure_reason_code == "impediment"
    assert mission.failure_reason == "Voiture en panne"


def test_fail_rejects_unknown_reason_code() -> None:
    response = _post_fail(
        _client(FakeDb(), _user()),
        uuid4(),
        key="fail-bad-code",
        payload={"failure_reason_code": "lazy"},
    )
    assert response.status_code == 422


def test_fail_requires_code_or_details() -> None:
    response = _post_fail(_client(FakeDb(), _user()), uuid4(), key="fail-empty", payload={})
    assert response.status_code == 422


def test_fail_legacy_text_only_still_accepted() -> None:
    current_user = _user()
    mission = _mission(current_user.id)
    db = FakeDb(scalar_results=[None, mission])

    response = _post_fail(
        _client(db, current_user),
        mission.id,
        key="fail-legacy",
        payload={"failure_reason": "fatigue"},
    )

    assert response.status_code == 200
    assert mission.failure_reason_code is None


def test_complete_failed_outcome_accepts_reason_code_without_text() -> None:
    current_user = _user()
    mission = _mission(current_user.id)
    db = FakeDb(scalar_results=[None, mission])

    response = _post_complete(
        _client(db, current_user),
        mission.id,
        key="complete-failed-code",
        payload={"outcome": "failed", "failure_reason_code": "no_time"},
    )

    assert response.status_code == 200
    assert mission.status == "failed"
    assert mission.failure_reason_code == "no_time"


def test_complete_rejects_reason_code_on_completed_outcome() -> None:
    response = _post_complete(
        _client(FakeDb(), _user()),
        uuid4(),
        key="complete-code-on-success",
        payload={"outcome": "completed", "failure_reason_code": "no_time"},
    )
    assert response.status_code == 422


def test_complete_rejects_annex_ids_when_outcome_is_not_completed() -> None:
    response = _post_complete(
        _client(FakeDb(), _user()),
        uuid4(),
        key="complete-failed-annexes",
        payload={"outcome": "failed", "reason": "x", "completed_annex_mission_ids": [str(uuid4())]},
    )
    assert response.status_code == 422


def test_complete_defaults_to_no_annex_and_exposes_new_fields() -> None:
    current_user = _user()
    mission = _mission(current_user.id, estimated_minutes=45)
    db = FakeDb(scalar_results=[None, mission])

    response = _post_complete(
        _client(db, current_user),
        mission.id,
        key="complete-no-annex",
        payload={"outcome": "completed"},
    )

    assert response.status_code == 200
    body = response.json()["mission"]
    assert body["estimated_minutes"] == 45
    assert body["annex_of_mission_id"] is None
    assert response.json()["completed_annex_mission_ids"] == []


def test_idempotency_hash_payloads_stay_identical_for_legacy_clients() -> None:
    # Clés déjà stockées en production : un ancien client doit rejouer à l'identique.
    assert _stable_dump(FailMissionRequest(failure_reason="fatigue"), failure_reason_code=None) == {
        "failure_reason": "fatigue",
        "user_reported_signals": None,
        "ai_usable_reason": True,
    }
    legacy_complete = _stable_dump(
        CompleteMissionRequest(outcome="completed"), failure_reason_code=None, completed_annex_mission_ids=[]
    )
    assert legacy_complete == {"outcome": "completed", "reason": None}
    assert "estimated_minutes" not in _stable_dump(StartMissionRequest(title="x"), estimated_minutes=None)
    assert "estimated_minutes" not in _stable_dump(BacklogMissionCreateRequest(title="x"), estimated_minutes=None)
    assert _stable_dump(StartMissionRequest(title="x", estimated_minutes=5), estimated_minutes=None)["estimated_minutes"] == 5
