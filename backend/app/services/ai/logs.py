"""Navigateur des logs de l'IA (doc 72 §8) — Réglages → Intelligence artificielle → Logs.

Confiné par construction : les logs sont reconstruits depuis la base (tâches IA et
leurs résultats, éléments de Nourrir l'IA, décisions d'escalade de Nexus quand le score demandait un modèle
plus fort — la décision seulement, jamais le message) ; aucun accès au système de fichiers,
aucun chemin accepté. Lecture seule ; la correction passe par le chatbot.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import AIResult, AITask, KnowledgeInboxItem
from app.models.auth import User
from app.models.chat import ChatMessage

LIST_LIMIT = 200
MASK = "••••"
SECRET_MARKERS = ("key", "token", "secret", "password", "authorization", "cookie")
TASK_LABELS = {
    "imperium.rolling_replan": "Replanification",
    "weekly_report.summary": "Weekly Review",
    "imperium.weekly_review": "Weekly Review",
    "chatbot.routing": "Chatbot",
}
FOOTER = "Pour corriger une extraction, parle au chatbot."


class AILogNotFoundError(ValueError):
    pass


class AILogEntry(BaseModel):
    id: str
    name: str
    kind: str
    occurred_at: datetime


class AILogListResponse(BaseModel):
    logs: list[AILogEntry]


class AILogRead(AILogEntry):
    content: str


def list_logs(db: Session, *, current_user: User) -> AILogListResponse:
    entries = [
        AILogEntry(id=f"task:{task.id}", name=_task_name(task), kind="task", occurred_at=task.created_at)
        for task in db.scalars(
            select(AITask).where(AITask.user_id == current_user.id).order_by(AITask.created_at.desc()).limit(LIST_LIMIT)
        )
    ]
    entries += [
        AILogEntry(id=f"inbox:{item.id}", name=_inbox_name(item), kind="inbox", occurred_at=item.created_at)
        for item in db.scalars(
            select(KnowledgeInboxItem)
            .where(KnowledgeInboxItem.user_id == current_user.id, KnowledgeInboxItem.status != "deleted")
            .order_by(KnowledgeInboxItem.created_at.desc())
            .limit(LIST_LIMIT)
        )
    ]
    entries += [
        AILogEntry(id=f"routing:{message.id}", name=_routing_name(message), kind="routing", occurred_at=message.created_at)
        for message in db.scalars(
            select(ChatMessage)
            .where(ChatMessage.user_id == current_user.id, ChatMessage.routing.is_not(None),
                   ChatMessage.routing["role"].astext != "local_executor")
            .order_by(ChatMessage.created_at.desc())
            .limit(LIST_LIMIT)
        )
    ]
    entries.sort(key=lambda entry: entry.occurred_at, reverse=True)
    return AILogListResponse(logs=entries[:LIST_LIMIT])


def read_log(db: Session, *, current_user: User, log_id: str) -> AILogRead:
    kind, _, raw_id = (log_id or "").partition(":")
    try:
        object_id = UUID(raw_id)
    except ValueError as exc:
        raise AILogNotFoundError("Log not found.") from exc
    if kind == "task":
        task = db.get(AITask, object_id)
        if task is None or task.user_id != current_user.id:
            raise AILogNotFoundError("Log not found.")
        results = list(db.scalars(select(AIResult).where(AIResult.task_id == task.id).order_by(AIResult.created_at.asc())))
        return AILogRead(id=log_id, name=_task_name(task), kind="task", occurred_at=task.created_at,
                         content=_task_content(task, results))
    if kind == "inbox":
        item = db.get(KnowledgeInboxItem, object_id)
        if item is None or item.user_id != current_user.id or item.status == "deleted":
            raise AILogNotFoundError("Log not found.")
        return AILogRead(id=log_id, name=_inbox_name(item), kind="inbox", occurred_at=item.created_at,
                         content=_inbox_content(item))
    if kind == "routing":
        message = db.get(ChatMessage, object_id)
        if message is None or message.user_id != current_user.id or not message.routing:
            raise AILogNotFoundError("Log not found.")
        return AILogRead(id=log_id, name=_routing_name(message), kind="routing", occurred_at=message.created_at,
                         content=_routing_content(message))
    raise AILogNotFoundError("Log not found.")


# ---------- rendu ----------

def _routing_name(message: ChatMessage) -> str:
    routing = message.routing or {}
    verb = "Escalade" if routing.get("escalated") else "Escalade non faite"
    return f"{message.created_at:%Y-%m-%d} · {verb} · {routing.get('role')} ({routing.get('score')}/200)"


def _routing_content(message: ChatMessage) -> str:
    routing = message.routing or {}
    lines = [f"[{_hm(message.created_at)}] réponse de Nexus : score {routing.get('score')}/200 → {routing.get('role')}",
             f"confiance {routing.get('confidence')} · domaine {routing.get('domain')}",
             "raisons : " + ", ".join(routing.get("reasons") or [])]
    lines += _block("critères", routing.get("breakdown"))
    if routing.get("escalated"):
        lines.append(f"répondu par {routing.get('model') or message.model_used} ({message.latency_ms} ms au total)")
    else:
        lines.append(f"non escaladé : {routing.get('skipped') or 'local'}" + (f" ({routing['error']})" if routing.get("error") else ""))
    return "\n".join(lines + ["", "Le message lui-même n'est pas journalisé ici."])

def _task_name(task: AITask) -> str:
    return f"{task.created_at:%Y-%m-%d} · {TASK_LABELS.get(task.task_type, task.task_type)}"


def _inbox_name(item: KnowledgeInboxItem) -> str:
    return f"{item.created_at:%Y-%m-%d} · Nourrir l'IA · {item.title}"


def _task_content(task: AITask, results: list[AIResult]) -> str:
    lines = [f"[{_hm(task.created_at)}] task {task.task_type} status={task.status}"]
    if task.router_decision:
        lines.append("[routage] " + " ".join(f"{key}={value}" for key, value in sorted(_mask(task.router_decision).items())))
    lines += _block("entrée", task.input_payload)
    if task.started_at:
        lines.append(f"[{_hm(task.started_at)}] démarrée")
    for result in results:
        lines.append(f"[{_hm(result.created_at)}] résultat {result.result_type} ({result.status}, {result.model_used or 'modèle ?'})")
        lines += _block("résultat", result.result_payload)
    if task.completed_at:
        lines.append(f"[{_hm(task.completed_at)}] terminée")
    if task.failed_at or task.error_message:
        lines.append(f"[{_hm(task.failed_at)}] échec {task.error_code or ''} : {task.error_message or ''}".rstrip())
    return "\n".join(lines + ["", FOOTER])


def _inbox_content(item: KnowledgeInboxItem) -> str:
    lines = [f"[{_hm(item.created_at)}] import « {item.title} » (depuis {item.entry_app}) status={item.status}"]
    if item.context_text:
        lines.append(f"contexte : {item.context_text}")
    lines += _block("brouillon", item.extraction_draft)
    if item.error_message:
        lines.append(f"erreur : {item.error_message}")
    if item.validated_at:
        lines.append(f"[{_hm(item.validated_at)}] validé par l'utilisateur → {item.destination}")
    lines += _block("retenu", item.extraction_final)
    if item.vectorized_at:
        lines.append(f"[{_hm(item.vectorized_at)}] vectorisé dans la mémoire")
    return "\n".join(lines + ["", FOOTER])


def _block(title: str, payload: dict | None) -> list[str]:
    if not payload:
        return []
    return [f"{title} :"] + [f"  {line}" for line in _flatten(_mask(payload))]


def _flatten(value, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        out = []
        for key, inner in value.items():
            if isinstance(inner, (dict, list)) and inner:
                out.append(f"{prefix}{key}:")
                out += _flatten(inner, prefix + "  ")
            else:
                out.append(f"{prefix}{key}: {inner}")
        return out
    if isinstance(value, list):
        return [line for inner in value for line in (_flatten(inner, prefix + "- ") if isinstance(inner, (dict, list)) else [f"{prefix}- {inner}"])]
    return [f"{prefix}{value}"]


def _mask(value):
    if isinstance(value, dict):
        return {
            key: MASK if any(marker in str(key).lower() for marker in SECRET_MARKERS) else _mask(inner)
            for key, inner in value.items()
        }
    if isinstance(value, list):
        return [_mask(inner) for inner in value]
    return value


def _hm(value: datetime | None) -> str:
    return f"{value:%Y-%m-%d %H:%M:%S}" if value else "—"
