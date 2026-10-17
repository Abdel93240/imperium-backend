"""Statut standby et échéance des missions (doc 43 §5.4, décision 2026-10-16) — tests unitaires."""
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.imperium import FinishDayResponse, MissionStatus, ResolveStandbyRequest
from test_mission_completion_guardrails import FakeDb, _client, _post_start, _user


def test_standby_is_a_mission_status() -> None:
    assert MissionStatus.standby.value == "standby"


def test_start_stores_and_exposes_deadline_at() -> None:
    deadline = datetime(2026, 10, 20, 18, 0, tzinfo=UTC)
    db = FakeDb(scalar_results=[None, None])

    response = _post_start(
        _client(db, _user()),
        key="start-deadline",
        payload={"title": "Renouveler la carte VTC", "deadline_at": deadline.isoformat()},
    )

    assert response.status_code == 201
    assert response.json()["mission"]["deadline_at"] == deadline.isoformat().replace("+00:00", "Z")


def test_resolve_reschedule_requires_a_deadline() -> None:
    with pytest.raises(ValidationError):
        ResolveStandbyRequest(decision="reschedule")
    future = datetime.now(UTC) + timedelta(days=3)
    assert ResolveStandbyRequest(decision="reschedule", deadline_at=future).deadline_at == future


def test_resolve_other_decisions_reject_a_deadline() -> None:
    future = datetime.now(UTC) + timedelta(days=3)
    for decision in ("completed", "cancelled"):
        with pytest.raises(ValidationError):
            ResolveStandbyRequest(decision=decision, deadline_at=future)
        assert ResolveStandbyRequest(decision=decision).decision.value == decision


def test_resolve_rejects_unknown_decision() -> None:
    with pytest.raises(ValidationError):
        ResolveStandbyRequest(decision="ignore")


def test_finish_day_response_replays_legacy_body_without_closure_fields() -> None:
    # Les réponses déjà stockées (idempotence) n'ont pas les nouveaux champs.
    legacy = FinishDayResponse.model_fields
    assert legacy["missions_returned_to_backlog"].default == 0
    assert legacy["missions_to_standby"].default == 0
