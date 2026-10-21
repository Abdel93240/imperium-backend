"""WR P2 — la conversation marche l'agenda de la passe d'hypothèses (spec WR §9 P1-P2), en phases.

1. Préparation (après le lancement du WR, hors de la requête) : digest figé, passe d'hypothèses P1 par le
   rôle cloud (`wr.hypothesis_pass`), puis message d'ouverture écrit par le CODE. Ne fait rien tant que le
   slot cloud est éteint : le WR garde son déroulé d'avant. Si l'appel cloud échoue (quota de l'abonnement
   atteint, avec l'heure de retour quand la CLI la donne, ou autre panne), l'ouverture le dit et la
   conversation reste possible sans agenda ; tant que l'utilisateur n'a pas répondu, « Relancer l'analyse »
   refait la préparation (l'ouverture ratée reste dans le fil).
2. Phases (portées par le payload des messages du conducteur) : `analysis` (l'ouverture présente l'analyse ;
   l'utilisateur peut y réagir), puis « Passer aux questions » (`advance`) ouvre `questions` : une question
   à la fois, choisie par sa pertinence (P1 la note de 0 à 100 ; sous `wr.question_relevance_min`, elle
   n'est pas posée ; `wr.questions_max` au plus). Une relance n'est posée que si le conducteur la juge
   encore pertinente (même seuil), `wr.followups_max` au plus par sujet. Agenda épuisé, ou l'utilisateur
   veut s'arrêter : `ready_for_report`, et « Rédiger le rapport » lance l'audit de sortie (P5).
3. Chaque message : le conducteur local (`wr.conversation`, live via `ai.local_slot_modes`) accuse
   réception ; éteint ou en échec, le code pose simplement la question suivante. Il s'auto-évalue à chaque
   message (doc 30 §5) : quand le score l'exige, la question anonyme qu'il a écrite part au rôle choisi
   (`app.services.ai.escalation`, slot `nexus.escalation`) et la réponse remplace son accusé de réception ;
   slot éteint ou échec, sa réponse reste et la décision est notée (`routing`, `needs_bigger_model`).

Le conducteur n'affirme rien qui ne vienne des hypothèses, du digest ou de la conversation, et n'écrit
rien d'autre que ses messages.
"""

import json
import logging
import re
import threading
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.imperium import ImperiumWeeklyReviewMessage, ImperiumWeeklyReviewSession
from app.models.wr import WrHypothesis
from app.services.ai import cloud, escalation, local_executor
from app.services.params import get_parameter
from app.services.wr import digest as wr_digest
from app.services.wr import hypotheses

logger = logging.getLogger(__name__)

SLOT = "wr.conversation"
OPENING = "wr_opening"
FAILED_OPENING = "wr_opening_failed"
FOLLOWUP = "wr_conductor"
ANALYSIS, QUESTIONS, READY, FREE = "analysis", "questions", "ready_for_report", "free"
READY_TEXT = "J'ai ce qu'il me faut. Quand tu veux, je rédige le rapport de la semaine."
TRANSCRIPT_MESSAGES = 12
_preparing: set[UUID] = set()
_lock = threading.Lock()
OPEN_STATUSES = ("preparing_initial_summary", "initial_summary_ready", "waiting_for_user_answer",
                 "conversation_active", "integrating_answers", "revision_requested")

SYSTEM = (
    "Tu es Nexus, l'IA d'Imperium. Tu conduis la Weekly Review de l'utilisateur : une revue des décisions de "
    "sa semaine, pas un bavardage. Tu as reçu des hypothèses préparées sur sa semaine et un agenda de "
    "questions. Tu réponds en français, en le tutoyant, en phrases courtes.\n"
    "À chaque message :\n"
    "- comprehension : ce que sa réponse t'apprend, en une ou deux phrases.\n"
    "- ack_fr : accuse réception en reprenant l'essentiel (« Je note : … »), sans juger, sans poser de question, "
    "et sans annoncer la suite (c'est l'utilisateur qui lance le rapport, par un bouton).\n"
    "- followup_fr : si sa réponse est floue ou contredit une hypothèse, UNE relance sur le même sujet, sinon "
    "null ; followup_value dit de 0 à 100 combien la réponse à cette relance changerait le rapport (0 sans "
    "relance). Ne relance pas pour un détail, et ne repose jamais une relance déjà posée : si sa réponse ne "
    "l'a pas éclairée, passe à la suite.\n"
    "- next_index : le numéro de la question restante la plus utile maintenant, -1 s'il n'en reste pas.\n"
    "- wants_report : true seulement s'il demande d'arrêter les questions ou de passer au rapport.\n"

    "- open_question : s'il pose une question « pourquoi … ? » que les hypothèses ne couvrent pas, recopie-la "
    "(sinon null) et dis dans ack_fr que tu la gardes pour l'analyse.\n"
    "- N'invente aucun fait : appuie-toi seulement sur les hypothèses, le digest et ce qu'il a dit. Ne propose "
    "jamais une autre revue ni une date, et ne nomme aucun jour de la semaine qui ne vienne pas des données.\n"
    + escalation.SELF_ASSESSMENT_RULES
)
MODE_RULES = {
    ANALYSIS: "Phase d'analyse : il réagit à l'analyse présentée. Réponds à sa remarque dans ack_fr (tu peux "
              "préciser ou corriger une hypothèse), sans poser de question de l'agenda : next_index vaut -1, "
              "followup_fr null.",
    QUESTIONS: "Phase des questions : suis les règles ci-dessus.",
    READY: "Les questions sont finies : réponds à son message dans ack_fr, sans nouvelle question ; next_index "
           "vaut -1 et followup_fr null.",
}


def opening_message(db: Session, session: ImperiumWeeklyReviewSession) -> ImperiumWeeklyReviewMessage | None:
    return db.scalar(select(ImperiumWeeklyReviewMessage).where(
        ImperiumWeeklyReviewMessage.session_id == session.id,
        ImperiumWeeklyReviewMessage.payload["source"].astext == OPENING))


def prepare_in_background(session_id: UUID) -> None:
    """Tâche de fond lancée après le lancement du WR : sa propre session, une à la fois par WR, ne lève jamais."""
    from app.db.session import SessionLocal

    with _lock:
        if session_id in _preparing:
            return
        _preparing.add(session_id)
    try:
        with SessionLocal() as db:
            session = db.get(ImperiumWeeklyReviewSession, session_id)
            if session is not None:
                prepare(db, session=session)
    except Exception:  # noqa: BLE001 - la préparation ne doit jamais casser le WR
        logger.exception("WR preparation failed.", extra={"session_id": str(session_id)})
    finally:
        with _lock:
            _preparing.discard(session_id)


def prepare(db: Session, *, session: ImperiumWeeklyReviewSession) -> ImperiumWeeklyReviewMessage | None:
    """Digest, passe d'hypothèses, ouverture ; None si le slot cloud est éteint ou la session fermée."""
    if cloud.slot_mode(db, hypotheses.SLOT) != "live" or session.status not in OPEN_STATUSES:
        return None
    existing = opening_message(db, session)
    if existing is not None:
        return existing
    user = db.get(User, session.user_id)
    digest_row, _created = wr_digest.assemble_digest(db, current_user=user)
    row, error = None, None
    try:
        row, _stats = hypotheses.run_pass(db, user=user, digest=digest_row)
    except cloud.CloudError as exc:
        db.rollback()
        error = {"error": str(exc)[:200], "error_kind": "quota" if isinstance(exc, cloud.CloudQuotaError) else "unavailable",
                 "retry_hint": getattr(exc, "retry_hint", None)}
    message = _post_opening(db, session, row, error)
    db.commit()
    return message


def can_retry(db: Session, session: ImperiumWeeklyReviewSession) -> bool:
    """Analyse ratée et pas encore de réponse de l'utilisateur : la préparation peut être refaite."""
    opening = opening_message(db, session)
    if opening is None or not (opening.payload or {}).get("error") or session.status != "initial_summary_ready":
        return False
    return db.scalar(select(ImperiumWeeklyReviewMessage.id).where(
        ImperiumWeeklyReviewMessage.session_id == session.id, ImperiumWeeklyReviewMessage.role == "user",
        ImperiumWeeklyReviewMessage.created_at >= opening.created_at).limit(1)) is None


def retry(db: Session, *, session: ImperiumWeeklyReviewSession) -> bool:
    """Écarte l'ouverture ratée (gardée dans le fil) et remet la session en préparation ; False si refusé."""
    if not can_retry(db, session):
        return False
    opening = opening_message(db, session)
    opening.payload = {**opening.payload, "source": FAILED_OPENING}
    session.status = "preparing_initial_summary"
    db.commit()
    return True


def phase(db: Session, session: ImperiumWeeklyReviewSession) -> str | None:
    """Phase de la conversation guidée ; None sans ouverture (déroulé d'avant)."""
    last = db.scalar(select(ImperiumWeeklyReviewMessage).where(
        ImperiumWeeklyReviewMessage.session_id == session.id,
        ImperiumWeeklyReviewMessage.payload["source"].astext.in_((OPENING, FOLLOWUP)))
        .order_by(ImperiumWeeklyReviewMessage.created_at.desc()).limit(1))
    if last is None:
        return None
    payload = last.payload or {}
    # Messages d'avant les phases : l'ouverture posait déjà la 1re question.
    return payload.get("phase") or (READY if payload.get("final_confirmation_prompt") else QUESTIONS)


def next_step(db: Session, session: ImperiumWeeklyReviewSession) -> str | None:
    """Bouton de passage proposé : `questions` (analyse lue), `report` (questions finies), sinon None."""
    current = phase(db, session)
    if current == ANALYSIS:
        return "questions" if _agenda(opening_message(db, session)) else "report"
    if current == READY:
        return "report"
    if current == FREE:
        return "report" if _user_answered(db, session) else None
    return None


def advance(db: Session, *, session: ImperiumWeeklyReviewSession) -> ImperiumWeeklyReviewMessage | None:
    """« Passer aux questions » : pose la question la plus pertinente ; None si la phase ne le permet pas."""
    opening = opening_message(db, session)
    agenda = _agenda(opening)
    if phase(db, session) != ANALYSIS or not agenda:
        return None
    message = _post(db, session, f"Question 1 sur {len(agenda)} : {agenda[0]['question_fr']}",
                    {"phase": QUESTIONS, "mode": "deterministic", "agenda_index": 0}, role="backend")
    session.status = "conversation_active"
    db.flush()
    return message


def reply(db: Session, *, session: ImperiumWeeklyReviewSession, user_content: str) -> ImperiumWeeklyReviewMessage:
    """Réponse du conducteur au dernier message ; écrit seulement son message (flush)."""
    opening = opening_message(db, session)
    agenda = _agenda(opening)
    current = phase(db, session)
    current = current if current in MODE_RULES else READY  # sans agenda : plus de question à poser
    messages = list(db.scalars(select(ImperiumWeeklyReviewMessage)
                               .where(ImperiumWeeklyReviewMessage.session_id == session.id)
                               .order_by(ImperiumWeeklyReviewMessage.created_at)))
    conducted = [m for m in messages if (m.payload or {}).get("source") in (OPENING, FOLLOWUP)]
    asked = [(m.payload or {}).get("agenda_index") for m in conducted if (m.payload or {}).get("phase") == QUESTIONS
             or (m.payload or {}).get("phase") is None]
    asked = {index for index in asked if index is not None}
    remaining = [index for index in range(len(agenda)) if index not in asked] if current == QUESTIONS else []
    output, mode = None, "deterministic"
    if local_executor.slot_mode(db, SLOT) == "live":
        try:
            output = _converse(db, session, opening, agenda, remaining, messages, user_content, current)
            mode = "live"
        except local_executor.LocalExecutorError:
            output = None
    if output is None:
        output = {"ack_fr": "Noté.", "followup_fr": None, "followup_value": 0,
                  "next_index": remaining[0] if remaining else -1, "wants_report": False, "open_question": None}
    text = (output.get("ack_fr") or "Noté.").strip()
    payload = {"source": FOLLOWUP, "mode": mode, "phase": current, "agenda_index": None,
               "open_question": output.get("open_question")}
    if mode == "live":
        text, payload["routing"] = _escalate(db, session, output.get("assessment"), text)
        if payload["routing"]["role"] != "local_executor":
            payload["needs_bigger_model"] = True
    if current == QUESTIONS:
        threshold = int(get_parameter(db, "wr.question_relevance_min", default=40))
        followups = _followups_since_question(conducted)
        followup = (output.get("followup_fr") or "").strip()
        if followup and _already_asked(followup, conducted):
            followup = ""  # le modèle répète une relance : on passe à la suite
        index = output.get("next_index")
        index = index if isinstance(index, int) and index in remaining else (remaining[0] if remaining else None)
        if output.get("wants_report"):
            text, payload["phase"] = _ready_text(text), READY
        elif followup and int(output.get("followup_value") or 0) >= threshold \
                and followups < int(get_parameter(db, "wr.followups_max", default=6)):
            text = f"{text} {followup}"
            payload["followup_value"] = int(output.get("followup_value") or 0)
        elif index is not None:
            text = f"{text} Question {len(asked) + 1} sur {len(agenda)} : {agenda[index]['question_fr']}"
            payload["agenda_index"] = index
        else:
            text, payload["phase"] = _ready_text(text), READY
    message = _post(db, session, text, payload, role="qwen" if mode == "live" else "backend")
    db.flush()
    return message


def _escalate(db: Session, session: ImperiumWeeklyReviewSession, assessment: dict | None,
              ack: str) -> tuple[str, dict]:
    """Escalade invisible (doc 72 §3) : la réponse du rôle choisi remplace l'accusé de réception ; sinon il reste."""
    decision = escalation.decide(db, assessment)
    routing = {**decision.log(), "escalated": False}
    question = (assessment or {}).get("expert_question")
    if not decision.escalates or not question or not escalation.live(db):
        return ack, routing
    try:
        expert = escalation.ask_expert(db, decision, question, related_entity_type="weekly_review_session",
                                       related_entity_id=session.id)
    except cloud.CloudError as exc:
        return ack, {**routing, "skipped": "cloud_error", "error": str(exc)[:200]}
    answer = str(expert.output.get("answer_fr") or "").strip()
    return (answer, {**routing, "escalated": True, "model": expert.model}) if answer else (ack, routing)


def _ready_text(ack: str) -> str:
    """Fin des questions : l'accusé de réception du modèle, sauf s'il annonce lui-même le rapport (c'est un bouton)."""
    return READY_TEXT if "rapport" in ack.lower() else f"{ack} {READY_TEXT}"


def _already_asked(followup: str, conducted: list[ImperiumWeeklyReviewMessage]) -> bool:
    """La relance ressemble à une question déjà posée par le conducteur (mots communs, 60 % au moins)."""
    def words(value: str) -> set[str]:
        return {word for word in re.findall(r"\w{4,}", value.lower())}

    asked = words(followup)
    return bool(asked) and any(len(asked & words(m.content or "")) >= 0.6 * len(asked) for m in conducted[-6:])


def _agenda(opening: ImperiumWeeklyReviewMessage | None) -> list[dict]:
    return list((opening.payload or {}).get("agenda") or []) if opening is not None else []


def _user_answered(db: Session, session: ImperiumWeeklyReviewSession) -> bool:
    return db.scalar(select(ImperiumWeeklyReviewMessage.id).where(
        ImperiumWeeklyReviewMessage.session_id == session.id,
        ImperiumWeeklyReviewMessage.role == "user").limit(1)) is not None


def _followups_since_question(conducted: list[ImperiumWeeklyReviewMessage]) -> int:
    count = 0
    for message in reversed(conducted):
        if (message.payload or {}).get("agenda_index") is not None:
            break
        count += 1
    return count


def _post(db: Session, session: ImperiumWeeklyReviewSession, content: str, payload: dict,
          *, role: str) -> ImperiumWeeklyReviewMessage:
    message = ImperiumWeeklyReviewMessage(
        session_id=session.id, user_id=session.user_id, role=role, message_type="assistant_followup",
        content=content, payload={"source": FOLLOWUP, **payload}, created_at=datetime.now(UTC))
    db.add(message)
    return message


def _post_opening(db: Session, session: ImperiumWeeklyReviewSession, row: WrHypothesis | None,
                  error: dict | None) -> ImperiumWeeklyReviewMessage:
    found = (row.output if row is not None else {}) or {}
    items = found.get("systemic_hypotheses") or []
    threshold = int(get_parameter(db, "wr.question_relevance_min", default=40))
    ranked = sorted(found.get("agenda") or [], key=lambda item: -int(item.get("relevance", 100)))
    kept = [item for item in ranked if int(item.get("relevance", 100)) >= threshold]
    kept = kept[:int(get_parameter(db, "wr.questions_max", default=30))]
    agenda = [{"question_fr": item["question_fr"], "stake_fr": item.get("stake_fr"),
               "relevance": int(item.get("relevance", 100))} for item in kept]
    if row is None:
        hint = (error or {}).get("retry_hint")
        cause = ("Le quota de ton abonnement cloud est atteint" + (f" (retour annoncé : {hint})" if hint else "")
                 + " : je n'ai pas pu préparer l'analyse de ta semaine." if (error or {}).get("error_kind") == "quota"
                 else "Je n'ai pas pu préparer l'analyse de ta semaine (modèle cloud indisponible).")
        content = (f"{cause} Appuie sur « Relancer l'analyse » plus tard, ou commence sans : qu'est-ce qui a le "
                   "plus compté pour toi cette semaine ?")
    else:
        lines = [f"• {item['statement_fr']} (confiance {item['confidence']} %)" for item in items]
        head = ("Voici ce que je retiens de ta semaine :\n" + "\n".join(lines)) if lines else (
            "Je n'ai pas trouvé de lien net entre tes domaines cette semaine.")
        content = head + "\n\n" + (
            f"J'ai retenu {len(agenda)} question{'s' if len(agenda) > 1 else ''} pour toi. Réagis à cette "
            "analyse si tu veux ; quand tu es prêt, passe aux questions." if agenda
            else "Je n'ai pas de question à te poser cette semaine. Réagis à cette analyse si tu veux ; quand tu "
                 "es prêt, je rédige le rapport.")
    message = ImperiumWeeklyReviewMessage(
        session_id=session.id, user_id=session.user_id, role="backend", message_type="initial_summary",
        content=content, created_at=datetime.now(UTC),
        payload={"source": OPENING, "phase": FREE if row is None else ANALYSIS,
                 "hypotheses_id": str(row.id) if row is not None else None, "agenda": agenda,
                 "questions_dropped": len(ranked) - len(agenda), "agenda_index": None, "error": None,
                 **(error or {})})
    db.add(message)
    if session.status in ("preparing_initial_summary", "integrating_answers"):
        session.status = "initial_summary_ready"
    db.flush()
    return message


def _converse(db: Session, session: ImperiumWeeklyReviewSession, opening: ImperiumWeeklyReviewMessage | None,
              agenda: list[dict], remaining: list[int], messages: list[ImperiumWeeklyReviewMessage],
              user_content: str, current: str) -> dict:
    found = {}
    hypotheses_id = (opening.payload or {}).get("hypotheses_id") if opening is not None else None
    if hypotheses_id:
        row = db.get(WrHypothesis, UUID(hypotheses_id))
        found = row.output if row is not None else {}
    digest_row = wr_digest.current_digest(db, current_user=db.get(User, session.user_id))
    docket = [{"type": entry.get("item_type"), "domain": entry.get("domain"), "title": entry.get("title_fr")}
              for entries in ((digest_row.digest if digest_row else {}).get("docket") or {}).values()
              for entry in entries]
    transcript = [f"{'Utilisateur' if m.role == 'user' else 'Nexus'} : {(m.content or '')[:600]}"
                  for m in messages[-TRANSCRIPT_MESSAGES:]]
    prompt = (
        f"Semaine revue : du {session.week_start.isoformat()} au {session.week_end.isoformat()}. "
        f"Aujourd'hui : {date.today().isoformat()}.\n{MODE_RULES[current]}\n\n"
        "Hypothèses préparées :\n" + json.dumps(found.get("systemic_hypotheses") or [], ensure_ascii=False)
        + "\n\nAgenda (numéro : question) :\n"
        + "\n".join(f"{i} : {item['question_fr']} ({'à poser' if i in remaining else 'déjà posée ou hors phase'})"
                    for i, item in enumerate(agenda))
        + "\n\nItems de la semaine :\n" + json.dumps(docket, ensure_ascii=False)
        + "\n\nConversation :\n" + "\n".join(transcript)
        + f"\n\nDernier message de l'utilisateur : {user_content[:1500]}\nRéponds-lui."
    )
    schema = {"type": "object", "additionalProperties": False,
              "required": ["comprehension", "assessment", "ack_fr", "followup_fr", "followup_value", "next_index",
                           "wants_report", "open_question"],
              "properties": {"comprehension": {"type": "string", "maxLength": 400},
                             "assessment": escalation.assessment_schema(),
                             "ack_fr": {"type": "string", "maxLength": 700},
                             "followup_fr": {"type": ["string", "null"], "maxLength": 300},
                             "followup_value": {"type": "integer", "minimum": 0, "maximum": 100},
                             "next_index": {"type": "integer", "enum": [*remaining, -1]},
                             "wants_report": {"type": "boolean"},
                             "open_question": {"type": ["string", "null"], "maxLength": 300}}}
    return local_executor.structured(slot_code=SLOT, app_name="imperium", system=SYSTEM, user=prompt, schema=schema,
                                     max_tokens=900, related_entity_type="weekly_review_session",
                                     related_entity_id=session.id).output
