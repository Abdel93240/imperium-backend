"""WR P2 — la conversation marche l'agenda de la passe d'hypothèses (spec WR §9 P1-P2).

1. Préparation (après le lancement du WR, hors de la requête) : digest figé, passe d'hypothèses P1 par le
   rôle cloud (`wr.hypothesis_pass`), puis message d'ouverture écrit par le CODE (hypothèses + première
   question de l'agenda). Ne fait rien tant que le slot cloud est éteint : le WR garde son déroulé d'avant.
   Si l'appel cloud échoue (quota de l'abonnement atteint, avec l'heure de retour quand la CLI la donne, ou
   autre panne), l'ouverture le dit et la conversation reste possible sans agenda ; tant que l'utilisateur
   n'a pas répondu, « Relancer l'analyse » refait la préparation (l'ouverture ratée reste dans le fil).
2. Chaque message de l'utilisateur : le conducteur local (`wr.conversation`, live via `ai.local_slot_modes`)
   répond brièvement, relance si la réponse est floue, puis pose la question restante la plus utile ;
   éteint ou en échec, le code pose simplement la question suivante. Agenda épuisé : invitation à finir.

Le conducteur n'affirme rien qui ne vienne des hypothèses, du digest ou de la conversation, et n'écrit
rien d'autre que ses messages.
"""

import json
import logging
import threading
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.imperium import ImperiumWeeklyReviewMessage, ImperiumWeeklyReviewSession
from app.models.wr import WrHypothesis
from app.services.ai import cloud, local_executor
from app.services.wr import digest as wr_digest
from app.services.wr import hypotheses

logger = logging.getLogger(__name__)

SLOT = "wr.conversation"
OPENING = "wr_opening"
FAILED_OPENING = "wr_opening_failed"
FOLLOWUP = "wr_conductor"
CLOSING_PROMPT = "As-tu autre chose à ajouter avant que je prépare le rapport final ?"
TRANSCRIPT_MESSAGES = 12
_preparing: set[UUID] = set()
_lock = threading.Lock()
OPEN_STATUSES = ("preparing_initial_summary", "initial_summary_ready", "waiting_for_user_answer",
                 "conversation_active", "integrating_answers", "revision_requested")

SYSTEM = (
    "Tu es Nexus, l'IA d'Imperium. Tu conduis la Weekly Review de l'utilisateur : une revue des décisions de "
    "sa semaine, pas un bavardage. Tu as reçu des hypothèses préparées sur sa semaine et un agenda de "
    "questions. Tu réponds en français, en le tutoyant, en trois phrases au plus.\n"
    "À chaque message :\n"
    "- Commence par « comprehension » : ce que sa réponse t'apprend, en une ou deux phrases.\n"
    "- Dans reply_fr, accuse réception en reprenant l'essentiel (« Je note : … »), sans juger.\n"
    "- Si sa réponse est floue ou contredit une hypothèse, pose UNE relance sur le même sujet et mets "
    "next_index à -1.\n"
    "- Sinon, choisis parmi les questions restantes la plus utile maintenant, recopie-la (tu peux la "
    "raccourcir) à la fin de reply_fr, et mets son numéro dans next_index.\n"
    "- S'il ne reste aucune question, next_index vaut -1 et tu termines reply_fr par : « " + CLOSING_PROMPT + " »\n"
    "- Si l'utilisateur pose une question « pourquoi … ? » que les hypothèses ne couvrent pas, recopie-la "
    "dans open_question (sinon null) et dis que tu la gardes pour l'analyse.\n"
    "- N'invente aucun fait : appuie-toi seulement sur les hypothèses, le digest et ce qu'il a dit."
)


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


def reply(db: Session, *, session: ImperiumWeeklyReviewSession, user_content: str) -> ImperiumWeeklyReviewMessage:
    """Réponse du conducteur au dernier message ; écrit seulement son message (flush)."""
    opening = opening_message(db, session)
    agenda = list((opening.payload or {}).get("agenda") or []) if opening is not None else []
    messages = list(db.scalars(select(ImperiumWeeklyReviewMessage)
                               .where(ImperiumWeeklyReviewMessage.session_id == session.id)
                               .order_by(ImperiumWeeklyReviewMessage.created_at)))
    asked = {(message.payload or {}).get("agenda_index") for message in messages
             if (message.payload or {}).get("source") in (OPENING, FOLLOWUP)}
    remaining = [index for index in range(len(agenda)) if index not in asked]
    output, mode = None, "deterministic"
    if local_executor.slot_mode(db, SLOT) == "live":
        try:
            output = _converse(db, session, opening, agenda, remaining, messages, user_content)
            mode = "live"
        except local_executor.LocalExecutorError:
            output = None
    if output is None:
        index = remaining[0] if remaining else -1
        question = agenda[index]["question_fr"] if index >= 0 else CLOSING_PROMPT
        output = {"reply_fr": f"Noté. {question}", "next_index": index, "open_question": None}
    index = output.get("next_index")
    index = index if isinstance(index, int) and index in remaining else None
    text = output["reply_fr"].strip()
    if remaining and CLOSING_PROMPT in text:
        # Agenda pas fini : jamais d'invitation à conclure, la question restante suivante la remplace.
        text = text.replace(CLOSING_PROMPT, "").strip()
        if index is None:
            index = remaining[0]
            text = f"{text} {agenda[index]['question_fr']}".strip()
    done = index is None and not remaining
    payload = {"source": FOLLOWUP, "mode": mode, "agenda_index": index, "open_question": output.get("open_question")}
    if done:
        payload["final_confirmation_prompt"] = CLOSING_PROMPT
    message = ImperiumWeeklyReviewMessage(
        session_id=session.id, user_id=session.user_id, role="qwen" if mode == "live" else "backend",
        message_type="assistant_followup", content=text, payload=payload,
        created_at=datetime.now(UTC))
    db.add(message)
    db.flush()
    return message


def _post_opening(db: Session, session: ImperiumWeeklyReviewSession, row: WrHypothesis | None,
                  error: dict | None) -> ImperiumWeeklyReviewMessage:
    found = (row.output if row is not None else {}) or {}
    items = found.get("systemic_hypotheses") or []
    agenda = [{"question_fr": item["question_fr"], "stake_fr": item.get("stake_fr")}
              for item in found.get("agenda") or []]
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
            f"J'ai {len(agenda)} question{'s' if len(agenda) > 1 else ''} pour toi. "
            f"Première : {agenda[0]['question_fr']}" if agenda
            else "Qu'est-ce qui a le plus compté pour toi cette semaine ?")
    message = ImperiumWeeklyReviewMessage(
        session_id=session.id, user_id=session.user_id, role="backend", message_type="initial_summary",
        content=content, created_at=datetime.now(UTC),
        payload={"source": OPENING, "hypotheses_id": str(row.id) if row is not None else None,
                 "agenda": agenda, "agenda_index": 0 if agenda else None, "error": None, **(error or {})})
    db.add(message)
    if session.status in ("preparing_initial_summary", "integrating_answers"):
        session.status = "initial_summary_ready"
    db.flush()
    return message


def _converse(db: Session, session: ImperiumWeeklyReviewSession, opening: ImperiumWeeklyReviewMessage | None,
              agenda: list[dict], remaining: list[int], messages: list[ImperiumWeeklyReviewMessage],
              user_content: str) -> dict:
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
        "Hypothèses préparées :\n" + json.dumps(found.get("systemic_hypotheses") or [], ensure_ascii=False)
        + "\n\nAgenda (numéro : question) :\n"
        + "\n".join(f"{i} : {item['question_fr']} ({'à poser' if i in remaining else 'déjà posée'})"
                    for i, item in enumerate(agenda))
        + "\n\nItems de la semaine :\n" + json.dumps(docket, ensure_ascii=False)
        + "\n\nConversation :\n" + "\n".join(transcript)
        + f"\n\nDernier message de l'utilisateur : {user_content[:1500]}\nRéponds-lui."
    )
    schema = {"type": "object", "additionalProperties": False,
              "required": ["comprehension", "reply_fr", "next_index", "open_question"],
              "properties": {"comprehension": {"type": "string", "maxLength": 400},
                             "reply_fr": {"type": "string", "maxLength": 900},
                             "next_index": {"type": "integer", "enum": [*remaining, -1]},
                             "open_question": {"type": ["string", "null"], "maxLength": 300}}}
    return local_executor.structured(slot_code=SLOT, app_name="imperium", system=SYSTEM, user=prompt, schema=schema,
                                     max_tokens=900, related_entity_type="weekly_review_session",
                                     related_entity_id=session.id).output
