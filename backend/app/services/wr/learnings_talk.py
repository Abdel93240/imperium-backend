"""WR — tri des apprentissages en conversation (après « Valider le rapport »).

Nexus pose la liste numérotée des apprentissages de l'audit de sortie encore à trier et demande ce qu'en
pense l'utilisateur. Il répond librement (« tout est bon », « tout sauf le 3 », « le 7, c'est plutôt … ») :
le conducteur local (`wr.conversation`) lit sa réponse et rend une décision par numéro ; sans modèle, le
code comprend seulement « tout » et « sauf N ». Quand chaque numéro a sa décision, Nexus écrit le récap ;
« Confirmer » (seule vraie validation, bouton) applique les décisions (mêmes règles que les décisions une à
une : définitives, rien n'entre en mémoire) puis enregistre la revue approuvée. Tant que le récap n'est pas
confirmé, un nouveau message le remplace.
"""

import re
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.imperium import (
    ImperiumWeeklyReviewFinalReport,
    ImperiumWeeklyReviewMessage,
    ImperiumWeeklyReviewSession,
)
from app.services.ai import local_executor

LIST = "wr_learnings_list"
NOTE = "wr_learnings_note"
RECAP = "wr_learnings_recap"
DONE = "wr_learnings_done"
SOURCES = (LIST, NOTE, RECAP, DONE)
TRANSCRIPT_MESSAGES = 10
DECISIONS = ("approve", "reject", "edit")

SYSTEM = (
    "Tu es Nexus, l'IA d'Imperium. La Weekly Review est finie ; l'utilisateur trie les apprentissages que tu "
    "proposes de retenir sur lui (liste numérotée). Lis sa réponse et rends une décision par numéro qu'elle "
    "permet de trancher :\n"
    "- approve : il est d'accord ; « tout est bon » ou « tout sauf … » vaut approve pour tous les autres ;\n"
    "- reject : il dit que c'est faux, inutile, à écarter ;\n"
    "- edit : il corrige le sens ; edited_text est alors l'apprentissage réécrit avec sa correction, en le "
    "tutoyant (« Tu … »), une seule phrase.\n"
    "Tiens compte des messages précédents de ce tri. Ne décide rien qu'il n'a pas dit ou impliqué. reply_fr : "
    "une ou deux phrases en français, tutoiement ; s'il reste des numéros sans décision ou si sa réponse est "
    "ambiguë, demande-lui ce qu'il en pense, sans reposer toute la liste."
)


def pending(db: Session, session: ImperiumWeeklyReviewSession
            ) -> tuple[ImperiumWeeklyReviewFinalReport | None, list[dict]]:
    """Rapport validé ou enregistré de l'audit et ses apprentissages encore à trier (dans l'ordre)."""
    from app.services.imperium import weekly_review_conversation as wrc

    report = db.scalar(select(ImperiumWeeklyReviewFinalReport).where(
        ImperiumWeeklyReviewFinalReport.session_id == session.id,
        ImperiumWeeklyReviewFinalReport.status.in_(("approved", "stored")),
        ImperiumWeeklyReviewFinalReport.report_payload["source"].astext == "wr_exit_audit")
        .order_by(ImperiumWeeklyReviewFinalReport.created_at.desc()).limit(1))
    if report is None:
        return None, []
    decisions = wrc._get_memory_candidate_decisions_for_report(db, report_id=report.id, user_id=session.user_id)
    response = wrc._memory_candidates_response(report=report, session=session, decisions=decisions)
    return report, [c.model_dump() for c in response.candidates
                    if c.source == "wr_exit_audit" and c.decision_status == "undecided"]


def active(db: Session, session: ImperiumWeeklyReviewSession) -> bool:
    """Tri en cours : la liste a été posée et des apprentissages attendent."""
    return _numbers(db, session) is not None and bool(pending(db, session)[1])


def post_list(db: Session, *, session: ImperiumWeeklyReviewSession) -> ImperiumWeeklyReviewMessage | None:
    """Pose la liste numérotée (après validation du rapport) ; None s'il n'y a rien à trier."""
    _report, candidates = pending(db, session)
    if not candidates:
        return None
    lines = [f"{n}. {c['content']} (confiance {round(_percent(c['confidence']))} %)"
             for n, c in enumerate(candidates, start=1)]
    content = ("Voici ce que je propose de retenir de ta semaine :\n" + "\n".join(lines) + "\n\nQu'est-ce que tu "
               "en penses ? Réponds librement, par exemple « tout est bon », « tout sauf le 3 » ou « le 2, c'est "
               "plutôt … ».")
    return _post(db, session, content, {"source": LIST, "numbers": {str(n): c["id"]
                                                                     for n, c in enumerate(candidates, start=1)}})


def reply(db: Session, *, session: ImperiumWeeklyReviewSession, user_content: str) -> ImperiumWeeklyReviewMessage:
    """Lit la réponse de l'utilisateur : récap à confirmer si tout est tranché, sinon une question (flush)."""
    numbers = _numbers(db, session) or {}
    _report, candidates = pending(db, session)
    open_ids = {c["id"] for c in candidates}
    numbers = {n: cid for n, cid in numbers.items() if cid in open_ids}
    texts = {n: next(c["content"] for c in candidates if c["id"] == cid) for n, cid in numbers.items()}
    output, mode = None, "deterministic"
    if local_executor.slot_mode(db, "wr.conversation") == "live":
        try:
            output = _read(db, session, texts, user_content)
            mode = "live"
        except local_executor.LocalExecutorError:
            output = None
    if output is None:
        output = _parse(user_content, list(numbers))
    decided: dict[str, dict] = {}
    for item in output.get("decisions") or []:
        n, decision = str(item.get("number")), item.get("decision")
        edited = (item.get("edited_text") or "").strip()
        if n in numbers and decision in DECISIONS and (decision != "edit" or edited):
            decided[n] = {"decision": decision, "edited_text": edited or None}
    if numbers and set(decided) == set(numbers):
        return _post(db, session, _recap_text(decided, texts),
                     {"source": RECAP, "mode": mode, "decisions": {numbers[n]: d for n, d in decided.items()}})
    text = (output.get("reply_fr") or "").strip() or (
        "Je n'ai pas tout compris : dis-moi par exemple « tout est bon » ou « tout sauf le 3 ».")
    return _post(db, session, text, {"source": NOTE, "mode": mode})


def can_confirm(db: Session, session: ImperiumWeeklyReviewSession) -> bool:
    """Le dernier message du tri est un récap auquel l'utilisateur n'a pas répondu."""
    last = _last(db, session)
    return last is not None and (last.payload or {}).get("source") == RECAP and bool(pending(db, session)[1])


def confirm(db: Session, *, session: ImperiumWeeklyReviewSession, user: User) -> bool:
    """Applique le récap (décisions définitives) puis enregistre la revue validée ; False si rien à confirmer."""
    from app.schemas.weekly_review import (
        WeeklyReviewMemoryCandidateApproveRequest,
        WeeklyReviewMemoryCandidateEditRequest,
        WeeklyReviewMemoryCandidateRejectRequest,
    )
    from app.services.imperium import weekly_review_conversation as wrc

    if not can_confirm(db, session):
        return False
    recap = _last(db, session)
    report, candidates = pending(db, session)
    open_ids = {c["id"] for c in candidates}
    counts = {"approve": 0, "edit": 0, "reject": 0}
    for candidate_id, decided in (recap.payload or {}).get("decisions", {}).items():
        if candidate_id not in open_ids:
            continue
        common = {"current_user": user, "report_id": report.id, "candidate_id": candidate_id,
                  "idempotency_key": str(uuid5(NAMESPACE_URL, f"wr-learnings/{recap.id}/{candidate_id}")),
                  "request_method": "POST", "request_path": f"/weekly-review/{session.id}/learnings/confirm"}
        if decided["decision"] == "approve":
            wrc.approve_weekly_review_memory_candidate(db, payload=WeeklyReviewMemoryCandidateApproveRequest(),
                                                       **common)
        elif decided["decision"] == "reject":
            wrc.reject_weekly_review_memory_candidate(db, payload=WeeklyReviewMemoryCandidateRejectRequest(),
                                                      **common)
        else:
            wrc.edit_weekly_review_memory_candidate(db, payload=WeeklyReviewMemoryCandidateEditRequest(
                edited_content=decided["edited_text"]), **common)
        counts[decided["decision"]] += 1
    stored = report.status == "approved"
    if stored:
        now = datetime.now(UTC)
        report.status, report.stored_at = "stored", now
        session.status = "stored"
        session.completed_at = session.completed_at or now
    summary = ", ".join(part for part in (
        f"{counts['approve']} retenu{'s' if counts['approve'] > 1 else ''}" if counts["approve"] else "",
        f"{counts['edit']} corrigé{'s' if counts['edit'] > 1 else ''}" if counts["edit"] else "",
        f"{counts['reject']} écarté{'s' if counts['reject'] > 1 else ''}" if counts["reject"] else "") if part)
    _post(db, session, f"C'est noté : {summary}." + (" La revue est enregistrée." if stored else "")
          + " Rien n'entre dans ma mémoire tant qu'elle n'est pas allumée.", {"source": DONE})
    db.commit()
    return True


def _numbers(db: Session, session: ImperiumWeeklyReviewSession) -> dict[str, str] | None:
    listed = db.scalar(select(ImperiumWeeklyReviewMessage).where(
        ImperiumWeeklyReviewMessage.session_id == session.id,
        ImperiumWeeklyReviewMessage.payload["source"].astext == LIST)
        .order_by(ImperiumWeeklyReviewMessage.created_at.desc()).limit(1))
    return dict((listed.payload or {}).get("numbers") or {}) if listed is not None else None


def _last(db: Session, session: ImperiumWeeklyReviewSession) -> ImperiumWeeklyReviewMessage | None:
    return db.scalar(select(ImperiumWeeklyReviewMessage).where(
        ImperiumWeeklyReviewMessage.session_id == session.id,
        (ImperiumWeeklyReviewMessage.role == "user")
        | ImperiumWeeklyReviewMessage.payload["source"].astext.in_(SOURCES))
        .order_by(ImperiumWeeklyReviewMessage.created_at.desc()).limit(1))


def _post(db: Session, session: ImperiumWeeklyReviewSession, content: str, payload: dict
          ) -> ImperiumWeeklyReviewMessage:
    message = ImperiumWeeklyReviewMessage(
        session_id=session.id, user_id=session.user_id, role="qwen" if payload.get("mode") == "live" else "backend",
        message_type="assistant_followup", content=content, payload=payload, created_at=datetime.now(UTC))
    db.add(message)
    db.flush()
    return message


def _percent(confidence) -> float:
    value = float(confidence or 0)
    return value * 100 if value <= 1 else value


def _recap_text(decided: dict[str, dict], texts: dict[str, str]) -> str:
    def numbers(kind: str) -> list[str]:
        return sorted((n for n, d in decided.items() if d["decision"] == kind), key=int)

    parts = []
    if kept := numbers("approve"):
        parts.append("Je retiens : " + ", ".join(kept) + ".")
    for n in numbers("edit"):
        parts.append(f"Je corrige le {n} : « {decided[n]['edited_text']} »")
    if dropped := numbers("reject"):
        parts.append("J'écarte : " + ", ".join(dropped) + ".")
    return "\n".join(parts) + "\n\nC'est bon pour toi ? Confirme, ou dis-moi ce qu'il faut changer."


def _parse(text: str, numbers: list[str]) -> dict:
    """Sans modèle : « tout » (avec « sauf N, M » écartés) ; sinon rien de tranché."""
    lowered = text.lower()
    if not re.search(r"\btout", lowered):
        return {"decisions": [], "reply_fr": None}
    _head, _sep, tail = lowered.partition("sauf")
    excluded = set(re.findall(r"\d+", tail))
    return {"decisions": [{"number": n, "decision": "reject" if n in excluded else "approve", "edited_text": None}
                          for n in numbers], "reply_fr": None}


def _read(db: Session, session: ImperiumWeeklyReviewSession, texts: dict[str, str], user_content: str) -> dict:
    messages = list(db.scalars(select(ImperiumWeeklyReviewMessage).where(
        ImperiumWeeklyReviewMessage.session_id == session.id)
        .order_by(ImperiumWeeklyReviewMessage.created_at.desc()).limit(TRANSCRIPT_MESSAGES)))[::-1]
    listed = next((i for i, m in enumerate(messages) if (m.payload or {}).get("source") == LIST), 0)
    transcript = [f"{'Utilisateur' if m.role == 'user' else 'Nexus'} : {(m.content or '')[:600]}"
                  for m in messages[listed + 1:]]
    prompt = ("Apprentissages à trier :\n" + "\n".join(f"{n}. {text}" for n, text in texts.items())
              + "\n\nÉchanges du tri :\n" + "\n".join(transcript)
              + f"\n\nDernier message de l'utilisateur : {user_content[:1500]}")
    schema = {"type": "object", "additionalProperties": False, "required": ["decisions", "reply_fr"],
              "properties": {"decisions": {"type": "array", "maxItems": max(1, len(texts)), "items": {
                  "type": "object", "additionalProperties": False,
                  "required": ["number", "decision", "edited_text"],
                  "properties": {"number": {"type": "string", "enum": list(texts) or ["0"]},
                                 "decision": {"type": "string", "enum": list(DECISIONS)},
                                 "edited_text": {"type": ["string", "null"], "maxLength": 600}}}},
                  "reply_fr": {"type": ["string", "null"], "maxLength": 500}}}
    return local_executor.structured(slot_code="wr.conversation", app_name="imperium", system=SYSTEM, user=prompt,
                                     schema=schema, max_tokens=1200, related_entity_type="weekly_review_session",
                                     related_entity_id=session.id).output
