"""Job runner imperium.rolling_replan (doc 43 §2, §3.2).

Traite les tâches IA de replanification en file :
- première proposition : DÉTERMINISTE (doc 43 §2 — sélection déterministe d'abord),
  selon la catégorie de raison (doc 43 §3.4) ;
- correction demandée dans le chatbot : modèle local (local_executor) ; sa sortie est
  validée par le backend, sinon la proposition précédente est conservée.
Le job dépose la proposition ; seul l'utilisateur l'accepte (doc 59 §12.6).
"""

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import AITask
from app.models.imperium import PlanningReplanEvent
from app.schemas.imperium import ReplanProposalAttachRequest
from app.services.imperium.replan import REPLAN_TASK_TYPE, attach_replan_proposal

logger = logging.getLogger(__name__)

SHIFT_MINUTES = 30
PAUSE_MINUTES = 20
BATCH_SIZE = 20
MAX_BATCHES = 10  # borne de sécurité : au plus 200 tâches par réveil
_DEFAULT = object()

ModelCall = Callable[[str], dict]


def rolling_replan_job(ctx, window) -> None:  # noqa: ARG001 - signature du runner
    process_queued_replans(ctx)


def process_queued_replans(ctx, *, call_model: ModelCall | None | object = _DEFAULT, now: datetime | None = None) -> None:
    db: Session = ctx.db
    now = now or datetime.now(UTC)
    model = _default_model() if call_model is _DEFAULT else call_model
    proposed = superseded = failed = seen = 0
    # Vide la file par lots : chaque tâche traitée quitte l'état queued.
    for _ in range(MAX_BATCHES):
        task_ids = list(
            db.scalars(
                select(AITask.id)
                .where(AITask.task_type == REPLAN_TASK_TYPE, AITask.status == "queued")
                .order_by(AITask.created_at.asc())
                .limit(BATCH_SIZE)
            )
        )
        if not task_ids:
            break
        for task_id in task_ids:
            outcome = _process_task(db, task_id=task_id, model=model, now=now)
            seen += 1
            proposed += outcome == "proposed"
            superseded += outcome == "superseded"
            failed += outcome == "failed"
    ctx.items_in = seen
    ctx.items_out = proposed
    ctx.detail = {"proposed": proposed, "superseded": superseded, "failed": failed}


def build_deterministic_proposal(blocks: list[dict], *, reason_category: str, now: datetime) -> tuple[list[dict], str]:
    """Proposition sans IA, explicable, selon la catégorie de raison (doc 43 §3.4)."""
    out = [{**block, "change": "unchanged"} for block in blocks]
    scheduled = [block for block in out if _start(block) is not None]
    current = next((block for block in scheduled if _is_current(block, now)), None)
    upcoming = [block for block in scheduled if block is not current and _start(block) > now]

    def shift(minutes: int) -> None:
        for block in upcoming:
            _move(block, minutes)

    if reason_category == "fatigue":
        pause_start = now.replace(second=0, microsecond=0)
        pause = {
            "block_type": "mission",
            "title": "Pause récupération",
            "planned_start": pause_start.isoformat(),
            "planned_end": (pause_start + timedelta(minutes=PAUSE_MINUTES)).isoformat(),
            "change": "new",
        }
        shift(PAUSE_MINUTES)
        index = out.index(upcoming[0]) if upcoming else len(out)
        out.insert(index, pause)
        return out, (
            f"J'ai ajouté une pause récupération de {PAUSE_MINUTES} min maintenant et décalé la suite d'autant. "
            "Dis-moi si tu veux alléger davantage."
        )
    if reason_category == "wrong_estimation" and current is not None:
        end = _end(current)
        if end is not None:
            current["planned_end"] = (end + timedelta(minutes=SHIFT_MINUTES)).isoformat()
            current["change"] = "moved"
        shift(SHIFT_MINUTES)
        return out, (
            f"J'ai prolongé « {current.get('title')} » de {SHIFT_MINUTES} min et décalé la suite d'autant. "
            "Dis-moi si l'écart est plus grand."
        )
    if reason_category == "priority_shift":
        return out, "Ton plan ne bouge pas encore : quelle mission doit passer avant les autres ?"
    if not upcoming:
        return out, "Il ne reste rien à décaler aujourd'hui. Dis-moi ce que tu veux changer."
    shift(SHIFT_MINUTES)
    return out, (
        f"J'ai décalé la suite de ta journée de {SHIFT_MINUTES} min pour absorber l'imprévu. "
        "Tu peux me demander des corrections."
    )


def build_revision_proposal(
    current: list[dict], *, correction: str, call_model: ModelCall | None
) -> tuple[list[dict], str, bool]:
    """Correction en langage naturel : modèle local, sortie validée ; sinon proposition conservée."""
    if call_model is not None:
        prompt = (
            "Tu es le modèle local d'Imperium. Corrige la proposition de planning selon la demande. "
            'Réponds en JSON strict : {"blocks": [...], "rationale": "phrase en français, tutoiement"}. '
            "Chaque bloc garde ses champs et porte change = unchanged | moved | new | removed. "
            f"Demande : {correction}\n"
            f"Proposition actuelle : {json.dumps(current, ensure_ascii=False, default=str)}"
        )
        try:
            raw = call_model(prompt)
            validated = ReplanProposalAttachRequest(blocks=raw.get("blocks"), rationale=raw.get("rationale"))
            return validated.blocks, validated.rationale or "Proposition corrigée.", True
        except Exception:  # noqa: BLE001 - toute sortie invalide retombe sur la proposition conservée
            logger.warning("Replan revision model output rejected; keeping previous proposal.")
    return current, (
        f"Je n'ai pas pu appliquer ta correction automatiquement (« {correction} »). "
        "La proposition précédente est conservée : précise ce que tu veux déplacer."
    ), False


# ---------- internes ----------

def _process_task(db: Session, *, task_id: UUID, model: ModelCall | None, now: datetime) -> str:
    task = db.get(AITask, task_id)
    row = db.get(PlanningReplanEvent, UUID(task.input_payload["replan_event_id"]))
    if row is None or row.ai_task_id != task.id or row.status not in ("requested", "revising"):
        task.status = "cancelled"
        task.completed_at = now
        db.commit()
        return "superseded"
    task.status = "running"
    task.started_at = now
    db.commit()
    try:
        payload = task.input_payload
        if "correction" in payload:
            blocks, rationale, used_model = build_revision_proposal(
                payload.get("current_proposal") or row.proposal or [], correction=payload["correction"], call_model=model
            )
            engine = "local_executor" if used_model else "fallback_keep_previous"
        else:
            blocks, rationale = build_deterministic_proposal(
                payload.get("current_plan_blocks") or [], reason_category=row.reason_category or "new_event", now=now
            )
            engine = "deterministic"
        attach_replan_proposal(
            db,
            request_id=row.id,
            payload=ReplanProposalAttachRequest(blocks=blocks, rationale=rationale, ai_task_id=task.id),
            idempotency_key=f"runner:{task.id}",
        )
        task = db.get(AITask, task_id)
        task.status = "result_received"
        task.completed_at = now
        task.router_decision = {"engine": engine}
        db.commit()
        return "proposed"
    except Exception as exc:  # noqa: BLE001 - l'échec est journalisé sur la tâche et la demande
        db.rollback()
        logger.exception("Replan task failed.", extra={"ai_task_id": str(task_id)})
        task = db.get(AITask, task_id)
        row = db.get(PlanningReplanEvent, row.id)
        task.status = "failed"
        task.failed_at = now
        task.error_code = "replan_runner_error"
        task.error_message = str(exc)[:500]
        row.status = "failed"
        row.resolved_at = now
        db.commit()
        return "failed"


def _default_model() -> ModelCall | None:
    """Modèle local réel seulement s'il est activé ; en dry-run, pas d'appel (repli explicite)."""
    from app.services.ai.providers.qwen import QwenClient

    client = QwenClient()
    if client._should_dry_run():  # noqa: SLF001 - même règle que le reste de l'adaptateur Qwen
        return None
    return lambda prompt: client.call(prompt=prompt, mode="replan_revision")


def _parse(value) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _start(block: dict) -> datetime | None:
    return _parse(block.get("planned_start"))


def _end(block: dict) -> datetime | None:
    return _parse(block.get("planned_end"))


def _is_current(block: dict, now: datetime) -> bool:
    if block.get("status") == "active" or block.get("block_type") == "current_mission":
        return True
    start, end = _start(block), _end(block)
    return start is not None and end is not None and start <= now < end


def _move(block: dict, minutes: int) -> None:
    for key in ("planned_start", "planned_end"):
        value = _parse(block.get(key))
        if value is not None:
            block[key] = (value + timedelta(minutes=minutes)).isoformat()
    block["change"] = "moved"
