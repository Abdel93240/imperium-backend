"""Decision Framework (doc 52) : score intrinsèque A-E, coefficient de domaine, bucket de priorité.

Barèmes externalisés (spec Daily §4, carte ACT-DLY-01) : les valeurs vivent dans les paramètres
versionnés `df.*`, semés À L'IDENTIQUE depuis les constantes ci-dessous (`CODE_SCALES`). Le service
lit `load_scales(db)` (cache mémoire par version de paramètre) ; sans paramètre ou avec un paramètre
invalide, il retombe sur `CODE_SCALES` (journalisé). Parité prouvée par tests dorés
(tests/fixtures/df_golden_scores.json). `imperium_user_priorities` reste la source de l'ORDRE des
domaines ; les VALEURS des coefficients deviennent des paramètres.
"""

import hashlib
import json
import logging
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select, text
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
    MissionDecisionScoreSummary,
    StartMissionRequest,
)

SUPPORTED_DOMAINS = ("religious", "business", "finance", "health")
DEFAULT_PRIORITY_ORDER = ("religious", "business", "finance", "health")
COEFFICIENT_BY_POSITION = {1: 10, 2: 8, 3: 5, 4: 4}
SOURCE = "decision_framework_v1"

logger = logging.getLogger(__name__)

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

_DEADLINE_POINTS = {"overdue_or_today": 30, "bands": [[2, 25], [6, 20], [14, 15], [30, 10]], "beyond": 5}
_DEPENDENCY_SCALE = {"bool_true": 5, "bool_false": 0, "blocked_count_bands": [[0, 0], [2, 5]], "blocked_count_beyond": 10}
_CRITERION_MAX = {"deadline": 30, "impact": 30, "mission_type": 20, "dependency": 10, "recurrence": 10}
_PRIORITY_BUCKETS = [[700, 10], [600, 9], [500, 8], [400, 7], [300, 6], [200, 5], [100, 4], [50, 3], [20, 2]]
_PRIORITY_BUCKET_FLOOR = 1


@dataclass(frozen=True)
class ScoringScales:
    """Barèmes du doc 52 : une instance = un jeu de versions des paramètres `df.*`."""

    deadline: dict
    impact: dict
    mission_type: dict
    dependency_labels: dict
    dependency: dict
    recurrence: dict
    criterion_max: dict
    coefficient_by_position: dict
    priority_buckets: list
    priority_bucket_floor: int


CODE_SCALES = ScoringScales(
    deadline=_DEADLINE_POINTS, impact=_IMPACT_POINTS, mission_type=_MISSION_TYPE_POINTS,
    dependency_labels=_DEPENDENCY_POINTS, dependency=_DEPENDENCY_SCALE, recurrence=_RECURRENCE_POINTS,
    criterion_max=_CRITERION_MAX, coefficient_by_position=COEFFICIENT_BY_POSITION, priority_buckets=_PRIORITY_BUCKETS,
    priority_bucket_floor=_PRIORITY_BUCKET_FLOOR,
)

# Paramètre `df.*` → champ(s) de ScoringScales ; la valeur semée = CODE_SCALES (migration 0101).
SCALE_PARAMETERS = {
    "df.deadline_points": "deadline",
    "df.impact_points": "impact",
    "df.mission_type_points": "mission_type",
    "df.dependency_points": "dependency",
    "df.recurrence_points": "recurrence",
    "df.criterion_max": "criterion_max",
    "df.coefficient_by_position": "coefficient_by_position",
    "df.priority_buckets": "priority_buckets",
}
_scales_cache: dict[tuple, ScoringScales] = {}

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


def scale_parameter_values(scales: ScoringScales = CODE_SCALES) -> dict[str, object]:
    """Valeurs JSON des paramètres `df.*` pour un jeu de barèmes (seed et lecture partagent ce format)."""
    return {
        "df.deadline_points": scales.deadline,
        "df.impact_points": scales.impact,
        "df.mission_type_points": scales.mission_type,
        "df.dependency_points": {"labels": scales.dependency_labels, **scales.dependency},
        "df.recurrence_points": scales.recurrence,
        "df.criterion_max": scales.criterion_max,
        "df.coefficient_by_position": {str(position): value for position, value in scales.coefficient_by_position.items()},
        "df.priority_buckets": {"thresholds": scales.priority_buckets, "floor": scales.priority_bucket_floor},
    }


def scales_from_parameter_values(values: dict[str, object]) -> ScoringScales:
    """Construit et valide un jeu de barèmes ; ValueError si une valeur est mal formée."""
    def bands(code: str, raw, *, descending: bool) -> list:
        if not isinstance(raw, list) or not all(
                isinstance(band, list) and len(band) == 2 and all(_is_int(x) for x in band) for band in raw):
            raise ValueError(f"{code}: expected a list of [bound, points] pairs")
        bounds = [band[0] for band in raw]
        if bounds != sorted(bounds, reverse=descending) or len(set(bounds)) != len(bounds):
            raise ValueError(f"{code}: bounds must be strictly {'decreasing' if descending else 'increasing'}")
        return [list(band) for band in raw]

    criterion_max = values["df.criterion_max"]
    if not isinstance(criterion_max, dict) or set(criterion_max) != set(_CRITERION_MAX) or not all(
            _is_int(v) and v >= 0 for v in criterion_max.values()) or sum(criterion_max.values()) > 100:
        raise ValueError("df.criterion_max: the five criteria A-E with non-negative maxima summing to at most 100")
    deadline = values["df.deadline_points"]
    if not isinstance(deadline, dict) or set(deadline) != {"overdue_or_today", "bands", "beyond"}:
        raise ValueError("df.deadline_points: expected overdue_or_today, bands, beyond")
    deadline_bands = bands("df.deadline_points", deadline["bands"], descending=False)
    if not all(_is_int(deadline[key]) for key in ("overdue_or_today", "beyond")) or not all(
            0 <= p <= criterion_max["deadline"] for p in
            [deadline["overdue_or_today"], deadline["beyond"], *(band[1] for band in deadline_bands)]):
        raise ValueError("df.deadline_points: points out of range")
    dependency = values["df.dependency_points"]
    if not isinstance(dependency, dict) or set(dependency) != {"labels", *_DEPENDENCY_SCALE}:
        raise ValueError("df.dependency_points: expected labels, bool_true, bool_false, blocked_count_bands, "
                         "blocked_count_beyond")
    dependency_labels = _points_map(dependency["labels"], "df.dependency_points", criterion_max["dependency"])
    blocked = bands("df.dependency_points", dependency["blocked_count_bands"], descending=False)
    if not all(_is_int(dependency[key]) and 0 <= dependency[key] <= criterion_max["dependency"]
               for key in ("bool_true", "bool_false", "blocked_count_beyond")):
        raise ValueError("df.dependency_points: points out of range")
    coefficients = values["df.coefficient_by_position"]
    if not isinstance(coefficients, dict) or set(coefficients) != {"1", "2", "3", "4"} or not all(
            _is_int(v) and v > 0 for v in coefficients.values()):
        raise ValueError("df.coefficient_by_position: positions 1-4 with positive coefficients")
    buckets = values["df.priority_buckets"]
    if not isinstance(buckets, dict) or set(buckets) != {"thresholds", "floor"} or not _is_int(buckets["floor"]):
        raise ValueError("df.priority_buckets: expected thresholds and floor")
    return ScoringScales(
        deadline={"overdue_or_today": deadline["overdue_or_today"], "bands": deadline_bands,
                  "beyond": deadline["beyond"]},
        impact=_points_map(values["df.impact_points"], "df.impact_points", criterion_max["impact"]),
        mission_type=_points_map(values["df.mission_type_points"], "df.mission_type_points", criterion_max["mission_type"]),
        dependency_labels=dependency_labels,
        dependency={"bool_true": dependency["bool_true"], "bool_false": dependency["bool_false"],
                    "blocked_count_bands": blocked, "blocked_count_beyond": dependency["blocked_count_beyond"]},
        recurrence=_points_map(values["df.recurrence_points"], "df.recurrence_points", criterion_max["recurrence"]),
        criterion_max=dict(criterion_max),
        coefficient_by_position={int(position): value for position, value in coefficients.items()},
        priority_buckets=bands("df.priority_buckets", buckets["thresholds"], descending=True),
        priority_bucket_floor=buckets["floor"],
    )


def _points_map(mapping, code: str, upper: int) -> dict:
    if not isinstance(mapping, dict) or not mapping or not all(
            isinstance(k, str) and _is_int(v) and 0 <= v <= upper for k, v in mapping.items()):
        raise ValueError(f"{code}: expected a non-empty map of labels to points in 0..{upper}")
    return dict(mapping)


def load_scales(db: Session) -> ScoringScales:
    """Barèmes courants depuis `df.*` ; cache par (code, version) ; repli sur CODE_SCALES si absent ou invalide."""
    rows = db.execute(
        text("SELECT code, version, value FROM v_parameters_current WHERE code = ANY(:codes) ORDER BY code"),
        {"codes": list(SCALE_PARAMETERS)},
    ).all()
    if len(rows) != len(SCALE_PARAMETERS):
        if rows:
            logger.warning("Incomplete df.* parameters: code scales used.", extra={"found": [row[0] for row in rows]})
        return CODE_SCALES
    key = tuple((row[0], row[1]) for row in rows)
    cached = _scales_cache.get(key)
    if cached is not None:
        return cached
    try:
        scales = scales_from_parameter_values({row[0]: row[2] for row in rows})
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("Invalid df.* parameters: code scales used.", extra={"error": str(exc)})
        return CODE_SCALES
    _scales_cache.clear()
    _scales_cache[key] = scales
    return scales


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


class DecisionFrameworkIdempotencyConflictError(ValueError):
    pass


def normalize_domain(domain: str) -> str:
    normalized = _strip_accents(domain).strip().lower().replace("_", "-").replace(" ", "-")
    canonical = _DOMAIN_ALIASES.get(normalized)
    if canonical is None:
        raise DecisionFrameworkValidationError(f"Unsupported decision framework domain: {domain}.")
    return canonical


def get_domain_coefficient(position: int, scales: ScoringScales = CODE_SCALES) -> int:
    try:
        return scales.coefficient_by_position[position]
    except KeyError as exc:
        raise DecisionFrameworkValidationError("Priority position must be between 1 and 4.") from exc


def get_or_initialize_user_priorities(db: Session, *, current_user: User) -> DecisionFrameworkPrioritiesResponse:
    priorities = get_canonical_priority_order(db, current_user=current_user)
    return _priorities_response(priorities, status="ok")


def get_user_priority_context(db: Session, *, current_user: User) -> list[ImperiumUserPriority]:
    return get_canonical_priority_order(db, current_user=current_user)


def get_canonical_priority_order(
    db: Session,
    *,
    current_user: User,
) -> list[ImperiumUserPriority]:
    """Return the Decision Framework priority hierarchy in canonical order.

    `imperium_user_priorities` is the canonical read source. When no persisted
    rows exist yet, callers receive the deterministic V1 default as transient
    context. Persistent initialization must go through an explicit POST flow.
    """

    priorities = _get_active_user_priorities(db, current_user=current_user)
    if priorities:
        return sorted(priorities, key=lambda item: item.position)
    return _build_default_priorities(current_user=current_user, transient=True, scales=load_scales(db))


def _build_default_priorities(
    *,
    current_user: User,
    transient: bool = False,
    scales: ScoringScales = CODE_SCALES,
) -> list[ImperiumUserPriority]:
    now = datetime.now(UTC)
    return [
        ImperiumUserPriority(
            id=_transient_priority_id(current_user=current_user, domain=domain) if transient else None,
            user_id=current_user.id,
            domain=domain,
            position=position,
            coefficient=get_domain_coefficient(position, scales),
            is_active=True,
            created_at=now if transient else None,
            updated_at=now if transient else None,
        )
        for position, domain in enumerate(DEFAULT_PRIORITY_ORDER, start=1)
    ]


def _transient_priority_id(*, current_user: User, domain: str):
    return uuid5(NAMESPACE_URL, f"imperium:user-priority:{current_user.id}:{domain}:v1-default")


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
    scales = load_scales(db)

    new_priorities = [
        ImperiumUserPriority(
            user_id=current_user.id,
            domain=domain,
            position=position,
            coefficient=get_domain_coefficient(position, scales),
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


def compute_intrinsic_score(
    candidate: DecisionFrameworkScorePreviewRequest | dict, scales: ScoringScales = CODE_SCALES
) -> int:
    explanation = explain_score(candidate, scales=scales)
    return explanation.final_intrinsic_score


def compute_weighted_score(intrinsic_score: int, domain_coefficient: int) -> int:
    return _clamp_int(intrinsic_score, 0, 100) * domain_coefficient


def explain_score(
    candidate: DecisionFrameworkScorePreviewRequest | dict,
    *,
    domain_position: int | None = None,
    domain_coefficient: int | None = None,
    scales: ScoringScales = CODE_SCALES,
) -> DecisionFrameworkScoreExplanation:
    _ = (domain_position, domain_coefficient)
    data = candidate.model_dump() if isinstance(candidate, DecisionFrameworkScorePreviewRequest) else dict(candidate)
    missing_fields: list[str] = []
    flags: list[str] = []

    deadline_points = _deadline_points(data.get("deadline_at"), missing_fields, flags, scales)
    impact_points = _impact_points(data, missing_fields, flags, scales)
    mission_type_points = _mission_type_points(data, missing_fields, flags, scales)
    dependency_points = _dependency_points(data, missing_fields, scales)
    recurrence_points = _recurrence_points(data, missing_fields, flags, scales)

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
    scales: ScoringScales = CODE_SCALES,
) -> DecisionFrameworkScorePreviewResponse:
    domain = normalize_domain(payload.domain)
    domain_position, domain_coefficient = _priority_for_domain(domain, priorities=priorities, scales=scales)
    explanation = explain_score(
        payload,
        domain_position=domain_position,
        domain_coefficient=domain_coefficient,
        scales=scales,
    )
    weighted_score = compute_weighted_score(explanation.final_intrinsic_score, domain_coefficient)
    breakdown = _build_breakdown(explanation, scales)
    missing_fields = list(explanation.missing_fields)
    score_status = _score_status(explanation)
    return DecisionFrameworkScorePreviewResponse(
        domain=domain,
        domain_position=domain_position,
        intrinsic_score=explanation.final_intrinsic_score,
        priority_bucket=_priority_bucket(weighted_score, scales),
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
    scales: ScoringScales = CODE_SCALES,
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
    return preview_decision_framework_score(payload, priorities=priorities, scales=scales)


def build_mission_score_from_start_request(
    payload: StartMissionRequest,
    *,
    priorities: list[ImperiumUserPriority] | None = None,
    scales: ScoringScales = CODE_SCALES,
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
    _domain_position, domain_coefficient = _priority_for_domain(domain, priorities=priorities, scales=scales)
    explanation = explain_score(score_payload, domain_coefficient=domain_coefficient, scales=scales)
    intrinsic_score = explanation.final_intrinsic_score
    weighted_score = compute_weighted_score(intrinsic_score, domain_coefficient)
    priority_bucket = _priority_bucket(weighted_score, scales)
    score_status = _score_status(explanation)
    explanation_payload = explanation.model_dump(mode="json")
    explanation_payload.update(
        {
            "priority_bucket": priority_bucket,
            "score_status": score_status,
            "source": SOURCE,
            # Entrées A-E gardées pour le refresh (ACT-DLY-03) : un barème changé se rejoue en entier.
            "inputs": score_payload.model_dump(
                mode="json", include={"impact", "mission_type", "dependency", "recurrence"}),
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


def rescore(
    score: ImperiumMissionScore,
    *,
    deadline_at: date | datetime | None,
    priorities: list[ImperiumUserPriority] | None,
    scales: ScoringScales,
) -> bool:
    """Refresh d'une ligne du registre (spec Daily §4.6) ; True si elle a changé.

    Avec `explanation.inputs` (lignes écrites depuis ACT-DLY-03) : score rejoué en entier avec les barèmes
    courants. Sans (lignes plus anciennes) : seul le critère A est recalculé (l'échéance vieillit), les
    points B-E stockés sont gardés tels quels. Dans les deux cas, coefficient et bucket suivent les
    barèmes et la hiérarchie courants.
    """
    explanation = dict(score.explanation or {})
    inputs = explanation.get("inputs")
    if isinstance(inputs, dict):
        fresh = explain_score({**inputs, "deadline_at": deadline_at}, scales=scales)
    else:
        missing = [field for field in explanation.get("missing_fields") or [] if field != "deadline_at"]
        flags = [flag for flag in explanation.get("flags") or [] if flag != "deadline_past"]
        new_missing: list[str] = []
        deadline_points = _deadline_points(deadline_at, new_missing, flags, scales)
        points = {key: int(explanation.get(f"{key}_points") or 0)
                  for key in ("impact", "mission_type", "dependency", "recurrence")}
        fresh = DecisionFrameworkScoreExplanation(
            deadline_points=deadline_points, **{f"{key}_points": value for key, value in points.items()},
            missing_fields=new_missing + missing, flags=flags,
            final_intrinsic_score=_clamp_int(deadline_points + sum(points.values()), 0, 100),
        )
    _position, coefficient = _priority_for_domain(score.domain, priorities=priorities, scales=scales)
    weighted = compute_weighted_score(fresh.final_intrinsic_score, coefficient)
    payload = fresh.model_dump(mode="json")
    payload.update({"priority_bucket": _priority_bucket(weighted, scales), "score_status": _score_status(fresh),
                    "source": SOURCE})
    if isinstance(inputs, dict):
        payload["inputs"] = inputs
    if (int(score.intrinsic_score), score.domain_coefficient, int(score.weighted_score), explanation) == (
            fresh.final_intrinsic_score, coefficient, weighted, payload):
        return False
    score.intrinsic_score, score.domain_coefficient, score.weighted_score = (
        fresh.final_intrinsic_score, coefficient, weighted)
    score.explanation = payload
    return True


def mission_decision_score_summary_from_row(
    score: ImperiumMissionScore, scales: ScoringScales = CODE_SCALES
) -> MissionDecisionScoreSummary:
    explanation = score.explanation or {}
    return MissionDecisionScoreSummary(
        intrinsic_score=int(score.intrinsic_score),
        priority_bucket=int(explanation.get("priority_bucket", _priority_bucket(int(score.weighted_score), scales))),
        score_status=str(explanation.get("score_status", _score_status_from_explanation_payload(explanation))),
        missing_fields=list(explanation.get("missing_fields") or []),
        source=score.source,
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


def _deadline_points(
    deadline_at: date | datetime | None, missing_fields: list[str], flags: list[str], scales: ScoringScales
) -> int:
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
        return scales.deadline["overdue_or_today"]
    for max_days, points in scales.deadline["bands"]:
        if delta_days <= max_days:
            return points
    return scales.deadline["beyond"]


def _impact_points(data: dict, missing_fields: list[str], flags: list[str], scales: ScoringScales) -> int:
    upper = scales.criterion_max["impact"]
    if data.get("impact") is not None:
        return _controlled_points(data["impact"], scales.impact, max_value=upper, field_name="impact")
    for legacy_field in ("impact_points", "impact_level"):
        if data.get(legacy_field) is not None:
            flags.append(f"legacy_field:{legacy_field}")
            return _clamp_int(data[legacy_field], 0, upper)
    missing_fields.append("impact")
    return 0


def _mission_type_points(data: dict, missing_fields: list[str], flags: list[str], scales: ScoringScales) -> int:
    upper = scales.criterion_max["mission_type"]
    if data.get("mission_type") is not None:
        return _controlled_points(data["mission_type"], scales.mission_type, max_value=upper, field_name="mission_type")
    if data.get("effort") is not None:
        flags.append("canonical_alias:effort_used_for_mission_type")
        return _controlled_points(data["effort"], scales.mission_type, max_value=upper, field_name="effort")
    for legacy_field in ("effort_points", "mission_type_points"):
        if data.get(legacy_field) is not None:
            flags.append(f"legacy_field:{legacy_field}")
            return _clamp_int(data[legacy_field], 0, upper)
    missing_fields.append("mission_type")
    return 0


def _dependency_points(data: dict, missing_fields: list[str], scales: ScoringScales) -> int:
    upper = scales.criterion_max["dependency"]
    if data.get("dependency") is not None:
        dependency = data["dependency"]
        if isinstance(dependency, bool):
            return scales.dependency["bool_true"] if dependency else scales.dependency["bool_false"]
        return _controlled_points(dependency, scales.dependency_labels, max_value=upper, field_name="dependency")
    if data.get("dependency_points") is not None:
        return _clamp_int(data["dependency_points"], 0, upper)
    blocked_count = data.get("blocked_mission_count")
    if blocked_count is None:
        missing_fields.append("dependency")
        return 0
    for max_count, points in scales.dependency["blocked_count_bands"]:
        if blocked_count <= max_count:
            return points
    return scales.dependency["blocked_count_beyond"]


def _recurrence_points(data: dict, missing_fields: list[str], flags: list[str], scales: ScoringScales) -> int:
    upper = scales.criterion_max["recurrence"]
    recurrence = data.get("recurrence")
    if recurrence is not None:
        return _controlled_points(recurrence, scales.recurrence, max_value=upper, field_name="recurrence")
    if data.get("alignment") is not None:
        flags.append("canonical_alias:alignment_used_for_recurrence")
        return _controlled_points(data["alignment"], scales.recurrence, max_value=upper, field_name="alignment")
    if data.get("alignment_points") is not None:
        flags.append("legacy_field:alignment_points")
        return _clamp_int(data["alignment_points"], 0, upper)
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
    scales: ScoringScales = CODE_SCALES,
) -> tuple[int, int]:
    if priorities:
        for priority in priorities:
            if priority.is_active and priority.domain == domain:
                return priority.position, priority.coefficient
    if fallback_position is not None and fallback_coefficient is not None:
        return fallback_position, fallback_coefficient
    default_position = DEFAULT_PRIORITY_ORDER.index(domain) + 1
    return default_position, get_domain_coefficient(default_position, scales)


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


def _build_breakdown(
    explanation: DecisionFrameworkScoreExplanation, scales: ScoringScales = CODE_SCALES
) -> list[DecisionFrameworkScoreBreakdownItem]:
    maxima = scales.criterion_max
    return [
        DecisionFrameworkScoreBreakdownItem(
            label="Deadline proximity",
            key="deadline",
            points=explanation.deadline_points,
            max_points=maxima["deadline"],
            reason=_reason_for_points(explanation.deadline_points, missing="deadline_at" in explanation.missing_fields),
        ),
        DecisionFrameworkScoreBreakdownItem(
            label="Impact gravity",
            key="impact",
            points=explanation.impact_points,
            max_points=maxima["impact"],
            reason=_reason_for_points(explanation.impact_points, missing="impact" in explanation.missing_fields),
        ),
        DecisionFrameworkScoreBreakdownItem(
            label="Mission type",
            key="mission_type",
            points=explanation.mission_type_points,
            max_points=maxima["mission_type"],
            reason=_reason_for_points(explanation.mission_type_points, missing="mission_type" in explanation.missing_fields),
        ),
        DecisionFrameworkScoreBreakdownItem(
            label="Dependency",
            key="dependency",
            points=explanation.dependency_points,
            max_points=maxima["dependency"],
            reason=_reason_for_points(explanation.dependency_points, missing="dependency" in explanation.missing_fields),
        ),
        DecisionFrameworkScoreBreakdownItem(
            label="Recurrence",
            key="recurrence",
            points=explanation.recurrence_points,
            max_points=maxima["recurrence"],
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


def _priority_bucket(weighted_score: int, scales: ScoringScales = CODE_SCALES) -> int:
    for threshold, bucket in scales.priority_buckets:
        if weighted_score >= threshold:
            return bucket
    return scales.priority_bucket_floor


def _clamp_int(value: object, lower: int, upper: int) -> int:
    try:
        integer = int(value)
    except (TypeError, ValueError) as exc:
        raise DecisionFrameworkValidationError("Score fields must be integers.") from exc
    return max(lower, min(upper, integer))


def _strip_accents(value: str) -> str:
    return "".join(character for character in unicodedata.normalize("NFKD", value) if not unicodedata.combining(character))
