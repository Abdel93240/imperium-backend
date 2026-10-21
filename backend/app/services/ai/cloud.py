"""Rôles cloud de l'écosystème (doc 30 §3, doc 73), un slot à la fois.

Un traitement nomme un SLOT ; le slot donne le rôle (`SLOT_ROLES`), le rôle donne le fournisseur et le
modèle (`ai_role_models`, jamais en dur). Le transport est choisi par le paramètre `ai.cloud_transport` :

- `off` (semé) : aucun appel ;
- `subscription` : tests réels avant toute clé API (décision utilisateur 2026-10-21) — la CLI du
  fournisseur, connectée à l'abonnement de l'utilisateur (`claude -p` pour anthropic, `codex exec` pour
  openai), lancée SANS AUCUN OUTIL (ni fichiers, ni commandes, ni web, ni MCP), dans un dossier vide,
  avec un environnement réduit et une durée maximale ; sortie contrainte par le JSON Schema du slot ;
- `api` (clés du doc 73) : pas encore codé.

Le catalogue d'un abonnement diffère de celui de l'API (par exemple Codex avec un compte ChatGPT refuse les
modèles API) : `ai.cloud_subscription_models` ({modèle du rôle: modèle de l'abonnement}, semé vide) traduit le
modèle du rôle pour le transport subscription seulement ; le rôle garde son identifiant API.

Interrupteur par slot : `ai.cloud_slot_modes` ({slot_code: off|live}, semé vide). Un slot n'est servi que
s'il est `cloud_forced` ou `routed` dans `ai_slot_transition`, hors domaine vault, et si son rôle n'est pas
local. Chaque appel, réussi ou non, va au journal central des appels IA (aucun contenu n'y est écrit).
"""

import json
import os
import re
import shutil
import subprocess  # nosec B404 - CLI fournisseur lancée sans shell, arguments en liste
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.toolbox import AISlotTransition
from app.services.ai import call_log
from app.services.ai.advanced import LOCAL_ONLY_ROLES
from app.services.ai.roles import RoleResolutionError, resolve_role
from app.services.params import get_parameter

TRANSPORTS = ("off", "subscription", "api")
MODES = ("off", "live")
CLOUD_TIERS = frozenset({"cloud_forced", "routed"})
# Rôle de chaque slot cloud branché (spec WR §9-10 ; exit_audit = high_reasoning, gravé).
SLOT_ROLES = {"wr.hypothesis_pass": "high_reasoning", "wr.exit_audit": "high_reasoning",
              "wr.report_revision": "first_cloud_tier"}
MODEL_TIERS = {"first_cloud_tier": "cloud_cheap", "high_reasoning": "cloud_premium",
               "high_reasoning_safeguard": "cloud_premium", "sustained_long_context": "cloud_premium"}
CLAUDE_EFFORT = {"minimal": "low", "low": "low", "medium": "medium", "high": "high", "xhigh": "xhigh"}
# Fonctions de la CLI Codex coupées : aucun outil ne reste (shell, navigateur, applis, images, agents...).
CODEX_DISABLED = ("shell_tool", "unified_exec", "apps", "browser_use", "browser_use_external", "computer_use",
                  "in_app_browser", "image_generation", "multi_agent", "plugins", "remote_plugin", "view_image",
                  "sleep_tool", "tool_suggest", "skill_search", "code_mode_host", "shell_snapshot",
                  "skill_mcp_dependency_install")
ENV_KEPT = ("HOME", "PATH", "LANG", "USER", "CODEX_HOME")
# Quota de l'abonnement atteint (messages des CLI) ; l'heure de retour quand la CLI la donne.
QUOTA = re.compile(r"usage limit|rate limit|hit your limit|limit reached|quota|too many requests|\b429\b", re.I)
QUOTA_EPOCH = re.compile(r"limit reached\|(\d{10})")
QUOTA_WHEN = re.compile(r"(?:resets?|try again)(?: at| in)? ([^.\n|]{1,40})", re.I)

# Remplacé par les tests : (args, stdin, timeout, cwd) -> stdout.
_run: Callable[[list[str], str, int, str], str] | None = None


class CloudError(RuntimeError):
    pass


class CloudQuotaError(CloudError):
    """Quota de l'abonnement atteint ; `retry_hint` = heure de retour annoncée par la CLI (ou None)."""

    def __init__(self, message: str, retry_hint: str | None) -> None:
        super().__init__(message)
        self.retry_hint = retry_hint


@dataclass(frozen=True)
class CloudResult:
    output: dict
    model: str
    provider: str
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None  # estimation au tarif API annoncée par la CLI (anthropic seulement)
    latency_ms: int


def transport(db: Session) -> str:
    value = get_parameter(db, "ai.cloud_transport", default="off")
    return value if value in TRANSPORTS else "off"


def slot_mode(db: Session, slot_code: str) -> str:
    """Mode effectif du slot : `off` dès qu'une condition de sûreté manque."""
    mode = (get_parameter(db, "ai.cloud_slot_modes", default={}) or {}).get(slot_code, "off")
    if mode != "live" or transport(db) == "off" or SLOT_ROLES.get(slot_code) in (None, *LOCAL_ONLY_ROLES):
        return "off"
    row = db.execute(select(AISlotTransition.tier, AISlotTransition.domain)
                     .where(AISlotTransition.slot_code == slot_code)).first()
    if row is None or row.tier not in CLOUD_TIERS or row.domain == "vault":
        return "off"
    return "live"


def structured(db: Session, *, slot_code: str, app_name: str, system: str, user: str, schema: dict,
               related_entity_type: str | None = None, related_entity_id: Any = None) -> CloudResult:
    """Un appel contraint au schéma ; lève CloudError (slot éteint, transport, CLI, sortie invalide)."""
    if slot_mode(db, slot_code) != "live":
        raise CloudError(f"Cloud slot '{slot_code}' is off.")
    if transport(db) != "subscription":
        raise CloudError("Only the subscription transport is coded.")
    role_code = SLOT_ROLES[slot_code]
    try:
        role = resolve_role(db, role_code)
    except RoleResolutionError as exc:
        raise CloudError(str(exc)) from exc
    call = {"anthropic": _claude, "openai": _codex}.get(role.provider)
    aliases = get_parameter(db, "ai.cloud_subscription_models", default={}) or {}
    model_id = str(aliases.get(role.model_id) or role.model_id)
    log = {"app_name": app_name, "task_type": slot_code, "model_tier": MODEL_TIERS.get(role_code, "cloud_standard"),
           "model_used": model_id, "trigger_source": "subscription_cli",
           "related_entity_type": related_entity_type, "related_entity_id": related_entity_id}
    with call_log.timed() as elapsed:
        try:
            if call is None:
                raise CloudError(f"No subscription CLI for provider '{role.provider}'.")
            output, model, input_tokens, output_tokens, cost = call(model_id, role.effort, system, user, schema)
            if not isinstance(output, dict):
                raise CloudError("The model output is not a JSON object.")
        except (CloudError, KeyError, IndexError, TypeError, ValueError, OSError) as exc:
            call_log.record(**log, duration_ms=elapsed(), success=False, error_code=type(exc).__name__[:32])
            if isinstance(exc, CloudError):
                raise
            raise CloudError(str(exc)) from exc
    result = CloudResult(output=output, model=model, provider=role.provider, input_tokens=input_tokens,
                         output_tokens=output_tokens, cost_usd=cost, latency_ms=elapsed())
    rate = get_parameter(db, "ai.usd_eur_rate", default=None)
    cost_eur = Decimal(str(cost)) * Decimal(str(rate)) if cost is not None and rate else None
    call_log.record(**{**log, "model_used": model}, input_tokens=input_tokens, output_tokens=output_tokens,
                    duration_ms=result.latency_ms, cost_eur=cost_eur.quantize(Decimal("0.000001")) if cost_eur else None)
    return result


def _claude(model: str, effort: str | None, system: str, user: str, schema: dict):
    args = [_binary(get_settings().claude_cli_path), "-p", "--model", model, "--output-format", "json",
            "--json-schema", json.dumps(schema), "--system-prompt", system, "--tools", "",
            "--no-session-persistence", "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands"]
    if effort in CLAUDE_EFFORT:
        args += ["--effort", CLAUDE_EFFORT[effort]]
    with tempfile.TemporaryDirectory(prefix="imperium-cloud-") as work:
        body = json.loads(_execute(args, user, work))
    if body.get("is_error") or body.get("subtype") != "success":
        raise _failure(f"Claude CLI error: {body.get('subtype')} {body.get('api_error_status')}",
                       f"{body.get('result')} {body.get('api_error_status')}")
    usage = body.get("usage") or {}
    models = list((body.get("modelUsage") or {}).keys())
    tokens_in = sum(usage.get(key) or 0 for key in ("input_tokens", "cache_creation_input_tokens",
                                                     "cache_read_input_tokens"))
    return (body["structured_output"], models[0] if models else model, tokens_in, usage.get("output_tokens"),
            body.get("total_cost_usd"))


def _codex(model: str, effort: str | None, system: str, user: str, schema: dict):
    with tempfile.TemporaryDirectory(prefix="imperium-cloud-") as work:
        root = Path(work)
        (root / "empty").mkdir()
        (root / "schema.json").write_text(json.dumps(schema), encoding="utf-8")
        args = [_binary(get_settings().codex_cli_path), "exec", "-m", model, "--ephemeral", "--skip-git-repo-check",
                "--ignore-user-config", "--ignore-rules", "--sandbox", "read-only", "-c", "web_search=disabled",
                "-C", str(root / "empty"), "--output-schema", str(root / "schema.json"),
                "-o", str(root / "last.txt"), "--json"]
        for feature in CODEX_DISABLED:
            args += ["--disable", feature]
        if effort:
            args += ["-c", f"model_reasoning_effort={effort}"]
        events = _execute([*args, "-"], f"{system}\n\n{user}", work)
        output = json.loads((root / "last.txt").read_text(encoding="utf-8"))
    usage = {}
    for line in events.splitlines():
        event = json.loads(line) if line.startswith("{") else {}
        if event.get("type") == "turn.completed":
            usage = event.get("usage") or {}
    return output, model, usage.get("input_tokens"), usage.get("output_tokens"), None


def _execute(args: list[str], stdin: str, cwd: str) -> str:
    timeout = get_settings().cloud_cli_timeout_seconds
    if _run is not None:
        return _run(args, stdin, timeout, cwd)
    env = {key: os.environ[key] for key in ENV_KEPT if key in os.environ}
    try:
        done = subprocess.run(args, input=stdin, capture_output=True, text=True, timeout=timeout, cwd=cwd,  # nosec B603
                              env=env, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CloudError(f"Cloud CLI failed: {type(exc).__name__}") from exc
    if done.returncode != 0:
        if args[1:2] == ["-p"] and done.stdout.lstrip().startswith("{"):
            return done.stdout  # Claude : l'erreur est dans la réponse JSON, lue par l'appelant
        raise _failure(f"Cloud CLI exited with {done.returncode}.", f"{done.stdout[-2000:]} {done.stderr[-2000:]}")
    return done.stdout


def _failure(message: str, cli_text: str) -> CloudError:
    """Erreur de la CLI ; quota atteint reconnu à son message, avec l'heure de retour si elle est donnée."""
    if not QUOTA.search(cli_text):
        return CloudError(message)
    hint = None
    if epoch := QUOTA_EPOCH.search(cli_text):
        hint = datetime.fromtimestamp(int(epoch.group(1)), UTC).astimezone(ZoneInfo("Europe/Paris")).strftime("%H:%M")
    elif when := QUOTA_WHEN.search(cli_text):
        hint = when.group(1).strip()
    return CloudQuotaError(f"Subscription quota reached ({message})", hint)


def _binary(name: str) -> str:
    path = os.environ.get("PATH", "") + os.pathsep + str(Path.home() / ".local" / "bin")
    found = shutil.which(name, path=path)
    if found is None:
        raise CloudError(f"Cloud CLI '{name}' not found.")
    return found
