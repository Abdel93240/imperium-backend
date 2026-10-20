"""Slots IA branchés sur l'exécuteur LOCAL de la Tower, un par un (décision utilisateur : local seulement).

Interrupteur par slot : le paramètre `ai.local_slot_modes` ({slot_code: off|shadow|live}, semé vide). Un
slot n'est jamais servi s'il n'est pas `local_default` dans `ai_slot_transition` (aucun slot prévu pour le
cloud ne passe ici) ni si l'URL de l'exécuteur n'est pas une adresse de bouclage : rien ne quitte la
machine. `real_ai_enabled` (chaînes cloud ou non codées) reste indépendant et éteint.

- shadow : le modèle tourne pour de vrai, sa sortie est enregistrée À CÔTÉ du résultat déterministe,
  rien n'est présenté ni appliqué ;
- live : sa sortie (validée) remplace le résultat factice ; une proposition reste soumise à décision.

Appel : chat completions, température 0, sans raisonnement, sortie contrainte par le JSON Schema du slot
(même format que le smoke `ops/gpu/local_executor_smoke.py`). Chaque appel, réussi ou non, va au journal
central des appels IA (aucun contenu n'y est écrit).
"""

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.toolbox import AISlotTransition
from app.services.ai import call_log
from app.services.ai.roles import LOCAL_EXECUTOR_ROLE
from app.services.params import get_parameter

MODES = ("off", "shadow", "live")
LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})

# Remplacé par les tests : (url, payload, timeout) -> réponse JSON.
_http_post: Callable[[str, dict, int], dict] | None = None


class LocalExecutorError(RuntimeError):
    pass


@dataclass(frozen=True)
class LocalResult:
    output: dict
    prompt_tokens: int | None
    output_tokens: int | None
    latency_ms: int


def slot_mode(db: Session, slot_code: str) -> str:
    """Mode effectif du slot : `off` dès qu'une condition de sûreté manque."""
    mode = (get_parameter(db, "ai.local_slot_modes", default={}) or {}).get(slot_code, "off")
    if mode not in MODES or mode == "off":
        return "off"
    tier = db.scalar(select(AISlotTransition.tier).where(AISlotTransition.slot_code == slot_code))
    if tier != "local_default" or not _loopback(get_settings().local_executor_url):
        return "off"
    return mode


def structured(*, slot_code: str, app_name: str, system: str, user: str, schema: dict,
               max_tokens: int = 512, related_entity_type: str | None = None,
               related_entity_id: Any = None) -> LocalResult:
    """Un appel contraint au schéma ; lève LocalExecutorError (réseau, statut, JSON invalide)."""
    settings = get_settings()
    base = settings.local_executor_url
    if not _loopback(base):
        raise LocalExecutorError("The local executor URL must be a loopback address.")
    payload = {
        "model": LOCAL_EXECUTOR_ROLE, "temperature": 0, "max_tokens": max_tokens, "thinking_budget_tokens": 0,
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": slot_code.replace(".", "_"), "strict": True, "schema": schema}},
    }
    post = _http_post or _post_json
    log = {"app_name": app_name, "task_type": slot_code, "model_tier": "local", "model_role": LOCAL_EXECUTOR_ROLE,
           "related_entity_type": related_entity_type, "related_entity_id": related_entity_id}
    with call_log.timed() as elapsed:
        try:
            body = post(base.rstrip("/") + "/v1/chat/completions", payload, settings.local_executor_timeout_seconds)
            choice = body["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise LocalExecutorError(f"Generation stopped early: {choice.get('finish_reason')}.")
            output = json.loads(choice["message"]["content"])
            if not isinstance(output, dict):
                raise LocalExecutorError("The model output is not a JSON object.")
        except (LocalExecutorError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            call_log.record(**log, duration_ms=elapsed(), success=False, error_code=type(exc).__name__[:32])
            raise LocalExecutorError(str(exc)) from exc
    usage = body.get("usage") or {}
    result = LocalResult(output=output, prompt_tokens=usage.get("prompt_tokens"),
                         output_tokens=usage.get("completion_tokens"), latency_ms=elapsed())
    call_log.record(**log, input_tokens=result.prompt_tokens, output_tokens=result.output_tokens,
                    duration_ms=result.latency_ms)
    return result


def _loopback(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.scheme == "http" and parsed.hostname in LOOPBACK


def _post_json(url: str, payload: dict, timeout: int) -> dict:
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - loopback only
            parsed = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise LocalExecutorError(f"Local executor unreachable: {exc}") from exc
    if not isinstance(parsed, dict):
        raise LocalExecutorError("Local executor answer is not a JSON object.")
    return parsed
