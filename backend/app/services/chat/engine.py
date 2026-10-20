"""Chatbot V1 sur l'exécuteur local (doc 72 ; décision utilisateur : IA locale seulement, aucun cloud).

Un tour = message de l'utilisateur → contexte en LISTE BLANCHE (journée, mission active, projets ouverts et leurs
missions à faire, routines, priorités ; jamais de santé, de religion ni de finances détaillées) + historique
récent → modèle local à température 0, sortie contrainte {reply_fr, proposal|null}. La proposition est vérifiée
par le code (action du catalogue, paramètres validés par les schémas d'écriture existants, projet ouvert) ;
sortie invalide → un nouvel essai avec les erreurs, puis réponse sans proposition. Elle n'est JAMAIS exécutée ici :
seule `validate_proposal`, appelée par l'utilisateur, écrit (doc 72 §4-5, doc 08), avec une clé d'idempotence
tirée de la proposition (une validation rejouée ne crée rien de plus).

Le slot `chat.converse` doit être en mode `live` dans `ai.local_slot_modes` ; sinon, ou si l'exécuteur est
injoignable, la réponse dit clairement que le moteur local est indisponible (doc 72 §10), sans repli cloud.
Pas d'escalade (§3) ni d'extraction d'apprentissages à la fermeture (§6) dans cette V1.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.chat import ChatMessage, ChatProposal, ChatSession
from app.schemas.chat import ChatMessageRead, ChatProposalRead, ChatSessionCreate, ChatSessionRead, ChatTurnRead
from app.schemas.operations import ProjectCreate, ProjectMissionCreate, RoutineCreate
from app.services.ai import local_executor
from app.services.imperium import operations
from app.services.imperium.decision_framework import get_canonical_priority_order
from app.services.imperium.missions import get_current_active_mission
from app.services.imperium.planning_days import get_current_planning_day
from app.services.params import get_parameter

SLOT = "chat.converse"
ACTIONS = ("create_project", "add_project_mission", "create_routine")
HISTORY_MESSAGES = 12
HISTORY_CHARS = 6000
DOMAIN_LABELS = {"religious": "Religion", "business": "Business", "finance": "Finances", "health": "Santé"}
DEGRADED_REPLY = ("Le moteur local est indisponible pour le moment : je ne peux pas te répondre. "
                  "Réessaie dans un instant ; rien n'a été modifié.")

SYSTEM = (
    "Tu es l'assistant d'Imperium, le système personnel qui organise la vie de l'utilisateur. Tu réponds en français, "
    "en le tutoyant, clairement et brièvement. Tu ne fais JAMAIS rien toi-même : quand l'utilisateur demande une action que tu sais "
    "faire, tu la proposes dans « proposal », avec un résumé d'une phrase, et c'est lui qui la validera. Une seule "
    "proposition par réponse ; aucune si rien n'est demandé. Actions possibles :\n"
    "- create_project : créer un projet (params : title, description facultative) ;\n"
    "- add_project_mission : ajouter une mission à un projet existant (params : project_id = le repère du projet "
    "dans le contexte, par exemple P1, "
    "title, estimated_minutes facultatif, notes facultatives) ;\n"
    "- create_routine : créer une routine (params : name, frequency daily|weekly|biweekly|monthly, "
    "estimated_minutes facultatif, priority low|medium|high, notes facultatives).\n"
    "Quand l'utilisateur donne une durée, reporte-la toujours dans estimated_minutes (en minutes). "
    "Pour tout le reste, réponds sans proposition et dis simplement que tu ne sais pas encore le faire. "
    "N'invente jamais de donnée : appuie-toi seulement sur le contexte fourni."
)

def _variant(action: str, required: list[str], params: dict) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["action", "summary_fr", "params"],
            "properties": {"action": {"const": action}, "summary_fr": {"type": "string", "maxLength": 300},
                           "params": {"type": "object", "additionalProperties": False, "required": required,
                                      "properties": params}}}


def output_schema(aliases: list[str]) -> dict:
    """Une variante par action, champs obligatoires compris ; `project_id` ne peut être qu'un repère réel (P1…).
    Une durée est obligatoire mais peut valoir null : le modèle doit la reporter ou dire qu'elle est inconnue."""
    minutes = {"type": ["integer", "null"]}
    text = {"type": "string"}
    notes = {"type": ["string", "null"]}
    variants = [
        _variant("create_project", ["title", "description"], {"title": text, "description": notes}),
        _variant("create_routine", ["name", "frequency", "estimated_minutes", "priority", "notes"],
                 {"name": text, "frequency": {"enum": ["daily", "weekly", "biweekly", "monthly"]}, "estimated_minutes": minutes,
                  "priority": {"enum": ["low", "medium", "high"]}, "notes": notes}),
    ]
    if aliases:
        variants.insert(1, _variant("add_project_mission", ["project_id", "title", "estimated_minutes", "notes"],
                                    {"project_id": {"enum": aliases}, "title": text, "estimated_minutes": minutes, "notes": notes}))
    return {"type": "object", "additionalProperties": False, "required": ["reply_fr", "proposal"],
            "properties": {"reply_fr": {"type": "string", "maxLength": 1500},
                           "proposal": {"anyOf": [{"type": "null"}, *variants]}}}


class ChatNotFoundError(ValueError):
    pass


class ChatStateError(ValueError):
    pass


def enabled(db: Session) -> bool:
    return bool(get_parameter(db, "chat.enabled", default=False))


def start_session(db: Session, *, current_user: User, payload: ChatSessionCreate) -> ChatSessionRead:
    session = ChatSession(id=uuid4(), user_id=current_user.id, context_kind=payload.context_kind,
                          context_ref=payload.context_ref, status="open", started_at=datetime.now(UTC))
    db.add(session)
    db.flush()
    read = _session_read(db, session)
    db.commit()
    return read


def get_session(db: Session, *, current_user: User, session_id: UUID) -> ChatSessionRead:
    return _session_read(db, _get(db, current_user, session_id))


def send_message(db: Session, *, current_user: User, session_id: UUID, text: str) -> ChatTurnRead:
    session = _get(db, current_user, session_id)
    if session.status != "open":
        raise ChatStateError("Session closed.")
    now = datetime.now(UTC)
    user_message = ChatMessage(id=uuid4(), session_id=session.id, user_id=current_user.id, role="user", content=text,
                               created_at=now)
    db.add(user_message)
    db.flush()
    context, aliases = _context(db, current_user)
    reply, proposal, model, latency, degraded = _converse(db, session, context, aliases)
    assistant = ChatMessage(id=uuid4(), session_id=session.id, user_id=current_user.id, role="assistant",
                            content=reply[:8000], model_used=model, latency_ms=latency, degraded=degraded,
                            created_at=datetime.now(UTC))
    db.add(assistant)
    db.flush()
    stored = None
    if proposal is not None:
        for previous in db.scalars(select(ChatProposal).where(ChatProposal.session_id == session.id,
                                                              ChatProposal.status == "proposed")):
            previous.status, previous.decided_at = "superseded", now
        db.flush()
        stored = ChatProposal(id=uuid4(), session_id=session.id, message_id=assistant.id, user_id=current_user.id,
                              action=proposal["action"], params=proposal["params"], summary_fr=proposal["summary_fr"],
                              status="proposed", created_at=now)
        db.add(stored)
        db.flush()
    turn = ChatTurnRead(user_message=ChatMessageRead.model_validate(user_message),
                        assistant_message=ChatMessageRead.model_validate(assistant),
                        proposal=ChatProposalRead.model_validate(stored) if stored else None)
    db.commit()
    return turn


def validate_proposal(db: Session, *, current_user: User, session_id: UUID, proposal_id: UUID) -> ChatProposalRead:
    """Seule voie d'écriture du chatbot : exécute l'action validée par l'utilisateur, idempotente."""
    proposal = _proposal(db, current_user, session_id, proposal_id)
    key = f"chat-proposal-{proposal.id}"
    try:
        result = _execute(db, current_user, proposal.action, proposal.params, key)
    except (ValidationError, ValueError, LookupError) as exc:
        db.rollback()
        proposal = _proposal(db, current_user, session_id, proposal_id)
        proposal.status, proposal.decided_at, proposal.result = "failed", datetime.now(UTC), {"error": str(exc)[:300]}
        read = ChatProposalRead.model_validate(proposal)
        db.commit()
        return read
    proposal = _proposal(db, current_user, session_id, proposal_id, any_status=True)
    proposal.status, proposal.decided_at, proposal.result = "validated", datetime.now(UTC), result
    read = ChatProposalRead.model_validate(proposal)
    db.commit()
    return read


def reject_proposal(db: Session, *, current_user: User, session_id: UUID, proposal_id: UUID) -> ChatProposalRead:
    proposal = _proposal(db, current_user, session_id, proposal_id)
    proposal.status, proposal.decided_at = "rejected", datetime.now(UTC)
    read = ChatProposalRead.model_validate(proposal)
    db.commit()
    return read


def close_session(db: Session, *, current_user: User, session_id: UUID) -> ChatSessionRead:
    session = _get(db, current_user, session_id)
    if session.status == "open":
        now = datetime.now(UTC)
        session.status, session.closed_at = "closed", now
        for proposal in db.scalars(select(ChatProposal).where(ChatProposal.session_id == session.id, ChatProposal.status == "proposed")):
            proposal.status, proposal.decided_at = "superseded", now
    read = _session_read(db, session)
    db.commit()
    return read


def delete_session(db: Session, *, current_user: User, session_id: UUID) -> None:
    """Suppression réelle du journal de la session (messages et propositions partent avec elle)."""
    db.delete(_get(db, current_user, session_id))
    db.commit()


# --- Moteur -------------------------------------------------------------------------------------

def _converse(db: Session, session: ChatSession, context: str, aliases: dict[str, str]):
    if local_executor.slot_mode(db, SLOT) != "live":
        return DEGRADED_REPLY, None, None, None, True
    history = list(db.scalars(select(ChatMessage).where(ChatMessage.session_id == session.id)
                              .order_by(ChatMessage.created_at.desc()).limit(HISTORY_MESSAGES)))[::-1]
    transcript = "\n".join(f"{'Utilisateur' if m.role == 'user' else 'Assistant'} : {m.content}" for m in history)[-HISTORY_CHARS:]
    prompt = f"## Contexte\n{context}\n\n## Conversation\n{transcript}\n\nRéponds au dernier message de l'utilisateur."
    latency = 0
    for attempt in range(2):
        try:
            result = local_executor.structured(slot_code=SLOT, app_name="imperium", system=SYSTEM, user=prompt,
                                               schema=output_schema(list(aliases)), max_tokens=900, related_entity_type="chat_session",
                                               related_entity_id=session.id)
        except local_executor.LocalExecutorError:
            return DEGRADED_REPLY, None, None, latency or None, True
        latency += result.latency_ms
        reply = str(result.output.get("reply_fr") or "").strip() or "…"
        proposal = result.output.get("proposal")
        if proposal and proposal.get("action") == "add_project_mission":
            # Repère court (P1…) → identifiant réel ; un repère inconnu est refusé par _check.
            params = dict(proposal.get("params") or {})
            params["project_id"] = aliases.get(str(params.get("project_id")), "")
            proposal = {**proposal, "params": params}
        errors = _check(proposal, set(aliases.values())) if proposal else []
        if not errors:
            return reply, proposal, "local_executor", latency, False
        prompt += f"\n\n## rappel\nProposition invalide : {', '.join(errors)}. Corrige-la ou n'en fais pas."
    return reply + "\n\n(Je n'ai pas réussi à formuler l'action correctement : reformule ta demande.)", None, "local_executor", latency, False


def _check(proposal: dict, projects: set[str]) -> list[str]:
    """Paramètres validés par les schémas d'écriture existants ; projet obligatoirement ouvert."""
    action, params = proposal.get("action"), proposal.get("params") or {}
    try:
        if action == "create_project":
            ProjectCreate(title=params.get("title", ""), description=params.get("description"), source="chatbot")
        elif action == "add_project_mission":
            if params.get("project_id") not in projects:
                return ["project_id inconnu"]
            ProjectMissionCreate(title=params.get("title", ""), notes=params.get("notes"),
                                 estimated_minutes=params.get("estimated_minutes"))
        elif action == "create_routine":
            RoutineCreate(name=params.get("name", ""), frequency=params.get("frequency", "daily"),
                          estimated_minutes=params.get("estimated_minutes"), priority=params.get("priority", "medium"),
                          notes=params.get("notes"))
        else:
            return [f"action inconnue {action}"]
    except ValidationError as exc:
        return [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()][:3]
    if not str(proposal.get("summary_fr") or "").strip():
        return ["summary_fr vide"]
    return []


def _execute(db: Session, user: User, action: str, params: dict, key: str) -> dict:
    if action == "create_project":
        project = operations.create_project(db, current_user=user, idempotency_key=key, payload=ProjectCreate(
            title=params["title"], description=params.get("description"), source="chatbot"))
        return {"project_id": str(project.id), "title": project.title}
    if action == "add_project_mission":
        mission = operations.add_project_mission(db, current_user=user, project_id=UUID(params["project_id"]), idempotency_key=key,
                                                 payload=ProjectMissionCreate(title=params["title"], notes=params.get("notes"),
                                                                              estimated_minutes=params.get("estimated_minutes")))
        return {"mission_id": str(mission.id), "title": mission.title}
    if action == "create_routine":
        routine = operations.create_routine(db, current_user=user, idempotency_key=key, payload=RoutineCreate(
            name=params["name"], frequency=params.get("frequency", "daily"), estimated_minutes=params.get("estimated_minutes"),
            priority=params.get("priority", "medium"), notes=params.get("notes")))
        return {"routine_id": str(routine.id), "name": routine.name}
    raise ValueError(f"Unknown action {action}.")


def _context(db: Session, user: User) -> tuple[str, dict[str, str]]:
    """Contexte en liste blanche : seulement ce qui sert aux actions du catalogue et à situer la journée."""
    lines = []
    day = get_current_planning_day(db, current_user=user)
    lines.append(f"Journée : {'en cours depuis ' + day.started_at.isoformat(timespec='minutes') if day and not day.finished_at else 'non démarrée'}")
    active = get_current_active_mission(db, current_user=user).mission
    lines.append(f"Mission active : {active.title if active else 'aucune'}")
    projects = operations.list_projects(db, current_user=user).projects
    aliases = {f"P{i}": str(p.id) for i, p in enumerate(projects, start=1)}
    for alias, p in zip(aliases, projects):
        todo = [m.title for m in p.missions if m.status not in ("completed", "cancelled", "failed")][:8]
        lines.append(f"{alias} : projet{' actif' if p.active else ' en attente'} « {p.title} » ; missions à faire : "
                     f"{', '.join(todo) or 'aucune'}")
    routines = operations.list_routines(db, current_user=user).routines
    lines.append("Routines : " + (", ".join(f"{r.name} ({r.frequency})" for r in routines if r.active) or "aucune"))
    order = [DOMAIN_LABELS.get(p.domain, p.domain) for p in get_canonical_priority_order(db, current_user=user)]
    lines.append("Priorités : " + " > ".join(order))
    return "\n".join(lines), aliases


def _get(db: Session, user: User, session_id: UUID) -> ChatSession:
    session = db.get(ChatSession, session_id)
    if session is None or session.user_id != user.id:
        raise ChatNotFoundError("Session not found.")
    return session


def _proposal(db: Session, user: User, session_id: UUID, proposal_id: UUID, *, any_status: bool = False) -> ChatProposal:
    proposal = db.get(ChatProposal, proposal_id, with_for_update=True)
    if proposal is None or proposal.user_id != user.id or proposal.session_id != session_id:
        raise ChatNotFoundError("Proposal not found.")
    if not any_status and proposal.status != "proposed":
        raise ChatStateError(f"Proposal already {proposal.status}.")
    return proposal


def _session_read(db: Session, session: ChatSession) -> ChatSessionRead:
    messages = db.scalars(select(ChatMessage).where(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at))
    open_proposal = db.scalar(select(ChatProposal).where(ChatProposal.session_id == session.id, ChatProposal.status == "proposed"))
    return ChatSessionRead(id=session.id, status=session.status, context_kind=session.context_kind,
                           context_ref=session.context_ref, started_at=session.started_at, closed_at=session.closed_at,
                           messages=[ChatMessageRead.model_validate(m) for m in messages],
                           open_proposal=ChatProposalRead.model_validate(open_proposal) if open_proposal else None)
