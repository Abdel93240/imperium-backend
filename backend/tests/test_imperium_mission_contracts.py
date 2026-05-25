from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.schemas.imperium import (
    BacklogMissionCreateResponse,
    BacklogMissionRead,
    BacklogPromotionSummary,
    MissionDecisionScoreSummary,
    MissionResponse,
    MissionWriteResponse,
    PromoteBacklogMissionResponse,
    PromotedBacklogMissionRead,
)


def _score_summary() -> MissionDecisionScoreSummary:
    return MissionDecisionScoreSummary(
        intrinsic_score=42,
        priority_bucket=3,
        score_status="partial",
        missing_fields=["deadline_at", "impact"],
        source="decision_framework_v1",
    )


def _mission_response() -> MissionResponse:
    now = datetime.now(UTC)
    return MissionResponse(
        id=uuid4(),
        status="active",
        title="Prepare invoice",
        category="admin",
        domain="business",
        priority_level=4,
        mission_type_category="cat_e",
        planned_start_at=None,
        planned_end_at=None,
        started_at=now,
        ended_at=None,
        completion_note=None,
        failure_reason=None,
        user_reported_signals=None,
        ai_usable_reason=True,
        event_id="evt_mission",
        idempotency_key="mission-score-1",
    )


def _backlog_mission_read() -> BacklogMissionRead:
    now = datetime.now(UTC)
    return BacklogMissionRead(
        id=uuid4(),
        status="backlog",
        title="Prepare invoice",
        category="admin",
        domain="business",
        priority_level=4,
        mission_type_category="cat_e",
        planned_start_at=None,
        planned_end_at=None,
        created_at=now,
        updated_at=now,
        decision_score=_score_summary(),
    )


def _promoted_backlog_mission_read() -> PromotedBacklogMissionRead:
    now = datetime.now(UTC)
    return PromotedBacklogMissionRead(
        id=uuid4(),
        status="active",
        title="Prepare invoice",
        category="admin",
        domain="business",
        priority_level=4,
        mission_type_category="cat_e",
        planned_start_at=None,
        planned_end_at=None,
        started_at=now,
        created_at=now,
        updated_at=now,
        decision_score=_score_summary(),
    )


@pytest.mark.parametrize(
    "response",
    [
        MissionWriteResponse(
            mission=_mission_response(),
            event_id="evt_1",
            idempotency_key="mission-write-1",
            status="started",
            score_created=True,
            decision_score=_score_summary(),
        ),
        BacklogMissionCreateResponse(
            mission=_backlog_mission_read(),
            event_id="evt_2",
            idempotency_key="backlog-create-1",
            status="created",
            score_created=True,
        ),
        PromoteBacklogMissionResponse(
            mission=_promoted_backlog_mission_read(),
            promotion_summary=BacklogPromotionSummary(
                status="promoted",
                guardrails_checked=[
                    "OWNERSHIP_CONFIRMED",
                    "MISSION_WAS_BACKLOG",
                    "NO_ACTIVE_MISSION_FOUND",
                    "IDEMPOTENCY_KEY_ACCEPTED",
                ],
                safe_explanation="Mission promoted from backlog using deterministic backend guardrails only.",
            ),
            event_id="evt_3",
            idempotency_key="backlog-promote-1",
            status="promoted",
            decision_score=_score_summary(),
        ),
    ],
)
def test_public_mission_responses_hide_internal_score_fields(response) -> None:
    serialized = response.model_dump_json()

    for forbidden in (
        "intrinsic_score",
        "weighted_score",
        "domain_coefficient",
        "final_weighted_score",
        "coefficient",
    ):
        assert forbidden not in serialized

