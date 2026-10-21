"""Chatbot V1 sur l'exécuteur local (doc 72 ; décision utilisateur : IA locale seulement, aucun cloud).

Un tour = message de l'utilisateur → contexte en LISTE BLANCHE (journée, mission active, projets ouverts et leurs
missions à faire, routines, priorités ; jamais de santé, de religion ni de finances détaillées) + historique
récent → modèle local à température 0, sortie contrainte {reply_fr, proposal|null}. La proposition est vérifiée
par le code (action du catalogue, paramètres validés par les schémas d'écriture existants, projet ouvert) ;
sortie invalide → un nouvel essai avec les erreurs, puis réponse sans proposition. Chaque action a sa fiche
« ce qu'il faut savoir » (`chat.action_requirements`, donnée éditable) : une proposition incomplète est refusée et,
si le modèle insiste, c'est le code qui pose la question. Un projet naît complet (objectif et premières
missions), validé en une seule fois. Un agent par situation (`chat.agents`, donnée éditable : rôle, actions
permises, activation) : le code le choisit à l'ouverture selon le contexte de la session (Général, Projet,
Mission), et chaque agent reçoit sa propre liste blanche de contexte. Quand la discussion change de sujet, le
modèle peut proposer de changer d'agent (`switch_agent`) : c'est une proposition comme les autres, que
l'utilisateur valide. La proposition n'est JAMAIS exécutée ici :
seule `validate_proposal`, appelée par l'utilisateur, écrit (doc 72 §4-5, doc 08), avec une clé d'idempotence
tirée de la proposition (une validation rejouée ne crée rien de plus).

Le slot `chat.converse` doit être en mode `live` dans `ai.local_slot_modes` ; sinon, ou si l'exécuteur est
injoignable, la réponse dit clairement que le moteur local est indisponible (doc 72 §10), sans repli cloud.
Escalade invisible (§3, `app.services.ai.escalation`) : chaque réponse locale porte l'auto-évaluation du modèle ;
le code calcule le score /200 et, pour une réponse sans proposition, peut faire répondre un rôle cloud à la
question anonyme du modèle (slot `nexus.escalation`, éteint par défaut : la décision est alors seulement
journalisée dans `chat_messages.routing`). Les propositions d'action restent locales ; une proposition
n'empêche pas l'escalade de la réponse quand le modèle a écrit une question pour l'expert.
Pas d'extraction d'apprentissages à la fermeture (§6) dans cette V1.
"""

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.chat import ChatMessage, ChatProposal, ChatSession
from app.models.imperium import ImperiumMission, ImperiumProject
from app.schemas.chat import ChatMessageRead, ChatProposalRead, ChatSessionCreate, ChatSessionRead, ChatTurnRead
from app.schemas.imperium import CalendarEventCreate
from app.schemas.operations import IntrinsicMissionCreate, ProjectCreate, ProjectMissionCreate, RoutineCreate
from app.services.ai import cloud, escalation, local_executor
from app.services.imperium import calendar, calendar_recurrence, operations
from app.services.imperium.decision_framework import get_canonical_priority_order
from app.services.imperium.missions import get_current_active_mission
from app.services.imperium.planning_days import get_current_planning_day
from app.services.params import get_parameter

SLOT = "chat.converse"
ACTIONS = ("create_project", "add_project_mission", "create_mission", "create_routine", "add_event")
PARIS = ZoneInfo("Europe/Paris")
WEEKDAYS_FR = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
HISTORY_MESSAGES = 12
HISTORY_CHARS = 6000
DOMAIN_LABELS = {"religious": "Religion", "business": "Business", "finance": "Finances", "health": "Santé"}
DEGRADED_REPLY = ("Le moteur local est indisponible pour le moment : je ne peux pas te répondre. "
                  "Réessaie dans un instant ; rien n'a été modifié.")

DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
TIME_PATTERN = r"^\d{2}:\d{2}$"
DEFAULT_REQUIREMENTS = {
    "create_project": {"required": [["title", "le nom du projet"], ["description", "le résultat que tu vises avec ce projet"], ["missions", "ses premières étapes (au moins une mission)"]],
                       "min_description_chars": 15, "min_missions": 1, "max_missions": 10},
    "add_project_mission": {"required": [["project_id", "le projet concerné"], ["title", "ce que la mission consiste à faire"]]},
    "create_mission": {"required": [["title", "ce qu'il faut faire"]]},
    "add_event": {"required": [["title", "ce que c'est"], ["date", "le jour"]]},
    "create_routine": {"required": [["name", "le nom de la routine"], ["frequency", "sa fréquence (chaque jour, semaine, 2 semaines ou mois)"]]},
}


DEFAULT_AGENTS = {
    "general": {"enabled": True, "label": "Général",
                "role": "Tu es l'assistant général d'Imperium : tu aides l'utilisateur à créer des projets complets, à "
                        "ajouter des missions à ses projets, à noter des missions hors projet (démarches, paperasse…), "
                        "à créer des routines et à remplir son calendrier (rendez-vous, échéances, vacances).",
                "actions": list(ACTIONS)},
}
CONTEXT_AGENT = {"project": "project", "mission": "mission"}  # contexte de session → agent ; le reste → Général
SWITCH_HELP = {
    "general": "l'agent Général, pour tout le reste (créer un projet ou une routine, parler de plusieurs projets)",
    "project": "l'agent Projet, pour travailler sur UN projet précis (project_id = son repère)",
    "mission": "l'agent Mission, pour la mission en cours (s'y mettre, se débloquer)",
}
ACTION_HELP = {
    "create_project": "créer un projet complet, avec ses premières missions",
    "add_project_mission": "ajouter une mission à un projet existant (project_id = son repère dans le contexte, par exemple P1)",
    "create_mission": "créer une mission hors projet, ponctuelle (démarche, paperasse, rendez-vous, course…) ; "
                      "deadline = échéance et start_date = jour à partir duquel s'y mettre, au format AAAA-MM-JJ, "
                      "tirés de ce qu'il dit (« avant vendredi », « jeudi ») avec la date du jour du contexte, sinon "
                      "null ; demande l'échéance s'il n'en a donné aucune et ne l'invente pas ; domain "
                      "religious|business|finance|health seulement s'il est évident, sinon null",
    "create_routine": "créer une routine (frequency daily|weekly|biweekly|monthly, priority low|medium|high)",
    "add_event": "ajouter un événement au calendrier : event_type event (rendez-vous qui bloque un créneau), "
                 "deadline (échéance : date et heure limite, task = ce qu'il faut avoir fait, prep_minutes = temps "
                 "estimé), vacation (vacances ou voyage, date et end_date), blocked_period (période où une activité "
                 "est impossible) ; date et end_date au format AAAA-MM-JJ, time et end_time HH:MM (null = journée "
                 "entière), tirés de ce qu'il dit avec la date du jour ; repeat none|daily|weekly|monthly|yearly "
                 "(« tous les vendredis » = weekly le jour de date) ; rien dans le passé",
}


def agents(db: Session) -> dict:
    """Agents du chatbot (paramètre éditable `chat.agents`) ; Général existe toujours."""
    return {**DEFAULT_AGENTS, **(get_parameter(db, "chat.agents", default={}) or {})}


def agent_sheet(db: Session, code: str) -> dict:
    sheet = agents(db).get(code) or DEFAULT_AGENTS["general"]
    return {**sheet, "actions": [a for a in sheet.get("actions", []) if a in ACTIONS]}


def requirements(db: Session) -> dict:
    """Fiches « ce qu'il faut savoir » par action (paramètre éditable `chat.action_requirements`)."""
    return {**DEFAULT_REQUIREMENTS, **(get_parameter(db, "chat.action_requirements", default={}) or {})}


def system_prompt(agent: dict, sheets: dict, switches: list[str] | tuple[str, ...] = ()) -> str:
    def needs(action: str) -> str:
        return " ; ".join(label for _, label in sheets.get(action, {}).get("required", []))
    actions = agent["actions"]
    lines = "".join(f"- {a} : {ACTION_HELP[a]} ; il faut {needs(a)}.\n" for a in actions)
    return (
        f"{agent.get('role', '')}\n"
        "Tu t'appelles Nexus, l'IA d'Imperium, le système personnel qui organise la vie de l'utilisateur ; si l'on te "
        "demande ton nom, c'est Nexus. Tu réponds en français, "
        "en le tutoyant, clairement et brièvement. Tu ne fais JAMAIS rien toi-même : quand l'utilisateur demande une action "
        "que tu sais faire, tu la proposes dans « proposal » et c'est lui qui la validera.\n"
        "Règles de conduite :\n"
        "- Commence par « comprehension » : relis toute la conversation et note ce que tu sais déjà pour l'action en cours, "
        "information par information, en DÉDUISANT tout ce qui peut l'être. Par exemple « je veux créer une machine à remonter "
        "le temps » donne à la fois le nom (Machine à remonter le temps) et l'objectif (construire une machine qui permet de "
        "voyager dans le temps). Ne redemande jamais ce qui est déjà dit ou déductible. Quand tu as déduit quelque chose, "
        "reprends-le au début de ta réponse (« Je note : … ») pour qu'il puisse corriger, puis ne demande que ce qui manque "
        "vraiment.\n"
        "- Avant de proposer, réunis TOUTES les informations demandées pour l'action. S'il en manque, ne propose rien : "
        "pose une ou deux questions courtes à la fois.\n"
        "- N'invente jamais une information que l'utilisateur n'a pas donnée (objectif, mission, durée, notes…) : "
        "laisse null ce qu'il n'a pas dit.\n"
        "- Les repères P1, P2… sont internes : dans tes réponses et dans summary_fr, nomme le projet par son titre.\n"
        "- Quand tu as tout, résume en une phrase dans summary_fr et propose. Une seule proposition par réponse.\n"
        "- Quand l'utilisateur donne une durée, reporte-la dans estimated_minutes (en minutes).\n"
        + (f"Actions possibles et informations à réunir :\n{lines}" if actions else "Tu ne peux proposer aucune action ici : proposal vaut toujours null.\n")
        + ("Changer d'agent : si l'utilisateur veut travailler sur un sujet qu'un autre agent gère mieux (par exemple avancer "
           "sur un projet précis), remplis « switch » : une carte lui proposera de changer, tu n'as qu'à le dire en une phrase "
           "(« on passe sur le projet … ? »). Ne pose jamais cette question sans remplir switch. Sinon switch vaut null ; "
           "une simple mention ou une action que tu sais faire toi-même ne suffit pas. Possible ici :\n"
           + "".join(f"- {code} : {SWITCH_HELP[code]}\n" for code in switches) if switches else "")
        + "Pour tout le reste (questions, conseils), réponds sans proposition : toi-même si tu sais le faire de façon "
        "fiable, sinon en remplissant expert_question (voir l'auto-évaluation). "
        "Appuie-toi seulement sur le contexte fourni et sur ce que l'utilisateur a dit.\n"
        + escalation.SELF_ASSESSMENT_RULES
    )


def _variant(action: str, required: list[str], params: dict) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["action", "summary_fr", "params"],
            "properties": {"action": {"const": action}, "summary_fr": {"type": "string", "maxLength": 300},
                           "params": {"type": "object", "additionalProperties": False, "required": required,
                                      "properties": params}}}


def output_schema(aliases: list[str], actions: list[str] | tuple[str, ...] = ACTIONS,
                  switches: list[str] | tuple[str, ...] = ()) -> dict:
    """Une variante par action, champs obligatoires compris ; `project_id` ne peut être qu'un repère réel (P1…).
    Une durée est obligatoire mais peut valoir null : le modèle doit la reporter ou dire qu'elle est inconnue."""
    minutes = {"type": ["integer", "null"]}
    text = {"type": "string"}
    notes = {"type": ["string", "null"]}
    variants = [
        _variant("create_project", ["title", "description", "missions"], {
            "title": text, "description": text,
            "missions": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                    "required": ["title", "estimated_minutes"],
                                                    "properties": {"title": text, "estimated_minutes": minutes}}}}),
        _variant("create_mission", ["title", "domain", "deadline", "start_date", "estimated_minutes", "notes"], {
            "title": text, "domain": {"enum": ["religious", "business", "finance", "health", None]},
            "deadline": {"type": ["string", "null"], "pattern": DATE_PATTERN},
            "start_date": {"type": ["string", "null"], "pattern": DATE_PATTERN}, "estimated_minutes": minutes, "notes": notes}),
        _variant("add_event", ["title", "event_type", "date", "time", "end_date", "end_time", "location", "notes",
                               "task", "prep_minutes", "urgency", "repeat"], {
            "title": text, "event_type": {"enum": ["event", "deadline", "vacation", "blocked_period"]},
            "date": {"type": "string", "pattern": DATE_PATTERN}, "time": {"type": ["string", "null"], "pattern": TIME_PATTERN},
            "end_date": {"type": ["string", "null"], "pattern": DATE_PATTERN},
            "end_time": {"type": ["string", "null"], "pattern": TIME_PATTERN}, "location": notes, "notes": notes,
            "task": notes, "prep_minutes": minutes, "urgency": {"enum": ["low", "normal", "high", "critical"]},
            "repeat": {"enum": ["none", "daily", "weekly", "monthly", "yearly"]}}),
        _variant("create_routine", ["name", "frequency", "estimated_minutes", "priority", "notes"],
                 {"name": text, "frequency": {"enum": ["daily", "weekly", "biweekly", "monthly"]}, "estimated_minutes": minutes,
                  "priority": {"enum": ["low", "medium", "high"]}, "notes": notes}),
    ]
    if aliases and "add_project_mission" in actions:
        variants.insert(1, _variant("add_project_mission", ["project_id", "title", "estimated_minutes", "notes"],
                                    {"project_id": {"enum": aliases}, "title": text, "estimated_minutes": minutes, "notes": notes}))
    variants = [v for v in variants if v["properties"]["action"]["const"] in actions]
    targets = [{"type": "object", "additionalProperties": False, "required": ["agent", "project_id"],
                "properties": {"agent": {"const": "project"}, "project_id": {"enum": aliases}}}
               for code in switches if code == "project" and aliases]
    targets += [{"type": "object", "additionalProperties": False, "required": ["agent"], "properties": {"agent": {"const": code}}}
                for code in switches if code != "project"]
    return {"type": "object", "additionalProperties": False,
            "required": ["comprehension", "assessment", "reply_fr", "proposal", "switch"],
            "properties": {"comprehension": {"type": "string", "maxLength": 800},  # réfléchir avant de répondre
                           "assessment": escalation.assessment_schema(),  # s'évaluer avant de répondre (doc 72 §3.1)
                           "reply_fr": {"type": "string", "maxLength": 1500},
                           "proposal": {"anyOf": [{"type": "null"}, *variants]},
                           "switch": {"anyOf": [{"type": "null"}, *targets]}}}


class ChatNotFoundError(ValueError):
    pass


class ChatStateError(ValueError):
    pass


def enabled(db: Session) -> bool:
    return bool(get_parameter(db, "chat.enabled", default=False))


def start_session(db: Session, *, current_user: User, payload: ChatSessionCreate) -> ChatSessionRead:
    session = ChatSession(id=uuid4(), user_id=current_user.id, context_kind=payload.context_kind,
                          context_ref=payload.context_ref, agent=_choose_agent(db, current_user, payload),
                          status="open", started_at=datetime.now(UTC))
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
    assistant, stored = _answer(db, current_user, session, now)
    turn = ChatTurnRead(user_message=ChatMessageRead.model_validate(user_message),
                        assistant_message=ChatMessageRead.model_validate(assistant),
                        proposal=ChatProposalRead.model_validate(stored) if stored else None)
    db.commit()
    return turn


def resume_after_switch(db: Session, *, current_user: User, session_id: UUID) -> ChatTurnRead:
    """Juste après un changement d'agent validé : le nouvel agent répond à la demande qui l'a amené, sans la faire
    répéter. Une seule fois par changement (aucun message depuis la validation), sinon 409."""
    session = _get(db, current_user, session_id)
    if session.status != "open":
        raise ChatStateError("Session closed.")
    switch = db.scalar(select(ChatProposal).where(ChatProposal.session_id == session.id, ChatProposal.status == "validated")
                       .order_by(ChatProposal.decided_at.desc()).limit(1))
    last = db.scalar(select(ChatMessage.created_at).where(ChatMessage.session_id == session.id)
                     .order_by(ChatMessage.created_at.desc()).limit(1))
    if switch is None or switch.action != "switch_agent" or (last is not None and last > switch.decided_at):
        raise ChatStateError("Nothing to resume.")
    assistant, stored = _answer(db, current_user, session, datetime.now(UTC), resume=True)
    turn = ChatTurnRead(user_message=None, assistant_message=ChatMessageRead.model_validate(assistant),
                        proposal=ChatProposalRead.model_validate(stored) if stored else None)
    db.commit()
    return turn


def _answer(db: Session, current_user: User, session: ChatSession, now: datetime,
            resume: bool = False) -> tuple[ChatMessage, ChatProposal | None]:
    """Réponse de l'agent de la session (et proposition éventuelle, qui remplace celle encore ouverte)."""
    agent = agent_sheet(db, session.agent)
    context, aliases = CONTEXTS[session.agent](db, current_user, session)
    switches = _switch_options(db, current_user, session, aliases)
    reply, proposal, model, latency, degraded, routing = _converse(db, session, agent, context, aliases, switches,
                                                                   resume)
    assistant = ChatMessage(id=uuid4(), session_id=session.id, user_id=current_user.id, role="assistant",
                            content=reply[:8000], model_used=model, latency_ms=latency, degraded=degraded,
                            routing=routing, created_at=datetime.now(UTC))
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
    return assistant, stored


def validate_proposal(db: Session, *, current_user: User, session_id: UUID, proposal_id: UUID) -> ChatProposalRead:
    """Seule voie d'écriture du chatbot : exécute l'action validée par l'utilisateur, idempotente."""
    proposal = _proposal(db, current_user, session_id, proposal_id)
    key = f"chat-proposal-{proposal.id}"
    try:
        if proposal.action == "switch_agent":
            result = _switch(db, current_user, _get(db, current_user, session_id), proposal.params)
        else:
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

def _choose_agent(db: Session, user: User, payload: ChatSessionCreate) -> str:
    """Le code choisit l'agent selon l'endroit d'où le terminal est ouvert ; un agent désactivé → Général.
    Le repère du contexte doit appartenir à l'utilisateur (sinon 404) ; Mission sans repère = mission en cours."""
    code = CONTEXT_AGENT.get(payload.context_kind, "general")
    if code == "general" or not agents(db).get(code, {}).get("enabled"):
        return "general"
    ref = _ref(payload.context_ref)
    if code == "project":
        project = db.get(ImperiumProject, ref) if ref else None
        if project is None or project.user_id != user.id or project.status != "open":
            raise ChatNotFoundError("Project not found.")
        return code
    if payload.context_ref is not None:
        mission = db.get(ImperiumMission, ref) if ref else None
        if mission is None or mission.user_id != user.id:
            raise ChatNotFoundError("Mission not found.")
        return code
    return code if get_current_active_mission(db, current_user=user).mission else "general"


def _ref(value: str | None) -> UUID | None:
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _switch_options(db: Session, user: User, session: ChatSession, aliases: dict[str, str]) -> list[str]:
    """Agents vers lesquels on peut proposer de passer : activés, autres que l'actuel, avec une cible réelle."""
    sheets = agents(db)
    options = [] if session.agent == "general" else ["general"]
    if sheets.get("project", {}).get("enabled") and session.agent != "project" and aliases:
        options.append("project")
    if (sheets.get("mission", {}).get("enabled") and session.agent != "mission"
            and get_current_active_mission(db, current_user=user).mission):
        options.append("mission")
    return options


def _switch_proposal(db: Session, switch: dict | None, options: list[str], aliases: dict[str, str]) -> dict | None:
    """Changement d'agent proposé par le modèle → proposition `switch_agent` ; résumé écrit par le code (titres réels)."""
    code = (switch or {}).get("agent")
    if code not in options:
        return None
    if code == "project":
        project = db.get(ImperiumProject, _ref(aliases.get(str(switch.get("project_id")))))
        if project is None:
            return None
        return {"action": "switch_agent", "params": {"agent": "project", "context_ref": str(project.id)},
                "summary_fr": f"Passer sur le projet « {project.title} »"}
    if code == "mission":
        return {"action": "switch_agent", "params": {"agent": "mission", "context_ref": None},
                "summary_fr": "Passer sur la mission en cours"}
    return {"action": "switch_agent", "params": {"agent": "general", "context_ref": None},
            "summary_fr": "Revenir à l'agent Général"}


def _switch(db: Session, user: User, session: ChatSession, params: dict) -> dict:
    """Validation d'un changement d'agent : revérifie tout (agent activé, cible à l'utilisateur) au moment du clic."""
    code = params.get("agent")
    if session.status != "open":
        raise ValueError("Session fermée.")
    if code != "general" and not agents(db).get(code, {}).get("enabled"):
        raise ValueError("Cet agent est désactivé.")
    ref = None
    if code == "project":
        project = db.get(ImperiumProject, _ref(params.get("context_ref")))
        if project is None or project.user_id != user.id or project.status != "open":
            raise ValueError("Projet introuvable.")
        ref = str(project.id)
    elif code == "mission":
        active = get_current_active_mission(db, current_user=user).mission
        if active is None:
            raise ValueError("Aucune mission en cours.")
        ref = str(active.id)
    elif code != "general":
        raise ValueError(f"Agent inconnu {code}.")
    session.agent, session.context_kind, session.context_ref = code, code, ref
    return {"agent": code, "label": agent_sheet(db, code).get("label", code), "context_ref": ref}


def _converse(db: Session, session: ChatSession, agent: dict, context: str, aliases: dict[str, str],
              switches: list[str] | None = None, resume: bool = False):
    switches = switches or []
    sheets = requirements(db)
    if local_executor.slot_mode(db, SLOT) != "live":
        return DEGRADED_REPLY, None, None, None, True, None
    history = list(db.scalars(select(ChatMessage).where(ChatMessage.session_id == session.id)
                              .order_by(ChatMessage.created_at.desc()).limit(HISTORY_MESSAGES)))[::-1]
    transcript = "\n".join(f"{'Utilisateur' if m.role == 'user' else 'Assistant'} : {m.content}" for m in history)[-HISTORY_CHARS:]
    ask = ("Réponds au dernier message de l'utilisateur." if not resume else
           f"L'utilisateur vient d'accepter de passer sur toi (agent {agent.get('label', '')}). Reprends sa dernière "
           "demande, celle qui a mené au changement, et réponds-y directement, sans la lui faire répéter.")
    prompt = f"## Contexte\n{context}\n\n## Conversation\n{transcript}\n\n{ask}"
    latency = 0
    for attempt in range(2):
        try:
            result = local_executor.structured(slot_code=SLOT, app_name="imperium", system=system_prompt(agent, sheets, switches), user=prompt,
                                               schema=output_schema(list(aliases), agent["actions"], switches), max_tokens=900, related_entity_type="chat_session",
                                               related_entity_id=session.id)
        except local_executor.LocalExecutorError:
            return DEGRADED_REPLY, None, None, latency or None, True, None
        latency += result.latency_ms
        decision = escalation.decide(db, result.output.get("assessment"))
        reply = str(result.output.get("reply_fr") or "").strip() or "…"
        proposal = result.output.get("proposal")
        if proposal and proposal.get("action") == "add_project_mission":
            # Repère court (P1…) → identifiant réel ; un repère inconnu est refusé par _check.
            params = dict(proposal.get("params") or {})
            params["project_id"] = aliases.get(str(params.get("project_id")), "")
            proposal = {**proposal, "params": params}
        errors, missing = _check(proposal, set(aliases.values()), sheets, agent["actions"]) if proposal else ([], [])
        if proposal and not errors:
            # Une proposition n'empêche pas la vraie réponse : si le message demandait un modèle plus fort (question
            # pour l'expert écrite), la réponse est escaladée et la proposition reste en carte, à valider ou non.
            question = (result.output.get("assessment") or {}).get("expert_question")
            if decision.escalates and question:
                reply, model, latency, routing = _escalate(db, session, decision, question, reply, latency)
                return reply, proposal, model, latency, False, {**routing, "with_proposal": True}
            return reply, proposal, "local_executor", latency, False, {**decision.log(), "escalated": False,
                                                                        "skipped": "proposal"}
        # Pas d'action valable : un changement d'agent proposé passe (l'autre agent saura faire l'action).
        switch = _switch_proposal(db, result.output.get("switch"), switches, aliases)
        if switch:
            return reply, switch, "local_executor", latency, False, {**decision.log(), "escalated": False,
                                                                      "skipped": "switch"}
        if not errors:
            question = (result.output.get("assessment") or {}).get("expert_question")
            reply, model, latency, routing = _escalate(db, session, decision, question, reply, latency)
            return reply, None, model, latency, False, routing
        prompt += (f"\n\n## rappel\nProposition refusée : {', '.join(errors)}. "
                   + ("Ne propose rien : pose la question à l'utilisateur." if missing else "Corrige-la ou n'en fais pas."))
    if missing:
        # Le modèle a encore proposé une action incomplète : c'est le code qui pose la question (fiche de l'action).
        return "Avant de te proposer quoi que ce soit, j'ai besoin de savoir : " + " ; ".join(missing) + ".", None, \
            "local_executor", latency, False, None
    return reply + "\n\n(Je n'ai pas réussi à formuler l'action correctement : reformule ta demande.)", None, \
        "local_executor", latency, False, None


def _escalate(db: Session, session: ChatSession, decision, question: str | None, reply: str,
              latency: int) -> tuple[str, str, int, dict]:
    """Escalade invisible : le rôle choisi répond à la question anonyme ; la décision est toujours journalisée,
    même slot éteint (mode ombre) ou en échec (la réponse locale reste). Urgence vitale : la réponse, d'où qu'elle
    vienne, commence par la ligne d'appel aux secours écrite par le code."""
    answer, model, latency, routing = _ask(db, session, decision, question, reply, latency)
    if question:
        routing["expert_question"] = escalation.scrub(question)[:1500]  # anonyme : vérifiable dans les logs de l'IA
    if decision.emergency:
        answer = f"{escalation.EMERGENCY_LINE}\n\n{answer}"
    return answer, model, latency, routing


def _ask(db: Session, session: ChatSession, decision, question: str | None, reply: str,
         latency: int) -> tuple[str, str, int, dict]:
    routing = {**decision.log(), "escalated": False}
    if not decision.escalates:
        return reply, "local_executor", latency, routing
    if not question or not question.strip():
        return reply, "local_executor", latency, {**routing, "skipped": "no_expert_question"}
    if not escalation.live(db):
        return reply, "local_executor", latency, {**routing, "skipped": "slot_off"}
    try:
        expert = escalation.ask_expert(db, decision, question, related_entity_type="chat_session",
                                       related_entity_id=session.id)
    except cloud.CloudError as exc:
        return reply, "local_executor", latency, {**routing, "skipped": "cloud_error", "error": str(exc)[:200]}
    answer = str(expert.output.get("answer_fr") or "").strip()
    if not answer:
        return reply, "local_executor", latency, {**routing, "skipped": "empty_answer"}
    return answer, expert.model[:48], latency + expert.latency_ms, {**routing, "escalated": True,
                                                                     "model": expert.model}


def _check(proposal: dict, projects: set[str], sheets: dict, allowed=ACTIONS) -> tuple[list[str], list[str]]:
    """(erreurs, informations manquantes) : action permise à l'agent, fiche de l'action, puis schémas d'écriture
    existants ; projet ouvert."""
    action, params = proposal.get("action"), proposal.get("params") or {}
    if action not in allowed:
        return [f"action {action} non permise ici"], []
    sheet = sheets.get(action, {})
    labels = dict(sheet.get("required", []))
    missing = [label for field, label in sheet.get("required", [])
               if params.get(field) in (None, "", []) or (isinstance(params.get(field), str) and not params[field].strip())]
    if action == "create_project":
        description = str(params.get("description") or "").strip()
        if description and len(description) < int(sheet.get("min_description_chars", 0)):
            missing.append(labels.get("description", "l'objectif du projet"))
        missions = [m for m in params.get("missions") or [] if str(m.get("title") or "").strip()]
        if params.get("missions") and len(missions) < int(sheet.get("min_missions", 0)):
            missing.append(labels.get("missions", "ses premières étapes"))
        if len(missions) > int(sheet.get("max_missions", 10)):
            return [f"au plus {sheet.get('max_missions', 10)} missions"], []
    if missing:
        return [f"il manque {', '.join(missing)}"], list(dict.fromkeys(missing))
    try:
        if action == "create_project":
            ProjectCreate(title=params.get("title", ""), description=params.get("description"), source="chatbot")
            for mission in params.get("missions") or []:
                ProjectMissionCreate(title=mission.get("title", ""), estimated_minutes=mission.get("estimated_minutes"))
        elif action == "add_project_mission":
            if params.get("project_id") not in projects:
                return ["project_id inconnu"], []
            ProjectMissionCreate(title=params.get("title", ""), notes=params.get("notes"),
                                 estimated_minutes=params.get("estimated_minutes"))
        elif action == "create_mission":
            _intrinsic(params)
        elif action == "add_event":
            _event(params)
        elif action == "create_routine":
            RoutineCreate(name=params.get("name", ""), frequency=params.get("frequency", "daily"),
                          estimated_minutes=params.get("estimated_minutes"), priority=params.get("priority", "medium"),
                          notes=params.get("notes"))
        else:
            return [f"action inconnue {action}"], []
    except ValidationError as exc:
        return [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()][:3], []
    except ValueError as exc:
        return [str(exc)], []
    if not str(proposal.get("summary_fr") or "").strip():
        return ["summary_fr vide"], []
    return [], []


def _execute(db: Session, user: User, action: str, params: dict, key: str) -> dict:
    params = {k: (v.strip() or None) if isinstance(v, str) else v for k, v in params.items()}  # texte vide = absent
    if action == "create_project":
        project = operations.create_project(db, current_user=user, idempotency_key=key, payload=ProjectCreate(
            title=params["title"], description=params.get("description"), source="chatbot"))
        # Projet complet en une validation (doc 72 §5) ; clés dérivées : une validation rejouée ne duplique rien.
        missions = [operations.add_project_mission(db, current_user=user, project_id=project.id, idempotency_key=f"{key}-m{i}",
                                                   payload=ProjectMissionCreate(title=m["title"].strip(),
                                                                                estimated_minutes=m.get("estimated_minutes")))
                    for i, m in enumerate(params.get("missions") or []) if str(m.get("title") or "").strip()]
        return {"project_id": str(project.id), "title": project.title, "missions": len(missions)}
    if action == "add_project_mission":
        mission = operations.add_project_mission(db, current_user=user, project_id=UUID(params["project_id"]), idempotency_key=key,
                                                 payload=ProjectMissionCreate(title=params["title"], notes=params.get("notes"),
                                                                              estimated_minutes=params.get("estimated_minutes")))
        return {"mission_id": str(mission.id), "title": mission.title}
    if action == "add_event":
        event, _duplicate = calendar.create_calendar_event(db, current_user=user, payload=_event(params),
                                                           idempotency_key=key, request_method="POST",
                                                           request_path="/api/imperium/chat/add_event")
        return {"calendar_event_id": str(event.id), "title": event.title}
    if action == "create_mission":
        mission = operations.create_intrinsic_mission(db, current_user=user, idempotency_key=key, payload=_intrinsic(params))
        return {"mission_id": str(mission.id), "title": mission.title}
    if action == "create_routine":
        routine = operations.create_routine(db, current_user=user, idempotency_key=key, payload=RoutineCreate(
            name=params["name"], frequency=params.get("frequency", "daily"), estimated_minutes=params.get("estimated_minutes"),
            priority=params.get("priority", "medium"), notes=params.get("notes")))
        return {"routine_id": str(routine.id), "name": routine.name}
    raise ValueError(f"Unknown action {action}.")


def _event(params: dict) -> CalendarEventCreate:
    """Paramètres de la proposition → événement du calendrier ; sans heure, journée entière ; refuse le passé."""
    day = date.fromisoformat(params["date"])
    end_day = date.fromisoformat(params["end_date"]) if params.get("end_date") else None
    kind = params.get("event_type") or "event"
    clock = time.fromisoformat(params["time"]) if params.get("time") else None
    if kind == "deadline":
        starts = datetime.combine(day, clock or time(23, 59), tzinfo=PARIS)
        ends = None
    else:
        starts = datetime.combine(day, clock or time.min, tzinfo=PARIS)
        if params.get("end_time"):
            ends = datetime.combine(end_day or day, time.fromisoformat(params["end_time"]), tzinfo=PARIS)
        elif end_day or clock is None:
            ends = datetime.combine(end_day or day, time(23, 59), tzinfo=PARIS)
        else:
            ends = starts + timedelta(hours=1)
    repeat = params.get("repeat") or "none"
    rrule = None if repeat == "none" else f"FREQ={repeat.upper()}" + (
        f";BYDAY={calendar_recurrence.DAYS[day.weekday()]}" if repeat == "weekly" else "")
    payload = CalendarEventCreate(
        event_type=kind, title=str(params.get("title") or ""), starts_at=starts, ends_at=ends,
        location=params.get("location"), notes=params.get("notes"), all_day=clock is None and kind != "deadline",
        urgency=params.get("urgency") or "normal", task=params.get("task"), prep_minutes=params.get("prep_minutes"),
        recurrence_rrule=rrule)
    try:
        calendar._validate(kind, starts, ends, payload.all_day, rrule)
    except calendar.CalendarEventValidationError as exc:
        raise ValueError(str(exc)) from exc
    return payload


def _intrinsic(params: dict) -> IntrinsicMissionCreate:
    """Paramètres de la proposition → mission hors projet ; échéance le soir (23 h 59 de Paris), début le matin
    (0 h) ; sans aucune date, elle commence aujourd'hui pour que le moteur du jour la propose."""
    def day(value) -> date | None:
        return date.fromisoformat(value) if value else None

    deadline, start = day(params.get("deadline")), day(params.get("start_date"))
    if deadline and start and start > deadline:
        raise ValueError("start_date après deadline")
    if start is None and deadline is None:
        start = datetime.now(PARIS).date()
    return IntrinsicMissionCreate(
        title=str(params.get("title") or ""), domain=params.get("domain"), notes=params.get("notes"),
        estimated_minutes=params.get("estimated_minutes"), source="chatbot",
        deadline_at=datetime.combine(deadline, time(23, 59), tzinfo=PARIS) if deadline else None,
        planned_start_at=datetime.combine(start, time.min, tzinfo=PARIS) if start else None)


def _day_line(db: Session, user: User) -> str:
    day = get_current_planning_day(db, current_user=user)
    today = datetime.now(PARIS).date()
    return f"Aujourd'hui : {WEEKDAYS_FR[today.weekday()]} {today.isoformat()}\nJournée : {'en cours depuis ' + day.started_at.isoformat(timespec='minutes') if day and not day.finished_at else 'non démarrée'}"


def _context(db: Session, user: User, session: ChatSession | None = None) -> tuple[str, dict[str, str]]:
    """Agent Général. Contexte en liste blanche : seulement ce qui sert aux actions du catalogue et à situer la journée."""
    lines = [_day_line(db, user)]
    active = get_current_active_mission(db, current_user=user).mission
    lines.append(f"Mission active : {active.title if active else 'aucune'}")
    projects = operations.list_projects(db, current_user=user).projects
    aliases = {f"P{i}": str(p.id) for i, p in enumerate(projects, start=1)}
    for alias, p in zip(aliases, projects):
        todo = [m.title for m in p.missions if m.status not in ("completed", "cancelled", "failed")][:8]
        lines.append(f"{alias} : projet{' actif' if p.active else ' en attente'} « {p.title} » ; missions à faire : "
                     f"{', '.join(todo) or 'aucune'}")
    intrinsic = operations.list_intrinsic_missions(db, current_user=user).missions
    lines.append("Missions hors projet à faire : " + (", ".join(
        m.title + (f" (échéance {m.deadline_at.astimezone(PARIS).date().isoformat()})" if m.deadline_at else "")
        for m in intrinsic[:10]) or "aucune"))
    now = datetime.now(UTC)
    upcoming = calendar.list_occurrences(db, current_user=user, starts_from=now, starts_to=now + timedelta(days=7))[:10]
    lines.append("Calendrier, 7 prochains jours : " + (", ".join(
        f"{o.title} ({o.starts_at.astimezone(PARIS):%a %d/%m}" + ("" if o.all_day else f" {o.starts_at.astimezone(PARIS):%H:%M}") + ")"
        for o in upcoming) or "rien"))
    routines = operations.list_routines(db, current_user=user).routines
    lines.append("Routines : " + (", ".join(f"{r.name} ({r.frequency})" for r in routines if r.active) or "aucune"))
    order = [DOMAIN_LABELS.get(p.domain, p.domain) for p in get_canonical_priority_order(db, current_user=user)]
    lines.append("Priorités : " + " > ".join(order))
    return "\n".join(lines), aliases


def _focus_project(db: Session, user: User, project_id: UUID | None, lines: list[str]) -> dict[str, str]:
    """Un seul projet, repéré P1 : objectif et missions dans l'ordre (faites comprises, pour situer l'avancement)."""
    project = next((p for p in operations.list_projects(db, current_user=user).projects if p.id == project_id), None)
    if project is None:
        lines.append("Projet : aucun (supprimé, terminé ou introuvable).")
        return {}
    lines.append(f"P1 : projet{' actif' if project.active else ' en attente'} « {project.title} »")
    lines.append(f"Objectif : {project.description or 'non précisé'}")
    for m in sorted(project.missions, key=lambda m: m.project_position or 0)[:30]:
        done = m.status in ("completed", "cancelled", "failed")
        lines.append(f"- {'[fait] ' if done else ''}{m.title}"
                     + (f" ({m.estimated_minutes} min)" if m.estimated_minutes else ""))
    if not project.missions:
        lines.append("- aucune mission pour l'instant")
    return {"P1": str(project.id)}


def _project_context(db: Session, user: User, session: ChatSession) -> tuple[str, dict[str, str]]:
    """Agent Projet : la journée et ce projet seulement ; aucun autre projet, ni routines."""
    lines = [_day_line(db, user)]
    aliases = _focus_project(db, user, _ref(session.context_ref), lines)
    return "\n".join(lines), aliases


def _mission_context(db: Session, user: User, session: ChatSession) -> tuple[str, dict[str, str]]:
    """Agent Mission : la mission (repérée, sinon celle en cours) et son projet éventuel."""
    lines = [_day_line(db, user)]
    ref = _ref(session.context_ref)
    if ref is None:
        active = get_current_active_mission(db, current_user=user).mission
        ref = active.id if active else None
    mission = db.get(ImperiumMission, ref) if ref else None
    if mission is None or mission.user_id != user.id:
        lines.append("Mission : aucune en cours.")
        return "\n".join(lines), {}
    lines.append(f"Mission : « {mission.title} » ({mission.status})"
                 + (f", prévue pour {mission.estimated_minutes} min" if mission.estimated_minutes else "")
                 + (f", démarrée à {mission.started_at.isoformat(timespec='minutes')}" if mission.status == "active" else ""))
    for label, value in (("Description", mission.description), ("Notes", mission.notes)):
        if value:
            lines.append(f"{label} : {value[:600]}")
    aliases = _focus_project(db, user, mission.project_id, lines) if mission.project_id else {}
    return "\n".join(lines), aliases


CONTEXTS = {"general": _context, "project": _project_context, "mission": _mission_context}


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
                           context_ref=session.context_ref, agent=session.agent, started_at=session.started_at, closed_at=session.closed_at,
                           messages=[ChatMessageRead.model_validate(m) for m in messages],
                           open_proposal=ChatProposalRead.model_validate(open_proposal) if open_proposal else None)
