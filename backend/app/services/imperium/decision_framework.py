import hashlib
import json
import unicodedata
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import IdempotencyStatus
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumMissionScore, ImperiumUserPriority
from app.schemas.imperium import (
    DecisionFrameworkPrioritiesResponse,
    DecisionFrameworkPrioritiesUpdateRequest,
    DecisionFrameworkPriorityRead,
    DecisionFrameworkSchemaResponse,
    DecisionFrameworkScoreBreakdownItem,
    DecisionFrameworkScoreExplanation,
    DecisionFrameworkScorePreviewRequest,
    DecisionFrameworkScorePreviewResponse,
    MissionDecisionScoreRead,
    MissionDecisionScoreSummary,
    StartMissionRequest,
)

SUPPORTED_DOMAINS = ("religious", "business", "finance", "health")
DEFAULT_PRIORITY_ORDER = ("religious", "business", "finance", "health")
COEFFICIENT_BY_POSITION = {1: 10, 2: 8, 3: 5, 4: 4}
SOURCE = "decision_framework_v1"

_DOMAIN_ALIASES = {
    "religious": "religious",
    "religion": "religious",
    "religieux": "religious",
    "business": "business",
    "work": "business",
    "travail": "business",
    "finance": "finance",
    "finances": "finance",
    "financial": "finance",
    "health": "health",
    "sante": "health",
    "santé": "health",
}

_IMPACT_POINTS = {
    "cosmetic": 0,
    "quality_of_life": 5,
    "quality-of-life": 5,
    "mid": 10,
    "paperwork": 10,
    "important": 15,
    "critical": 20,
    "vital_short_term": 25,
    "vital-short-term": 25,
    "vital_immediate": 30,
    "vital-immediate": 30,
}

_MISSION_TYPE_POINTS = {
    "cat_a": 20,
    "vital_immediate": 20,
    "cat_b": 18,
    "legal_contractual": 18,
    "cat_c": 15,
    "medical_planned": 15,
    "cat_d": 12,
    "religious_obligatory": 12,
    "cat_e": 10,
    "work_income": 10,
    "cat_f": 8,
    "learning": 8,
    "cat_g": 5,
    "health_routine": 5,
    "cat_h": 3,
    "quality_of_life": 3,
    "cat_i": 0,
    "optional": 0,
}

_DEPENDENCY_POINTS = {
    "none": 0,
    "no": 0,
    "false": 0,
    "one_two": 5,
    "one-two": 5,
    "some": 5,
    "true": 5,
    "multiple": 10,
    "many": 10,
}

_RECURRENCE_POINTS = {
    "daily": 0,
    "quotidien": 0,
    "weekly": 3,
    "hebdomadaire": 3,
    "monthly": 5,
    "mensuel": 5,
    "yearly": 7,
    "annual": 7,
    "annuel": 7,
    "exceptional": 10,
    "unique": 10,
}

_UNSAFE_PAYLOAD_MARKERS = (
    "raw_payload",
    "provider_payload",
    "internal_prompt",
    "system_prompt",
    "hidden_reasoning",
    "chain_of_thought",
    "secret",
    "password",
    "token",
    "api_key",
    "authorization",
)

_LEGACY_SCORE_FIELDS = (
    "impact_points",
    "impact_level",
    "effort_points",
    "mission_type_points",
    "dependency_points",
    "blocked_mission_count",
    "alignment_points",
)


class DecisionFrameworkValidationError(ValueError):
    pass


class DecisionFrameworkIdempotencyConflictError(ValueError):
    pass


def normalize_domain(domain: str) -> str:
    normalized = _strip_accents(domain).strip().lower().replace("_", "-").replace(" ", "-")
    canonical = _DOMAIN_ALIASES.get(normalized)
    if canonical is None:
        raise DecisionFrameworkValidationError(f"Unsupported decision framework domain: {domain}.")
    return canonical


def get_domain_coefficient(position: int) -> int:
    try:
        return COEFFICIENT_BY_POSITION[position]
    except KeyError as exc:
        raise DecisionFrameworkValidationError("Priority position must be between 1 and 4.") from exc


def get_or_initialize_user_priorities(db: Session, *, current_user: User) -> DecisionFrameworkPrioritiesResponse:
    priorities = get_canonical_priority_order(db, current_user=current_user, persist_defaults=True)
    return _priorities_response(priorities, status="ok")


def get_user_priority_context(db: Session, *, current_user: User) -> list[ImperiumUserPriority]:
    return get_canonical_priority_order(db, current_user=current_user)


def get_canonical_priority_order(
    db: Session,
    *,
    current_user: User,
    persist_defaults: bool = False,
) -> list[ImperiumUserPriority]:
    """Return the Decision Framework priority hierarchy in canonical order.

    `imperium_user_priorities` is the canonical read source. When no persisted
    rows exist yet, callers can either receive the deterministic V1 default as a
    transient context or persist that default for public read endpoints.
    """

    priorities = _get_active_user_priorities(db, current_user=current_user)
    if priorities:
        return sorted(priorities, key=lambda item: item.position)
    if persist_defaults:
        priorities = _build_default_priorities(current_user=current_user)
        db.add_all(priorities)
        db.flush()
        db.commit()
        return sorted(priorities, key=lambda item: item.position)
    return _build_default_priorities(current_user=current_user, transient=True)


def _build_default_priorities(
    *,
    current_user: User,
    transient: bool = False,
) -> list[ImperiumUserPriority]:
    now = datetime.now(UTC)
    return [
        ImperiumUserPriority(
            id=None if transient else None,
            user_id=current_user.id,
            domain=domain,
            position=position,
            coefficient=get_domain_coefficient(position),
            is_active=True,
            created_at=now if transient else None,
            updated_at=now if transient else None,
        )
        for position, domain in enumerate(DEFAULT_PRIORITY_ORDER, start=1)
    ]


def replace_user_priorities(
    db: Session,
    *,
    current_user: User,
    payload: DecisionFrameworkPrioritiesUpdateRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[DecisionFrameworkPrioritiesResponse, bool]:
    ordered_domains = _validate_priority_domains(payload.domains)
    request_hash = _hash_payload({"domains": ordered_domains})
    existing_key = _get_existing_idempotency(db, current_user=current_user, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_existing_idempotency(existing_key, request_hash, request_path), True

    active_priorities = _get_active_user_priorities(db, current_user=current_user)
    for priority in active_priorities:
        priority.is_active = False

    new_priorities = [
        ImperiumUserPriority(
            user_id=current_user.id,
            domain=domain,
            position=position,
            coefficient=get_domain_coefficient(position),
            is_active=True,
        )
        for position, domain in enumerate(ordered_domains, start=1)
    ]
    db.add_all(new_priorities)
    db.flush()

    response = _priorities_response(new_priorities, status="updated", idempotency_key=idempotency_key)
    db.add(
        IdempotencyKey(
            user_id=current_user.id,
            idempotency_key=idempotency_key,
            request_method=request_method,
            request_path=request_path,
            request_hash=request_hash,
            status=IdempotencyStatus.completed,
            response_status_code=200,
            response_body=response.model_dump(mode="json"),
        )
    )
    db.commit()
    return response, False


def get_decision_framework_schema() -> DecisionFrameworkSchemaResponse:
    return DecisionFrameworkSchemaResponse(
        scoring_enabled=True,
        monthly_planning_enabled=False,
        daily_adaptation_enabled=False,
        real_ai_enabled=False,
        embeddings_enabled=False,
        supported_domains=list(SUPPORTED_DOMAINS),
        coefficient_policy={"visibility": "internal"},
        storage_tables=["imperium_user_priorities", "imperium_mission_scores"],
        note="Decision Framework V1 is deterministic foundation only: no monthly planning, no daily adaptation, no real AI, no embeddings.",
    )


def compute_intrinsic_score(candidate: DecisionFrameworkScorePreviewRequest | dict) -> int:
    explanation = explain_score(candidate)
    return explanation.final_intrinsic_score


def compute_weighted_score(intrinsic_score: int, domain_coefficient: int) -> int:
    return _clamp_int(intrinsic_score, 0, 100) * domain_coefficient


def explain_score(
    candidate: DecisionFrameworkScorePreviewRequest | dict,
    *,
    domain_position: int | None = None,
    domain_coefficient: int | None = None,
) -> DecisionFrameworkScoreExplanation:
    _ = (domain_position, domain_coefficient)
    data = candidate.model_dump() if isinstance(candidate, DecisionFrameworkScorePreviewRequest) else dict(candidate)
    missing_fields: list[str] = []
    flags: list[str] = []

    deadline_points = _deadline_points(data.get("deadline_at"), missing_fields, flags)
    impact_points = _impact_points(data, missing_fields, flags)
    mission_type_points = _mission_type_points(data, missing_fields, flags)
    dependency_points = _dependency_points(data, missing_fields)
    recurrence_points = _recurrence_points(data, missing_fields, flags)

    intrinsic_score = _clamp_int(
        deadline_points + impact_points + mission_type_points + dependency_points + recurrence_points,
        0,
        100,
    )
    if data.get("payload") is not None:
        flags.extend(_unsafe_payload_warnings(data["payload"]))
    flags.extend(_legacy_field_warnings(data))

    return DecisionFrameworkScoreExplanation(
        deadline_points=deadline_points,
        impact_points=impact_points,
        mission_type_points=mission_type_points,
        dependency_points=dependency_points,
        recurrence_points=recurrence_points,
        missing_fields=missing_fields,
        final_intrinsic_score=intrinsic_score,
        flags=flags,
    )


def preview_decision_framework_score(
    payload: DecisionFrameworkScorePreviewRequest,
    *,
    priorities: list[ImperiumUserPriority] | None = None,
) -> DecisionFrameworkScorePreviewResponse:
    domain = normalize_domain(payload.domain)
    domain_position, domain_coefficient = _priority_for_domain(domain, priorities=priorities)
    explanation = explain_score(
        payload,
        domain_position=domain_position,
        domain_coefficient=domain_coefficient,
    )
    weighted_score = compute_weighted_score(explanation.final_intrinsic_score, domain_coefficient)
    breakdown = _build_breakdown(explanation)
    missing_fields = list(explanation.missing_fields)
    score_status = _score_status(explanation)
    return DecisionFrameworkScorePreviewResponse(
        domain=domain,
        domain_position=domain_position,
        intrinsic_score=explanation.final_intrinsic_score,
        priority_bucket=_priority_bucket(weighted_score),
        score_status=score_status,
        display_title=_display_title(payload),
        display_summary=_display_summary(
            domain=domain,
            domain_position=domain_position,
            score_status=score_status,
            missing_count=len(missing_fields),
        ),
        explanation=explanation,
        breakdown=breakdown,
        missing_fields=missing_fields,
        warnings=list(dict.fromkeys(explanation.flags)),
        storage_enabled=False,
        source=SOURCE,
    )


def preview_score_from_mission_like(
    mission_like: dict,
    *,
    priorities: list[ImperiumUserPriority] | None = None,
) -> DecisionFrameworkScorePreviewResponse:
    domain_value = mission_like.get("domain") or mission_like.get("category")
    if domain_value is None:
        raise DecisionFrameworkValidationError("Mission-like preview requires domain or category.")
    payload = DecisionFrameworkScorePreviewRequest(
        domain=str(domain_value),
        title=mission_like.get("title"),
        deadline_at=mission_like.get("deadline_at") or mission_like.get("planned_end_at"),
        impact=mission_like.get("impact"),
        effort=mission_like.get("effort"),
        mission_type=mission_like.get("mission_type"),
        dependency=mission_like.get("dependency"),
        alignment=mission_like.get("alignment"),
        recurrence=mission_like.get("recurrence"),
        payload=mission_like.get("payload"),
    )
    return preview_decision_framework_score(payload, priorities=priorities)


def build_mission_score_from_start_request(
    payload: StartMissionRequest,
    *,
    priorities: list[ImperiumUserPriority] | None = None,
) -> dict:
    if payload.domain is None:
        raise DecisionFrameworkValidationError("Mission score storage requires a mission domain.")

    mission_type = payload.mission_type if payload.mission_type is not None else payload.mission_type_category
    score_payload = DecisionFrameworkScorePreviewRequest(
        domain=payload.domain,
        title=payload.title,
        deadline_at=payload.deadline_at,
        impact=payload.impact,
        mission_type=mission_type,
        dependency=payload.dependency,
        recurrence=payload.recurrence,
        payload=None,
    )
    domain = normalize_domain(score_payload.domain)
    _domain_position, domain_coefficient = _priority_for_domain(domain, priorities=priorities)
    explanation = explain_score(score_payload, domain_coefficient=domain_coefficient)
    intrinsic_score = explanation.final_intrinsic_score
    weighted_score = compute_weighted_score(intrinsic_score, domain_coefficient)
    priority_bucket = _priority_bucket(weighted_score)
    score_status = _score_status(explanation)
    explanation_payload = explanation.model_dump(mode="json")
    explanation_payload.update(
        {
            "priority_bucket": priority_bucket,
            "score_status": score_status,
            "source": SOURCE,
        }
    )
    return {
        "domain": domain,
        "intrinsic_score": intrinsic_score,
        "domain_coefficient": domain_coefficient,
        "weighted_score": weighted_score,
        "explanation": explanation_payload,
        "source": SOURCE,
        "priority_bucket": priority_bucket,
        "score_status": score_status,
        "missing_fields": list(explanation.missing_fields),
    }


def mission_decision_score_summary_from_row(score: ImperiumMissionScore) -> MissionDecisionScoreSummary:
    explanation = score.explanation or {}
    return MissionDecisionScoreSummary(
        intrinsic_score=int(score.intrinsic_score),
        priority_bucket=int(explanation.get("priority_bucket", _priority_bucket(int(score.weighted_score)))),
        score_status=str(explanation.get("score_status", _score_status_from_explanation_payload(explanation))),
        missing_fields=list(explanation.get("missing_fields") or []),
        source=score.source,
    )


def mission_decision_score_read_from_row(score: ImperiumMissionScore) -> MissionDecisionScoreRead:
    explanation_payload = score.explanation or {}
    explanation = DecisionFrameworkScoreExplanation(
        deadline_points=int(explanation_payload.get("deadline_points", 0)),
        impact_points=int(explanation_payload.get("impact_points", 0)),
        mission_type_points=int(explanation_payload.get("mission_type_points", 0)),
        dependency_points=int(explanation_payload.get("dependency_points", 0)),
        recurrence_points=int(explanation_payload.get("recurrence_points", 0)),
        missing_fields=list(explanation_payload.get("missing_fields") or []),
        final_intrinsic_score=int(explanation_payload.get("final_intrinsic_score", score.intrinsic_score)),
        flags=list(explanation_payload.get("flags") or []),
    )
    return MissionDecisionScoreRead(
        mission_id=score.mission_id,
        domain=score.domain,
        intrinsic_score=int(score.intrinsic_score),
        priority_bucket=int(explanation_payload.get("priority_bucket", _priority_bucket(int(score.weighted_score)))),
        score_status=str(explanation_payload.get("score_status", _score_status(explanation))),
        explanation=explanation,
        missing_fields=list(explanation.missing_fields),
        source=score.source,
        created_at=score.created_at,
        updated_at=score.updated_at,
    )


def _get_active_user_priorities(db: Session, *, current_user: User) -> list[ImperiumUserPriority]:
    return list(
        db.scalars(
            select(ImperiumUserPriority)
            .where(
                ImperiumUserPriority.user_id == current_user.id,
                ImperiumUserPriority.is_active.is_(True),
            )
            .order_by(ImperiumUserPriority.position.asc(), ImperiumUserPriority.created_at.asc())
        )
    )


def _priorities_response(
    priorities: list[ImperiumUserPriority],
    *,
    status: str,
    idempotency_key: str | None = None,
) -> DecisionFrameworkPrioritiesResponse:
    sorted_priorities = sorted(priorities, key=lambda item: item.position)
    return DecisionFrameworkPrioritiesResponse(
        priorities=[DecisionFrameworkPriorityRead.model_validate(priority) for priority in sorted_priorities],
        idempotency_key=idempotency_key,
        status=status,
    )


def _validate_priority_domains(domains: list[str]) -> list[str]:
    normalized = [normalize_domain(domain) for domain in domains]
    if len(normalized) != len(SUPPORTED_DOMAINS):
        raise DecisionFrameworkValidationError("Exactly four decision framework domains are required.")
    if set(normalized) != set(SUPPORTED_DOMAINS):
        raise DecisionFrameworkValidationError("Domains must contain religious, business, finance, and health exactly once.")
    if len(normalized) != len(set(normalized)):
        raise DecisionFrameworkValidationError("Duplicate domains are not allowed.")
    return normalized


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
    request_path: str,
) -> DecisionFrameworkPrioritiesResponse:
    if existing_key.request_path != request_path:
        raise DecisionFrameworkIdempotencyConflictError("Idempotency-Key already used on a different endpoint.")
    if existing_key.request_hash != request_hash:
        raise DecisionFrameworkIdempotencyConflictError("Idempotency key already used with different payload.")
    if existing_key.response_body is None:
        raise DecisionFrameworkIdempotencyConflictError("Idempotency key is already processing.")
    return DecisionFrameworkPrioritiesResponse(**existing_key.response_body)


def _hash_payload(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _deadline_points(deadline_at: date | datetime | None, missing_fields: list[str], flags: list[str]) -> int:
    if deadline_at is None:
        missing_fields.append("deadline_at")
        return 0
    now = datetime.now(UTC)
    if isinstance(deadline_at, datetime):
        deadline = deadline_at if deadline_at.tzinfo is not None else deadline_at.replace(tzinfo=UTC)
        deadline_date = deadline.date()
    else:
        deadline_date = deadline_at
    delta_days = (deadline_date - now.date()).days
    if delta_days <= 0:
        if delta_days < 0:
            flags.append("deadline_past")
        return 30
    if delta_days <= 2:
        return 25
    if delta_days <= 6:
        return 20
    if delta_days <= 14:
        return 15
    if delta_days <= 30:
        return 10
    return 5


def _impact_points(data: dict, missing_fields: list[str], flags: list[str]) -> int:
    if data.get("impact") is not None:
        return _controlled_points(data["impact"], _IMPACT_POINTS, max_value=30, field_name="impact")
    for legacy_field in ("impact_points", "impact_level"):
        if data.get(legacy_field) is not None:
            flags.append(f"legacy_field:{legacy_field}")
            return _clamp_int(data[legacy_field], 0, 30)
    missing_fields.append("impact")
    return 0


def _mission_type_points(data: dict, missing_fields: list[str], flags: list[str]) -> int:
    if data.get("mission_type") is not None:
        return _controlled_points(data["mission_type"], _MISSION_TYPE_POINTS, max_value=20, field_name="mission_type")
    if data.get("effort") is not None:
        flags.append("canonical_alias:effort_used_for_mission_type")
        return _controlled_points(data["effort"], _MISSION_TYPE_POINTS, max_value=20, field_name="effort")
    for legacy_field in ("effort_points", "mission_type_points"):
        if data.get(legacy_field) is not None:
            flags.append(f"legacy_field:{legacy_field}")
            return _clamp_int(data[legacy_field], 0, 20)
    missing_fields.append("mission_type")
    return 0


def _dependency_points(data: dict, missing_fields: list[str]) -> int:
    if data.get("dependency") is not None:
        dependency = data["dependency"]
        if isinstance(dependency, bool):
            return 5 if dependency else 0
        return _controlled_points(dependency, _DEPENDENCY_POINTS, max_value=10, field_name="dependency")
    if data.get("dependency_points") is not None:
        return _clamp_int(data["dependency_points"], 0, 10)
    blocked_count = data.get("blocked_mission_count")
    if blocked_count is None:
        missing_fields.append("dependency")
        return 0
    if blocked_count <= 0:
        return 0
    if blocked_count <= 2:
        return 5
    return 10


def _recurrence_points(data: dict, missing_fields: list[str], flags: list[str]) -> int:
    recurrence = data.get("recurrence")
    if recurrence is not None:
        return _controlled_points(recurrence, _RECURRENCE_POINTS, max_value=10, field_name="recurrence")
    if data.get("alignment") is not None:
        flags.append("canonical_alias:alignment_used_for_recurrence")
        return _controlled_points(data["alignment"], _RECURRENCE_POINTS, max_value=10, field_name="alignment")
    if data.get("alignment_points") is not None:
        flags.append("legacy_field:alignment_points")
        return _clamp_int(data["alignment_points"], 0, 10)
    missing_fields.append("recurrence")
    return 0


def _controlled_points(value: object, mapping: dict[str, int], *, max_value: int, field_name: str) -> int:
    if isinstance(value, int):
        return _clamp_int(value, 0, max_value)
    normalized = _strip_accents(str(value)).strip().lower().replace(" ", "_").replace("-", "_")
    normalized = normalized.replace("__", "_")
    if normalized in mapping:
        return mapping[normalized]
    dashed = normalized.replace("_", "-")
    if dashed in mapping:
        return mapping[dashed]
    raise DecisionFrameworkValidationError(f"Unsupported {field_name} value: {value}.")


def _priority_for_domain(
    domain: str,
    *,
    priorities: list[ImperiumUserPriority] | None,
    fallback_position: int | None = None,
    fallback_coefficient: int | None = None,
) -> tuple[int, int]:
    if priorities:
        for priority in priorities:
            if priority.is_active and priority.domain == domain:
                return priority.position, priority.coefficient
    if fallback_position is not None and fallback_coefficient is not None:
        return fallback_position, fallback_coefficient
    default_position = DEFAULT_PRIORITY_ORDER.index(domain) + 1
    return default_position, get_domain_coefficient(default_position)


def _unsafe_payload_warnings(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return []
    warnings: list[str] = []
    for key in payload:
        normalized = _strip_accents(str(key)).strip().lower()
        if any(marker in normalized for marker in _UNSAFE_PAYLOAD_MARKERS):
            warnings.append("sanitized_payload_field")
    return warnings


def _legacy_field_warnings(data: dict) -> list[str]:
    return [f"legacy_field:{field}" for field in _LEGACY_SCORE_FIELDS if data.get(field) is not None]


def _build_breakdown(explanation: DecisionFrameworkScoreExplanation) -> list[DecisionFrameworkScoreBreakdownItem]:
    return [
        DecisionFrameworkScoreBreakdownItem(
            label="Deadline proximity",
            key="deadline",
            points=explanation.deadline_points,
            max_points=30,
            reason=_reason_for_points(explanation.deadline_points, missing="deadline_at" in explanation.missing_fields),
        ),
        DecisionFrameworkScoreBreakdownItem(
            label="Impact gravity",
            key="impact",
            points=explanation.impact_points,
            max_points=30,
            reason=_reason_for_points(explanation.impact_points, missing="impact" in explanation.missing_fields),
        ),
        DecisionFrameworkScoreBreakdownItem(
            label="Mission type",
            key="mission_type",
            points=explanation.mission_type_points,
            max_points=20,
            reason=_reason_for_points(explanation.mission_type_points, missing="mission_type" in explanation.missing_fields),
        ),
        DecisionFrameworkScoreBreakdownItem(
            label="Dependency",
            key="dependency",
            points=explanation.dependency_points,
            max_points=10,
            reason=_reason_for_points(explanation.dependency_points, missing="dependency" in explanation.missing_fields),
        ),
        DecisionFrameworkScoreBreakdownItem(
            label="Recurrence",
            key="recurrence",
            points=explanation.recurrence_points,
            max_points=10,
            reason=_reason_for_points(
                explanation.recurrence_points,
                missing="recurrence" in explanation.missing_fields,
            ),
        ),
    ]


def _reason_for_points(points: int, *, missing: bool) -> str:
    if missing:
        return "Missing input; scored as 0."
    if points == 0:
        return "Input provided with no additional priority points."
    return f"Deterministic rule assigned {points} points."


def _score_status(explanation: DecisionFrameworkScoreExplanation) -> str:
    if len(explanation.missing_fields) == 5 and explanation.final_intrinsic_score == 0:
        return "empty"
    if explanation.missing_fields:
        return "partial"
    return "complete"


def _score_status_from_explanation_payload(explanation: dict) -> str:
    missing_fields = list(explanation.get("missing_fields") or [])
    intrinsic_score = int(explanation.get("final_intrinsic_score") or 0)
    if len(missing_fields) == 5 and intrinsic_score == 0:
        return "empty"
    if missing_fields:
        return "partial"
    return "complete"


def _display_title(payload: DecisionFrameworkScorePreviewRequest) -> str:
    if payload.title:
        return payload.title
    return "Mission preview"


def _display_summary(*, domain: str, domain_position: int, score_status: str, missing_count: int) -> str:
    if score_status == "complete":
        return f"Mission {domain} classee selon la position {domain_position}. Score complet."
    if score_status == "empty":
        return f"Mission {domain} classee selon la position {domain_position}. Aucun signal de scoring fourni."
    return f"Mission {domain} classee selon la position {domain_position}. Score partiel car {missing_count} signaux sont manquants."


def _priority_bucket(weighted_score: int) -> int:
    if weighted_score >= 700:
        return 10
    if weighted_score >= 600:
        return 9
    if weighted_score >= 500:
        return 8
    if weighted_score >= 400:
        return 7
    if weighted_score >= 300:
        return 6
    if weighted_score >= 200:
        return 5
    if weighted_score >= 100:
        return 4
    if weighted_score >= 50:
        return 3
    if weighted_score >= 20:
        return 2
    return 1


def _clamp_int(value: object, lower: int, upper: int) -> int:
    try:
        integer = int(value)
    except (TypeError, ValueError) as exc:
        raise DecisionFrameworkValidationError("Score fields must be integers.") from exc
    return max(lower, min(upper, integer))


def _strip_accents(value: str) -> str:
    return "".join(character for character in unicodedata.normalize("NFKD", value) if not unicodedata.combining(character))
