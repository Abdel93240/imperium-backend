"""Journal central des appels IA (doc 43 §17, doc 78 F2-14) — « ALL STEPS LOGGED ».

record() est appelé par les providers juste après un appel réel (jamais en dry-run). Il écrit
dans sa propre session : la ligne survit au rollback de l'appelant (un appel raté reste un
appel) et un échec d'écriture n'interrompt jamais l'appelant (journalisé en warning).

Rien du contenu ne sort ici : ni prompt, ni réponse, ni texte reconnu. Coût : 0 pour un
appel local ; le coût donné par l'appelant (estimation de la CLI d'abonnement) ; sinon le trigger SQL le
calcule depuis `ai_model_pricing`, NULL sans prix connu.
"""

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.ai import AICallLog

logger = logging.getLogger(__name__)

APP_NAMES = frozenset({"imperium", "vector", "vault", "pulse", "path"})
MODEL_TIERS = frozenset({"local", "cloud_cheap", "cloud_standard", "cloud_premium"})

# Remplacé par les tests ; par défaut, la fabrique de sessions de l'application.
_session_factory: Callable[[], Session] | None = None


def record(
    *,
    app_name: str,
    task_type: str,
    model_tier: str,
    model_used: str | None = None,
    model_role: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    duration_ms: int | None = None,
    success: bool = True,
    error_code: str | None = None,
    trigger_source: str | None = None,
    related_entity_type: str | None = None,
    related_entity_id: Any = None,
    cost_eur: Decimal | None = None,
) -> None:
    if app_name not in APP_NAMES:
        raise ValueError(f"Unknown app_name '{app_name}'.")
    if model_tier not in MODEL_TIERS:
        raise ValueError(f"Unknown model_tier '{model_tier}'.")
    if (model_used is None) == (model_role is None):
        raise ValueError("Give exactly one of model_used or model_role.")
    try:
        with _new_session() as session:
            if model_used is None:
                model_used = _role_model_id(session, model_role)
            session.add(AICallLog(
                app_name=app_name, task_type=task_type[:64], model_used=model_used[:48], model_tier=model_tier,
                input_tokens=input_tokens, output_tokens=output_tokens, duration_ms=duration_ms, success=success,
                error_code=error_code, trigger_source=trigger_source, related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
                cost_eur=Decimal("0") if model_tier == "local" else cost_eur,
            ))
            session.commit()
    except Exception:  # noqa: BLE001 - le journal ne casse jamais l'appel journalisé
        logger.warning("AI call log write failed.", extra={"task_type": task_type}, exc_info=True)


@contextmanager
def timed() -> Iterator[Callable[[], int]]:
    """Chronomètre en millisecondes : `with timed() as elapsed: ...; elapsed()`."""
    start = time.monotonic()
    yield lambda: int((time.monotonic() - start) * 1000)


def _role_model_id(session: Session, role_code: str) -> str:
    """Identifiant réel du rôle (ai_role_models) ; le code du rôle à défaut."""
    from app.services.ai.roles import RoleResolutionError, resolve_model_id

    try:
        return resolve_model_id(role_code, db=session)
    except RoleResolutionError:
        return role_code


def _new_session() -> Session:
    factory = _session_factory
    if factory is None:
        from app.db.session import SessionLocal

        factory = SessionLocal
    return factory()


class AICallLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    called_at: datetime
    app_name: str
    task_type: str
    model_used: str
    model_tier: str
    input_tokens: int | None
    output_tokens: int | None
    cost_eur: Decimal | None
    duration_ms: int | None
    success: bool
    error_code: str | None


class AICallLogListResponse(BaseModel):
    calls: list[AICallLogRead]


class AIDailySpendRead(BaseModel):
    day: date
    total_calls: int
    local_calls: int
    cheap_calls: int
    standard_calls: int
    premium_calls: int
    total_cost_eur: Decimal | None
    premium_cost_eur: Decimal | None
    errors: int


class AIDailySpendResponse(BaseModel):
    days: list[AIDailySpendRead]


def list_calls(db: Session, *, limit: int) -> AICallLogListResponse:
    rows = db.scalars(select(AICallLog).order_by(AICallLog.called_at.desc()).limit(limit))
    return AICallLogListResponse(calls=[AICallLogRead.model_validate(row) for row in rows])


def daily_spend(db: Session, *, days: int) -> AIDailySpendResponse:
    rows = db.execute(
        text("SELECT * FROM ai_daily_spend WHERE day > (now() AT TIME ZONE 'Europe/Paris')::date - :days "
             "ORDER BY day DESC"),
        {"days": days},
    ).mappings()
    return AIDailySpendResponse(days=[AIDailySpendRead(**row) for row in rows])


class AICallAlertRead(BaseModel):
    code: str
    message_fr: str
    value: float
    threshold: float


class AICallAlertsResponse(BaseModel):
    alerts: list[AICallAlertRead]
