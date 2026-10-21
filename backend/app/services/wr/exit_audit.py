"""WR P5 — audit de sortie (spec WR §9 P5 ; carte V22 ACT-WR-15), slot cloud `wr.exit_audit`, rôle `high_reasoning`.

« J'ai fini » (quand le slot est live) : la session passe en `integrating_answers` et l'audit tourne en arrière-plan.
Entrée : le digest figé, la passe d'hypothèses, la conversation de la revue (messages bornés) et les questions
« pourquoi » gardées par le conducteur. Sortie (schéma `exit_audit`) : des apprentissages atomiques, les
corrections que les réponses de l'utilisateur ont apportées aux hypothèses, et le rapport en markdown.

Le rapport devient le brouillon de la revue (même circuit qu'avant : approuver, demander des changements,
enregistrer) ; les apprentissages deviennent ses candidats mémoire, qui attendent la décision de l'utilisateur
(la confrontation d'identité §6.2 et l'écriture en mémoire restent éteintes). Échec (quota, panne) : un message
le dit, la session revient en conversation et « J'ai fini » réessaie. La partie CODE de P5 (appliquer les
validations au graphe causal, `wr_phase5_write_enabled`) n'est pas codée ici.
"""

import json
import logging
import threading
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import AIResult, AITask
from app.models.auth import User
from app.models.imperium import ImperiumWeeklyReviewMessage, ImperiumWeeklyReviewSession
from app.models.wr import WrHypothesis
from app.services.ai import cloud
from app.services.wr import digest as wr_digest

logger = logging.getLogger(__name__)

SLOT = "wr.exit_audit"
FAILED = "wr_exit_audit_failed"
KINDS = ("behavior_pattern", "blocker", "weekly_commitment", "preference", "operational_signal", "risk",
         "achievement")
MAX_FACTS = 10
MAX_MESSAGES = 60
_running: set[UUID] = set()
_lock = threading.Lock()

SYSTEM = (
    "Tu es l'auditeur de sortie de la Weekly Review d'Imperium, le système personnel d'une seule personne "
    "(missions et projets = imperium, argent = vault, VTC = vector, santé = pulse, pratique religieuse = path). "
    "Tu reçois le digest figé de la semaine, les hypothèses préparées avant la revue, puis la conversation de la "
    "revue entre l'utilisateur et Nexus. Tu consolides la vérité validée : ce que l'utilisateur a confirmé, "
    "corrigé ou décidé pèse plus que les hypothèses de départ.\n"
    "Rends :\n"
    "- learning_facts : 10 au plus, chacun UNE affirmation atomique et durable sur l'utilisateur ou son "
    "fonctionnement (pas un résumé de la semaine), avec son type, ses preuves (ids du digest ou "
    "« conversation »), une confiance initiale de 0 à 100 et la condition où elle vaut (context_predicate, "
    "sinon null). Ne garde que ce que la conversation ou les données soutiennent.\n"
    "- corrections_applied_fr : chaque hypothèse de départ que ses réponses ont corrigée ou écartée, en une "
    "phrase (« H… : … »).\n"
    "- report_md : le rapport de la semaine en markdown, en français, tutoiement, phrases courtes, avec les "
    "sections ## Ce que la semaine a montré, ## Ce que tu as dit, ## Tes décisions et engagements, "
    "## Pour la semaine prochaine, ## Questions ouvertes. Cite les chiffres du digest quand ils comptent.\n"
    "N'invente rien : pas de chiffre, de décision ni d'engagement que les données ou l'utilisateur n'ont pas donnés."
)


def output_schema() -> dict:
    return {
        "type": "object", "additionalProperties": False,
        "required": ["learning_facts", "corrections_applied_fr", "report_md"],
        "properties": {
            "learning_facts": {"type": "array", "maxItems": MAX_FACTS, "items": {
                "type": "object", "additionalProperties": False,
                "required": ["statement_fr", "kind", "evidence_refs", "initial_confidence", "context_predicate"],
                "properties": {"statement_fr": {"type": "string"}, "kind": {"type": "string", "enum": list(KINDS)},
                               "evidence_refs": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
                               "initial_confidence": {"type": "integer"},
                               "context_predicate": {"type": ["string", "null"]}}}},
            "corrections_applied_fr": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
            "report_md": {"type": "string"},
        },
    }


def live(db: Session) -> bool:
    return cloud.slot_mode(db, SLOT) == "live"


def run_in_background(session_id: UUID) -> None:
    """Tâche de fond après « J'ai fini » : sa propre session, une à la fois par WR, ne lève jamais."""
    from app.db.session import SessionLocal

    with _lock:
        if session_id in _running:
            return
        _running.add(session_id)
    try:
        with SessionLocal() as db:
            session = db.get(ImperiumWeeklyReviewSession, session_id)
            if session is not None:
                run(db, session=session)
    except Exception:  # noqa: BLE001 - l'audit ne doit jamais casser la revue
        logger.exception("WR exit audit failed.", extra={"session_id": str(session_id)})
    finally:
        with _lock:
            _running.discard(session_id)


def run(db: Session, *, session: ImperiumWeeklyReviewSession) -> bool:
    """Audit de sortie de la session en attente ; True si un brouillon est posé, False sinon (message d'échec)."""
    if session.status != "integrating_answers":
        return False
    user = db.get(User, session.user_id)
    digest_row = wr_digest.current_digest(db, current_user=user)
    found = db.scalar(select(WrHypothesis).where(WrHypothesis.digest_id == digest_row.id)) if digest_row else None
    messages = list(db.scalars(select(ImperiumWeeklyReviewMessage)
                               .where(ImperiumWeeklyReviewMessage.session_id == session.id)
                               .order_by(ImperiumWeeklyReviewMessage.created_at)))[-MAX_MESSAGES:]
    transcript = [f"{'Utilisateur' if m.role == 'user' else 'Nexus'} : {(m.content or '')[:1200]}" for m in messages
                  if m.message_type in ("chat_message", "user_answer", "assistant_followup", "initial_summary")]
    open_questions = [q for m in messages if (q := (m.payload or {}).get("open_question"))]
    prompt = (
        f"Semaine du {session.week_start} au {session.week_end}.\n\nDigest :\n"
        + json.dumps(digest_row.digest if digest_row else {}, ensure_ascii=False)
        + "\n\nHypothèses préparées :\n" + json.dumps((found.output if found else {}), ensure_ascii=False)
        + "\n\nConversation de la revue :\n" + "\n".join(transcript)
        + "\n\nQuestions « pourquoi » gardées pour l'analyse :\n" + json.dumps(open_questions, ensure_ascii=False)
    )
    try:
        result = cloud.structured(db, slot_code=SLOT, app_name="imperium", system=SYSTEM, user=prompt,
                                  schema=output_schema(), related_entity_type="weekly_review_session",
                                  related_entity_id=session.id)
    except cloud.CloudError as exc:
        db.rollback()
        _fail(db, session, exc)
        return False
    _attach(db, session, result)
    db.commit()
    return True


def _attach(db: Session, session: ImperiumWeeklyReviewSession, result: cloud.CloudResult) -> None:
    from app.services.imperium import weekly_review_conversation as wrc

    output = result.output
    facts = [{"title": item["statement_fr"][:160], "content": item["statement_fr"], "kind": item.get("kind"),
              "confidence": max(0, min(100, int(item.get("initial_confidence", 50)))),
              "evidence_refs": item.get("evidence_refs") or [], "context_predicate": item.get("context_predicate"),
              "proposed_memory_scope": "weekly_review", "source": "wr_exit_audit"}
             for item in (output.get("learning_facts") or [])[:MAX_FACTS]]
    title = f"Weekly Review {session.week_start.isoformat()} - {session.week_end.isoformat()}"
    report_md = output.get("report_md") or ""
    # Contenu du rapport à part : les candidats mémoire ne sont lus qu'une fois (colonne memory_candidates).
    payload = {"report_payload": {"title": title, "summary": "Rapport rédigé par l'audit de sortie après la conversation.",
                                  "report_markdown": report_md, "source": "wr_exit_audit",
                                  "corrections_applied_fr": output.get("corrections_applied_fr") or []},
               "report_markdown": report_md, "memory_candidates": facts}
    task = AITask(user_id=session.user_id, task_type="weekly_report.exit_audit", status="result_received",
                  source_module="imperium", input_payload={"session_id": str(session.id), "slot": SLOT},
                  model_hint=result.model, privacy_level="medium", completed_at=datetime.now(UTC))
    db.add(task)
    db.flush()
    ai_result = AIResult(task_id=task.id, user_id=session.user_id, result_type="weekly_report.draft",
                         status="pending_validation", result_payload=payload,
                         raw_payload={"source": "wr_exit_audit", "dry_run": False}, model_used=result.model,
                         provider=result.provider)
    db.add(ai_result)
    db.flush()
    wrc._attach_final_report_candidate_from_ai_result(db, session=session, ai_result=ai_result,
                                                       message_type_override="final_report_draft")
    draft = db.scalar(select(ImperiumWeeklyReviewMessage).where(ImperiumWeeklyReviewMessage.ai_result_id == ai_result.id))
    draft.created_at = datetime.now(UTC)  # heure réelle : le rapport vient après toute la conversation


def _fail(db: Session, session: ImperiumWeeklyReviewSession, exc: cloud.CloudError) -> None:
    hint = getattr(exc, "retry_hint", None)
    cause = ("Le quota de ton abonnement cloud est atteint" + (f" (retour annoncé : {hint})" if hint else "")
             if isinstance(exc, cloud.CloudQuotaError) else "Le modèle cloud est indisponible")
    db.add(ImperiumWeeklyReviewMessage(
        session_id=session.id, user_id=session.user_id, role="backend", message_type="assistant_followup",
        content=f"{cause} : je n'ai pas pu rédiger le rapport. Appuie de nouveau sur « J'ai fini » pour réessayer.",
        payload={"source": FAILED, "error": str(exc)[:200],
                 "error_kind": "quota" if isinstance(exc, cloud.CloudQuotaError) else "unavailable",
                 "retry_hint": hint}, created_at=datetime.now(UTC)))
    session.status = "conversation_active"
    db.commit()
