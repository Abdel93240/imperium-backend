import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import IdempotencyStatus, PrivacyLevel, SourceApp
from app.models.event import Event
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumMission, ImperiumMissionScore
from app.schemas.imperium import (
    BacklogDecisionCandidate,
    BacklogDecisionPreviewResponse,
    BacklogDecisionScoreSummary,
    BacklogPromotionSummary,
    BacklogMissionCreateRequest,
    BacklogMissionCreateResponse,
    BacklogMissionListResponse,
    BacklogMissionRead,
    CompleteMissionRequest,
    FailMissionRequest,
    MissionCompletionResponse,
    MissionCompletionSummary,
    MissionDecisionScoreRead,
    MissionDecisionScoreSummary,
    MissionResponse,
    MissionWriteResponse,
    PromotedBacklogMissionRead,
    PromoteBacklogMissionResponse,
    StartMissionRequest,
)
from app.services.imperium.decision_framework import (
    SOURCE as DECISION_FRAMEWORK_SOURCE,
    build_mission_score_from_start_request,
    get_user_priority_context,
    mission_decision_score_read_from_row,
    mission_decision_score_summary_from_row,
)


class IdempotencyConflictError(ValueError):
    pass


class ActiveMissionExistsError(ValueError):
    pass


class MissionNotFoundError(ValueError):
    pass


class MissionStateConflictError(ValueError):
    pass


class MissionScoreNotFoundError(ValueError):
    pass


BACKLOG_ORDERING_NOTE = (
    "Sorted by higher stored Decision Framework priority_bucket first, "
    "then lower mission priority_level first, then created_at ascending for FIFO deterministic fallback."
)
BACKLOG_DECISION_PREVIEW_EXPLANATION = "Deterministic backend preview based on stored backlog fields only."
BACKLOG_PROMOTION_GUARDRAILS_CHECKED = [
    "OWNERSHIP_CONFIRMED",
    "MISSION_WAS_BACKLOG",
    "NO_ACTIVE_MISSION_FOUND",
    "IDEMPOTENCY_KEY_ACCEPTED",
]
BACKLOG_PROMOTION_SAFE_EXPLANATION = "Mission promoted from backlog using deterministic backend guardrails only."
MISSION_COMPLETION_GUARDRAILS_CHECKED = [
    "OWNERSHIP_CONFIRMED",
    "MISSION_WAS_ACTIVE",
    "OUTCOME_VALIDATED",
    "IDEMPOTENCY_KEY_ACCEPTED",
]
MISSION_COMPLETION_SAFE_EXPLANATION = "Mission completed using deterministic backend guardrails only."


def start_mission(
    db: Session,
    *,
    current_user: User,
    payload: StartMissionRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[MissionWriteResponse, bool]:
    request_hash = _hash_request("mission.started", payload.model_dump(mode="json"))
    existing_key = _get_existing_idempotency(db, current_user=current_user, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_existing_idempotency(existing_key, request_hash), True

    active_mission = _get_active_mission(db, current_user=current_user)
    if active_mission is not None:
        raise ActiveMissionExistsError("An active mission already exists for this user.")

    now = datetime.now(UTC)
    mission = ImperiumMission(
        user_id=current_user.id,
        title=payload.title,
        category=payload.category,
        domain=payload.domain,
        priority_level=payload.priority_level,
        mission_type_category=payload.mission_type_category,
        status="active",
        planned_start_at=payload.planned_start_at,
        planned_end_at=payload.planned_end_at,
        started_at=now,
    )
    db.add(mission)
    db.flush()

    event_id = f"evt_{uuid4().hex}"
    event_payload = {
        "mission_id": str(mission.id),
        **payload.model_dump(mode="json", exclude_none=True),
    }
    event = _build_event(
        current_user=current_user,
        event_id=event_id,
        event_type="mission.started",
        idempotency_key=idempotency_key,
        payload=event_payload,
    )
    db.add(event)
    db.flush()

    mission.created_by_event_id = event.id
    db.flush()

    decision_score = _maybe_create_decision_score(
        db,
        current_user=current_user,
        mission=mission,
        payload=payload,
    )

    response = _write_response(
        mission=mission,
        event_id=event_id,
        idempotency_key=idempotency_key,
        status_text="started",
        decision_score=decision_score,
    )
    _store_idempotency(
        db,
        current_user=current_user,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=201,
        response=response,
    )
    db.commit()
    return response, False


def create_backlog_mission(
    db: Session,
    *,
    current_user: User,
    payload: BacklogMissionCreateRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[BacklogMissionCreateResponse, bool]:
    request_hash = _hash_request("mission.backlog.created", payload.model_dump(mode="json"))
    existing_key = _get_existing_idempotency(db, current_user=current_user, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_existing_backlog_create_idempotency(existing_key, request_hash), True

    now = datetime.now(UTC)
    mission = ImperiumMission(
        user_id=current_user.id,
        title=payload.title,
        category=payload.category,
        domain=payload.domain,
        priority_level=payload.priority_level,
        mission_type_category=payload.mission_type_category,
        status="backlog",
        started_at=now,
    )
    db.add(mission)
    db.flush()

    event_id = f"evt_{uuid4().hex}"
    event_payload = {
        "mission_id": str(mission.id),
        **payload.model_dump(mode="json", exclude_none=True),
    }
    event = _build_event(
        current_user=current_user,
        event_id=event_id,
        event_type="mission.backlog.created",
        idempotency_key=idempotency_key,
        payload=event_payload,
    )
    db.add(event)
    db.flush()

    mission.created_by_event_id = event.id
    db.flush()

    decision_score = _maybe_create_decision_score(
        db,
        current_user=current_user,
        mission=mission,
        payload=_start_request_from_backlog_payload(payload),
    )

    response = _backlog_create_response(
        mission=mission,
        event_id=event_id,
        idempotency_key=idempotency_key,
        status_text="created",
        decision_score=decision_score,
    )
    _store_idempotency(
        db,
        current_user=current_user,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=201,
        response=response,
    )
    db.commit()
    return response, False


def list_backlog_missions(
    db: Session,
    *,
    current_user: User,
    limit: int = 20,
    offset: int = 0,
    domain: str | None = None,
    priority_level: int | None = None,
) -> BacklogMissionListResponse:
    filters = [
        ImperiumMission.user_id == current_user.id,
        ImperiumMission.status == "backlog",
    ]
    if domain is not None:
        filters.append(ImperiumMission.domain == domain)
    if priority_level is not None:
        filters.append(ImperiumMission.priority_level == priority_level)

    missions = list(
        db.scalars(
            select(ImperiumMission)
            .where(*filters)
            .order_by(ImperiumMission.created_at.asc(), ImperiumMission.id.asc())
        )
    )
    if not missions:
        return BacklogMissionListResponse(items=[], count=0, ordering=BACKLOG_ORDERING_NOTE)

    mission_ids = [mission.id for mission in missions]
    scores = list(
        db.scalars(
            select(ImperiumMissionScore)
            .where(
                ImperiumMissionScore.user_id == current_user.id,
                ImperiumMissionScore.mission_id.in_(mission_ids),
                ImperiumMissionScore.source == DECISION_FRAMEWORK_SOURCE,
            )
            .order_by(ImperiumMissionScore.created_at.desc())
        )
    )
    score_by_mission_id: dict[UUID, ImperiumMissionScore] = {}
    for score in scores:
        score_by_mission_id.setdefault(score.mission_id, score)

    sorted_missions = sorted(
        missions,
        key=lambda mission: _backlog_sort_key(mission, score_by_mission_id.get(mission.id)),
    )
    page = sorted_missions[offset : offset + limit]
    return BacklogMissionListResponse(
        items=[
            _backlog_mission_read(
                mission=mission,
                decision_score=_score_summary_or_none(score_by_mission_id.get(mission.id)),
            )
            for mission in page
        ],
        count=len(page),
        ordering=BACKLOG_ORDERING_NOTE,
    )


def get_backlog_decision_preview(
    db: Session,
    *,
    current_user: User,
    limit: int = 10,
    domain: str | None = None,
    priority_level: int | None = None,
    include_reasons: bool = True,
) -> BacklogDecisionPreviewResponse:
    filters = [
        ImperiumMission.user_id == current_user.id,
        ImperiumMission.status == "backlog",
    ]
    if domain is not None:
        filters.append(ImperiumMission.domain == domain)
    if priority_level is not None:
        filters.append(ImperiumMission.priority_level == priority_level)

    missions = list(
        db.scalars(
            select(ImperiumMission)
            .where(*filters)
            .order_by(ImperiumMission.created_at.asc(), ImperiumMission.id.asc())
        )
    )
    if not missions:
        return BacklogDecisionPreviewResponse(
            recommended_mission_id=None,
            candidate_count=0,
            candidates=[],
            safe_explanation=BACKLOG_DECISION_PREVIEW_EXPLANATION,
        )

    mission_ids = [mission.id for mission in missions]
    scores = list(
        db.scalars(
            select(ImperiumMissionScore)
            .where(
                ImperiumMissionScore.user_id == current_user.id,
                ImperiumMissionScore.mission_id.in_(mission_ids),
                ImperiumMissionScore.source == DECISION_FRAMEWORK_SOURCE,
            )
            .order_by(ImperiumMissionScore.created_at.desc())
        )
    )
    score_by_mission_id: dict[UUID, ImperiumMissionScore] = {}
    for score in scores:
        score_by_mission_id.setdefault(score.mission_id, score)

    sorted_missions = sorted(
        missions,
        key=lambda mission: _backlog_sort_key(mission, score_by_mission_id.get(mission.id)),
    )
    candidates = [
        _backlog_decision_candidate(
            mission=mission,
            score=score_by_mission_id.get(mission.id),
            include_reasons=include_reasons,
        )
        for mission in sorted_missions[:limit]
    ]
    recommended_mission_id = candidates[0].id if candidates else None
    return BacklogDecisionPreviewResponse(
        recommended_mission_id=recommended_mission_id,
        candidate_count=len(candidates),
        candidates=candidates,
        safe_explanation=BACKLOG_DECISION_PREVIEW_EXPLANATION,
    )


def promote_backlog_mission(
    db: Session,
    *,
    current_user: User,
    mission_id: UUID,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[PromoteBacklogMissionResponse, bool]:
    request_hash = _hash_request("mission.backlog.promoted", {"mission_id": str(mission_id)})
    existing_key = _get_existing_idempotency(db, current_user=current_user, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_existing_promote_idempotency(existing_key, request_hash), True

    mission = _get_user_mission(db, current_user=current_user, mission_id=mission_id)
    if mission is None:
        raise MissionNotFoundError("Mission not found.")
    if mission.status != "backlog":
        raise MissionStateConflictError("Mission is not in backlog.")

    active_mission = _get_active_mission(db, current_user=current_user)
    if active_mission is not None:
        raise ActiveMissionExistsError("An active mission already exists for this user.")

    now = datetime.now(UTC)
    event_id = f"evt_{uuid4().hex}"
    event_payload = {
        "mission_id": str(mission.id),
        "source": "backlog_promotion",
    }
    event = _build_event(
        current_user=current_user,
        event_id=event_id,
        event_type="mission.started",
        idempotency_key=idempotency_key,
        payload=event_payload,
    )
    db.add(event)
    db.flush()

    mission.status = "active"
    mission.started_at = now
    mission.ended_at = None
    if mission.created_by_event_id is None:
        mission.created_by_event_id = event.id
    db.flush()

    score = _get_existing_decision_score(db, current_user=current_user, mission_id=mission.id)
    response = _promote_response(
        mission=mission,
        event_id=event_id,
        idempotency_key=idempotency_key,
        decision_score=_score_summary_or_none(score),
    )
    _store_idempotency(
        db,
        current_user=current_user,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=200,
        response=response,
    )
    db.commit()
    return response, False


def complete_mission(
    db: Session,
    *,
    current_user: User,
    mission_id: UUID,
    payload: CompleteMissionRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[MissionCompletionResponse, bool]:
    request_hash = _hash_request(
        "mission.completion_guardrails",
        {"mission_id": str(mission_id), "payload": payload.model_dump(mode="json")},
    )
    existing_key = _get_existing_idempotency(db, current_user=current_user, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_existing_completion_idempotency(existing_key, request_hash), True

    mission = _get_user_mission(db, current_user=current_user, mission_id=mission_id)
    _require_active_mission(mission)

    outcome = payload.outcome.value
    event_id = f"evt_{uuid4().hex}"
    event_payload = {
        "mission_id": str(mission.id),
        "outcome": outcome,
        "reason": payload.reason,
    }
    event = _build_event(
        current_user=current_user,
        event_id=event_id,
        event_type=f"mission.{outcome}",
        idempotency_key=idempotency_key,
        payload={key: value for key, value in event_payload.items() if value is not None},
    )
    db.add(event)
    db.flush()

    mission.status = outcome
    mission.ended_at = datetime.now(UTC)
    if outcome == "completed":
        mission.completion_note = payload.reason
        mission.failure_reason = None
    else:
        mission.completion_note = None
        mission.failure_reason = payload.reason
    mission.ended_by_event_id = event.id
    db.flush()

    response = _completion_response(
        mission=mission,
        status_text=outcome,
    )
    _store_idempotency(
        db,
        current_user=current_user,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=200,
        response=response,
    )
    db.commit()
    return response, False


def fail_mission(
    db: Session,
    *,
    current_user: User,
    mission_id: UUID,
    payload: FailMissionRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[MissionWriteResponse, bool]:
    request_hash = _hash_request(
        "mission.failed",
        {"mission_id": str(mission_id), "payload": payload.model_dump(mode="json")},
    )
    existing_key = _get_existing_idempotency(db, current_user=current_user, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_existing_idempotency(existing_key, request_hash), True

    mission = _get_user_mission(db, current_user=current_user, mission_id=mission_id)
    _require_active_mission(mission)

    event_id = f"evt_{uuid4().hex}"
    event_payload = {
        "mission_id": str(mission.id),
        "failure_reason": payload.failure_reason,
        "user_reported_signals": payload.user_reported_signals,
        "ai_usable_reason": payload.ai_usable_reason,
    }
    event = _build_event(
        current_user=current_user,
        event_id=event_id,
        event_type="mission.failed",
        idempotency_key=idempotency_key,
        payload={key: value for key, value in event_payload.items() if value is not None},
    )
    db.add(event)
    db.flush()

    mission.status = "failed"
    mission.ended_at = datetime.now(UTC)
    mission.failure_reason = payload.failure_reason
    mission.user_reported_signals = payload.user_reported_signals
    mission.ai_usable_reason = payload.ai_usable_reason
    mission.ended_by_event_id = event.id
    db.flush()

    response = _write_response(
        mission=mission,
        event_id=event_id,
        idempotency_key=idempotency_key,
        status_text="failed",
    )
    _store_idempotency(
        db,
        current_user=current_user,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response_status_code=200,
        response=response,
    )
    db.commit()
    return response, False


def get_current_mission(db: Session, *, current_user: User) -> ImperiumMission | None:
    return _get_active_mission(db, current_user=current_user)


def get_recent_missions(db: Session, *, current_user: User, limit: int) -> list[ImperiumMission]:
    return list(
        db.scalars(
            select(ImperiumMission)
            .where(ImperiumMission.user_id == current_user.id)
            .order_by(ImperiumMission.started_at.desc())
            .limit(limit)
        )
    )


def get_mission_decision_score(
    db: Session,
    *,
    current_user: User,
    mission_id: UUID,
) -> MissionDecisionScoreRead:
    mission = _get_user_mission(db, current_user=current_user, mission_id=mission_id)
    if mission is None:
        raise MissionNotFoundError("Mission not found.")
    score = _get_existing_decision_score(db, current_user=current_user, mission_id=mission.id)
    if score is None:
        raise MissionScoreNotFoundError("Mission decision score not found.")
    return mission_decision_score_read_from_row(score)


def _get_existing_idempotency(
    db: Session,
    *,
    current_user: User,
    idempotency_key: str,
) -> IdempotencyKey | None:
    return db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == current_user.id,
            IdempotencyKey.idempotency_key == idempotency_key,
        )
    )


def _handle_existing_idempotency(
    existing_key: IdempotencyKey,
    request_hash: str,
) -> MissionWriteResponse:
    if existing_key.request_hash != request_hash:
        raise IdempotencyConflictError("Idempotency key already used with different payload.")
    if existing_key.response_body is None:
        raise IdempotencyConflictError("Idempotency key is already processing.")
    return MissionWriteResponse(**existing_key.response_body)


def _handle_existing_backlog_create_idempotency(
    existing_key: IdempotencyKey,
    request_hash: str,
) -> BacklogMissionCreateResponse:
    if existing_key.request_hash != request_hash:
        raise IdempotencyConflictError("Idempotency key already used with different payload.")
    if existing_key.response_body is None:
        raise IdempotencyConflictError("Idempotency key is already processing.")
    return BacklogMissionCreateResponse(**existing_key.response_body)


def _handle_existing_promote_idempotency(
    existing_key: IdempotencyKey,
    request_hash: str,
) -> PromoteBacklogMissionResponse:
    if existing_key.request_hash != request_hash:
        raise IdempotencyConflictError("Idempotency key already used with different payload.")
    if existing_key.response_body is None:
        raise IdempotencyConflictError("Idempotency key is already processing.")
    return PromoteBacklogMissionResponse(**existing_key.response_body)


def _handle_existing_completion_idempotency(
    existing_key: IdempotencyKey,
    request_hash: str,
) -> MissionCompletionResponse:
    if existing_key.request_hash != request_hash:
        raise IdempotencyConflictError("Idempotency key already used with different payload.")
    if existing_key.response_body is None:
        raise IdempotencyConflictError("Idempotency key is already processing.")
    return MissionCompletionResponse(**existing_key.response_body)


def _get_active_mission(db: Session, *, current_user: User) -> ImperiumMission | None:
    return db.scalar(
        select(ImperiumMission).where(
            ImperiumMission.user_id == current_user.id,
            ImperiumMission.status == "active",
        )
    )


def _start_request_from_backlog_payload(payload: BacklogMissionCreateRequest) -> StartMissionRequest:
    return StartMissionRequest(**payload.model_dump())


def _maybe_create_decision_score(
    db: Session,
    *,
    current_user: User,
    mission: ImperiumMission,
    payload: StartMissionRequest,
) -> MissionDecisionScoreSummary | None:
    if not _should_store_decision_score(payload):
        return None

    existing_score = _get_existing_decision_score(db, current_user=current_user, mission_id=mission.id)
    if existing_score is not None:
        return mission_decision_score_summary_from_row(existing_score)

    priorities = get_user_priority_context(db, current_user=current_user)
    score_payload = build_mission_score_from_start_request(payload, priorities=priorities)
    score = ImperiumMissionScore(
        user_id=current_user.id,
        mission_id=mission.id,
        domain=score_payload["domain"],
        intrinsic_score=score_payload["intrinsic_score"],
        domain_coefficient=score_payload["domain_coefficient"],
        weighted_score=score_payload["weighted_score"],
        explanation=score_payload["explanation"],
        source=score_payload["source"],
    )
    db.add(score)
    db.flush()
    return mission_decision_score_summary_from_row(score)


def _should_store_decision_score(payload: StartMissionRequest) -> bool:
    if payload.domain is None:
        return False
    return any(
        value is not None
        for value in (
            payload.deadline_at,
            payload.impact,
            payload.mission_type,
            payload.dependency,
            payload.recurrence,
            payload.mission_type_category,
        )
    )


def _get_existing_decision_score(
    db: Session,
    *,
    current_user: User,
    mission_id: UUID,
) -> ImperiumMissionScore | None:
    return db.scalar(
        select(ImperiumMissionScore)
        .where(
            ImperiumMissionScore.user_id == current_user.id,
            ImperiumMissionScore.mission_id == mission_id,
            ImperiumMissionScore.source == DECISION_FRAMEWORK_SOURCE,
        )
        .order_by(ImperiumMissionScore.created_at.desc())
    )


def _score_summary_or_none(score: ImperiumMissionScore | None) -> MissionDecisionScoreSummary | None:
    if score is None:
        return None
    return mission_decision_score_summary_from_row(score)


def _backlog_sort_key(mission: ImperiumMission, score: ImperiumMissionScore | None) -> tuple[int, int, datetime, str]:
    bucket = 0
    if score is not None:
        bucket = mission_decision_score_summary_from_row(score).priority_bucket
    priority = mission.priority_level if mission.priority_level is not None else 999
    created_at = mission.created_at or datetime.min.replace(tzinfo=UTC)
    return (-bucket, priority, created_at, str(mission.id))


def _priority_bucket_from_score(score: ImperiumMissionScore | None) -> int:
    if score is None:
        return 0
    return mission_decision_score_summary_from_row(score).priority_bucket


def _backlog_score_label(priority_bucket: int) -> str:
    if priority_bucket >= 4:
        return "high"
    if priority_bucket >= 2:
        return "medium"
    return "low"


def _backlog_reason_codes(*, priority_bucket: int, priority_level: int | None) -> list[str]:
    if priority_bucket >= 4:
        reason_codes = ["HIGH_PRIORITY_BUCKET"]
    elif priority_bucket >= 2:
        reason_codes = ["MEDIUM_PRIORITY_BUCKET"]
    else:
        reason_codes = ["LOW_PRIORITY_BUCKET"]

    if priority_level is not None and priority_level <= 2:
        reason_codes.append("LOW_PRIORITY_LEVEL")
    reason_codes.append("FIFO_BACKLOG")
    return reason_codes


def _get_user_mission(
    db: Session,
    *,
    current_user: User,
    mission_id: UUID,
) -> ImperiumMission | None:
    return db.scalar(
        select(ImperiumMission).where(
            ImperiumMission.id == mission_id,
            ImperiumMission.user_id == current_user.id,
        )
    )


def _require_active_mission(mission: ImperiumMission | None) -> None:
    if mission is None:
        raise MissionNotFoundError("Mission not found.")
    if mission.status != "active":
        raise MissionStateConflictError("Mission is not active.")


def _build_event(
    *,
    current_user: User,
    event_id: str,
    event_type: str,
    idempotency_key: str,
    payload: dict,
) -> Event:
    now = datetime.now(UTC)
    return Event(
        event_id=event_id,
        event_type=event_type,
        schema_version="1.0",
        occurred_at=now,
        received_at=now,
        source_app=SourceApp.imperium,
        device_id=None,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        correlation_id=f"corr_{event_type.replace('.', '_')}_{uuid4().hex}",
        causation_id=None,
        privacy_level=PrivacyLevel.medium,
        payload=payload,
    )


def _backlog_decision_candidate(
    *,
    mission: ImperiumMission,
    score: ImperiumMissionScore | None,
    include_reasons: bool,
) -> BacklogDecisionCandidate:
    priority_bucket = _priority_bucket_from_score(score)
    reason_codes = _backlog_reason_codes(
        priority_bucket=priority_bucket,
        priority_level=mission.priority_level,
    )
    return BacklogDecisionCandidate(
        id=mission.id,
        title=mission.title,
        domain=mission.domain,
        priority_level=mission.priority_level,
        priority_bucket=priority_bucket,
        score_summary=BacklogDecisionScoreSummary(
            label=_backlog_score_label(priority_bucket),
            reason_codes=reason_codes if include_reasons else None,
        ),
    )


def _store_idempotency(
    db: Session,
    *,
    current_user: User,
    idempotency_key: str,
    request_method: str,
    request_path: str,
    request_hash: str,
    response_status_code: int,
    response: BacklogMissionCreateResponse | MissionWriteResponse | PromoteBacklogMissionResponse | MissionCompletionResponse,
) -> None:
    db.add(
        IdempotencyKey(
            user_id=current_user.id,
            idempotency_key=idempotency_key,
            request_method=request_method,
            request_path=request_path,
            request_hash=request_hash,
            status=IdempotencyStatus.completed,
            response_status_code=response_status_code,
            response_body=response.model_dump(mode="json"),
        )
    )


def _backlog_mission_read(
    *,
    mission: ImperiumMission,
    decision_score: MissionDecisionScoreSummary | None = None,
) -> BacklogMissionRead:
    mission_response = BacklogMissionRead.model_validate(mission)
    mission_response.decision_score = decision_score
    return mission_response


def _backlog_create_response(
    *,
    mission: ImperiumMission,
    event_id: str,
    idempotency_key: str,
    status_text: str,
    decision_score: MissionDecisionScoreSummary | None = None,
) -> BacklogMissionCreateResponse:
    return BacklogMissionCreateResponse(
        mission=_backlog_mission_read(mission=mission, decision_score=decision_score),
        event_id=event_id,
        idempotency_key=idempotency_key,
        status=status_text,
        score_created=decision_score is not None,
    )


def _promote_response(
    *,
    mission: ImperiumMission,
    event_id: str,
    idempotency_key: str,
    decision_score: MissionDecisionScoreSummary | None = None,
) -> PromoteBacklogMissionResponse:
    mission_response = _promoted_backlog_mission_read(mission=mission, decision_score=decision_score)
    return PromoteBacklogMissionResponse(
        mission=mission_response,
        promotion_summary=BacklogPromotionSummary(
            status="promoted",
            guardrails_checked=BACKLOG_PROMOTION_GUARDRAILS_CHECKED,
            safe_explanation=BACKLOG_PROMOTION_SAFE_EXPLANATION,
        ),
        event_id=event_id,
        idempotency_key=idempotency_key,
        status="promoted",
        decision_score=decision_score,
    )


def _promoted_backlog_mission_read(
    *,
    mission: ImperiumMission,
    decision_score: MissionDecisionScoreSummary | None = None,
) -> PromotedBacklogMissionRead:
    mission_response = PromotedBacklogMissionRead.model_validate(mission)
    mission_response.decision_score = decision_score
    return mission_response


def _write_response(
    *,
    mission: ImperiumMission,
    event_id: str,
    idempotency_key: str,
    status_text: str,
    decision_score: MissionDecisionScoreSummary | None = None,
) -> MissionWriteResponse:
    mission_response = MissionResponse.model_validate(mission)
    mission_response.event_id = event_id
    mission_response.idempotency_key = idempotency_key
    return MissionWriteResponse(
        mission=mission_response,
        event_id=event_id,
        idempotency_key=idempotency_key,
        status=status_text,
        score_created=decision_score is not None,
        decision_score=decision_score,
    )


def _completion_response(
    *,
    mission: ImperiumMission,
    status_text: str,
) -> MissionCompletionResponse:
    return MissionCompletionResponse(
        mission=mission,
        completion_summary=MissionCompletionSummary(
            status=status_text,
            guardrails_checked=MISSION_COMPLETION_GUARDRAILS_CHECKED,
            safe_explanation=MISSION_COMPLETION_SAFE_EXPLANATION,
        ),
    )


def _hash_request(action: str, payload: dict) -> str:
    canonical = json.dumps(
        {"action": action, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
