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
    CompleteMissionRequest,
    FailMissionRequest,
    MissionDecisionScoreRead,
    MissionDecisionScoreSummary,
    MissionResponse,
    MissionWriteResponse,
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


def complete_mission(
    db: Session,
    *,
    current_user: User,
    mission_id: UUID,
    payload: CompleteMissionRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[MissionWriteResponse, bool]:
    request_hash = _hash_request(
        "mission.completed",
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
        "completion_note": payload.completion_note,
    }
    event = _build_event(
        current_user=current_user,
        event_id=event_id,
        event_type="mission.completed",
        idempotency_key=idempotency_key,
        payload={key: value for key, value in event_payload.items() if value is not None},
    )
    db.add(event)
    db.flush()

    mission.status = "completed"
    mission.ended_at = datetime.now(UTC)
    mission.completion_note = payload.completion_note
    mission.ended_by_event_id = event.id
    db.flush()

    response = _write_response(
        mission=mission,
        event_id=event_id,
        idempotency_key=idempotency_key,
        status_text="completed",
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


def _get_active_mission(db: Session, *, current_user: User) -> ImperiumMission | None:
    return db.scalar(
        select(ImperiumMission).where(
            ImperiumMission.user_id == current_user.id,
            ImperiumMission.status == "active",
        )
    )


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


def _store_idempotency(
    db: Session,
    *,
    current_user: User,
    idempotency_key: str,
    request_method: str,
    request_path: str,
    request_hash: str,
    response_status_code: int,
    response: MissionWriteResponse,
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


def _hash_request(action: str, payload: dict) -> str:
    canonical = json.dumps(
        {"action": action, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
