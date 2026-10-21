"""PostgreSQL : audit de sortie du WR (spec WR §9 P5) — le rapport de la revue et ses apprentissages, rédigés
par le rôle cloud après « Rédiger le rapport », sa réécriture
unique et le tri des apprentissages en conversation. CLI cloud simulée : aucun appel réel."""
from __future__ import annotations

import json
from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("WR exit audit DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models.auth import User  # noqa: E402
from app.models.imperium import (  # noqa: E402
    ImperiumWeeklyReviewMessage,
    ImperiumWeeklyReviewSession,
    ImperiumWeeklyReviewState,
)
from app.schemas.weekly_review import WeeklyReviewAnswerRequest  # noqa: E402
from app.services.ai import cloud, local_executor  # noqa: E402
from app.services.imperium import weekly_review_conversation as wrc  # noqa: E402
from app.services.imperium.weekly_review_state import week_start_on  # noqa: E402
from app.services.params import set_parameter  # noqa: E402
from app.services.wr import conductor, docket, exit_audit  # noqa: E402
from app.schemas.weekly_review import WeeklyReviewChatConfirmRequest  # noqa: E402

AGENDA = [{"question_fr": "Qu'est-ce qui a changé mercredi ?", "stake_fr": "La rupture.", "refs": []},
          {"question_fr": "Pourquoi le carburant a-t-il monté ?", "stake_fr": "Le net.", "refs": []},
          {"question_fr": "Tu veux une heure limite pour le VTC ?", "stake_fr": "Le sommeil.", "refs": []}]
PASS = {"systemic_hypotheses": [{"statement_fr": "La fatigue pèse sur le VTC.", "domains": ["pulse", "vector"],
                                 "evidence_refs": [], "confidence": 55}],
        "agenda": AGENDA, "drill_requests": []}


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


class Fakes:
    def __init__(self) -> None:
        self.cloud: list = []
        self.local: list = []
        self.prompts: list[str] = []

    def cli(self, args, stdin, timeout, cwd):
        item = self.cloud.pop(0)
        if isinstance(item, Exception):
            raise item
        return json.dumps({"type": "result", "subtype": "success", "is_error": False, "structured_output": item,
                           "usage": {"input_tokens": 10, "output_tokens": 10}, "modelUsage": {"m": {}}})

    def post(self, url, payload, timeout):
        self.prompts.append(payload["messages"][1]["content"])
        item = self.local.pop(0)
        if isinstance(item, Exception):
            raise item
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(item)}}], "usage": {}}


@pytest.fixture()
def fakes(monkeypatch) -> Fakes:
    fake = Fakes()
    monkeypatch.setattr(cloud, "_run", fake.cli)
    monkeypatch.setattr(cloud, "_binary", lambda name: name)
    monkeypatch.setattr(cloud.call_log, "record", lambda **row: None)
    monkeypatch.setattr(local_executor, "_http_post", fake.post)
    monkeypatch.setattr(local_executor, "get_settings", lambda: SimpleNamespace(
        local_executor_url="http://127.0.0.1:8081", local_executor_timeout_seconds=5))
    monkeypatch.setattr(local_executor.call_log, "record", lambda **row: None)
    return fake


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"wc-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _monday() -> date:
    """Début de la semaine du WR qui contient aujourd'hui (mardi, `wr.week_start_weekday` semé à 1)."""
    return week_start_on(date.today(), 1)


def _launch(db, user) -> ImperiumWeeklyReviewSession:
    db.add(ImperiumWeeklyReviewState(user_id=user.id, week_start=_monday(), ready=True, ready_at=datetime.now(UTC)))
    db.commit()
    docket.create_item(db, current_user=user, item_type="anomaly", domain="vault", title_fr="Carburant +60 %",
                       payload={}, evidence_refs={}, impact_estimate=3, source_worker="w4")
    db.commit()
    read, _duplicate = wrc.launch_weekly_review_session(db, current_user=user, week_start=_monday(),
                                                        idempotency_key=str(uuid4()), request_method="POST",
                                                        request_path="/api/imperium/weekly-review/launch")
    return db.get(ImperiumWeeklyReviewSession, read.id)


def _cloud_on(db) -> None:
    set_parameter(db, code="ai.cloud_transport", value="subscription", origin="user", rationale_fr="Test.")
    set_parameter(db, code="ai.cloud_slot_modes", value={"wr.hypothesis_pass": "live", "wr.exit_audit": "live"},
                  origin="user", rationale_fr="Test.")
    db.commit()


def _chat(db, user, session, content: str) -> ImperiumWeeklyReviewMessage:
    wrc.add_weekly_review_chat_message(db, session_id=session.id, current_user=user,
                                       payload=WeeklyReviewAnswerRequest(content=content),
                                       idempotency_key=str(uuid4()), request_method="POST", request_path="/chat")
    return db.scalars(select(ImperiumWeeklyReviewMessage).where(ImperiumWeeklyReviewMessage.session_id == session.id)
                      .order_by(ImperiumWeeklyReviewMessage.created_at.desc())).first()



AUDIT = {"learning_facts": [{"statement_fr": "Rouler après 22 h fait rater les missions du matin.", "kind": "behavior_pattern",
                             "evidence_refs": ["conversation"], "initial_confidence": 70,
                             "context_predicate": "veille d'une mission du matin"},
                            {"statement_fr": "Tu arrêtes le VTC à 22 h la veille d'une mission du matin.",
                             "kind": "weekly_commitment", "evidence_refs": ["conversation"], "initial_confidence": 90,
                             "context_predicate": None}],
         "corrections_applied_fr": ["H1 : la baisse vient d'une panne de clim, pas de la fatigue."],
         "report_md": "## Ce que la semaine a montré\nUne rupture mercredi.\n\n## Tes décisions et engagements\nStop à 22 h."}


def _finish(db, user, session, content=None):
    return wrc.confirm_weekly_review_no_more_input(db, session_id=session.id, current_user=user,
                                                   payload=WeeklyReviewChatConfirmRequest(content=content),
                                                   idempotency_key=str(uuid4()), request_method="POST",
                                                   request_path="/confirm")[0]


def _conversation_ready(db, fakes):
    user = _user(db)
    session = _launch(db, user)
    _cloud_on(db)
    fakes.cloud = [PASS]
    conductor.prepare(db, session=session)
    _chat(db, user, session, "Mercredi, panne de clim.")
    return user, session


def test_finish_without_the_slot_keeps_the_trial_draft(db, fakes) -> None:
    user = _user(db)
    session = _launch(db, user)
    set_parameter(db, code="ai.cloud_transport", value="subscription", origin="user", rationale_fr="Test.")
    set_parameter(db, code="ai.cloud_slot_modes", value={"wr.hypothesis_pass": "live"}, origin="user", rationale_fr="Test.")
    db.commit()
    fakes.cloud = [PASS]
    conductor.prepare(db, session=session)
    _chat(db, user, session, "Semaine dure.")
    assert not exit_audit.live(db)
    assert _finish(db, user, session).status == "draft_ready" and fakes.cloud == []


def test_exit_audit_writes_the_report_and_its_learnings(db, fakes, monkeypatch) -> None:
    user, session = _conversation_ready(db, fakes)
    prompts = []
    original = fakes.cli
    monkeypatch.setattr(cloud, "_run", lambda args, stdin, timeout, cwd: prompts.append(stdin) or original(args, stdin, timeout, cwd))
    read = _finish(db, user, session, "Je veux arrêter à 22 h.")
    assert read.status == "integrating_answers"
    waiting = wrc.get_weekly_review_conversation(db, current_user=user, session_id=session.id)
    assert waiting.flags.is_waiting_for_ai and not waiting.flags.can_send_message
    fakes.cloud = [AUDIT]
    assert exit_audit.run(db, session=session) is True
    prompt = prompts[-1]
    assert "La fatigue pèse sur le VTC." in prompt and "Utilisateur : Mercredi, panne de clim." in prompt
    assert "Utilisateur : Je veux arrêter à 22 h." in prompt and "Carburant +60 %" in prompt
    conversation = wrc.get_weekly_review_conversation(db, current_user=user, session_id=session.id)
    assert conversation.ui_state == "draft_ready" and conversation.flags.can_approve
    draft = conversation.chat_timeline[-1]
    assert draft.type == "final_draft" and draft.content.startswith("## Ce que la semaine a montré")
    assert draft.display_payload["source"] == "wr_exit_audit"
    assert draft.display_payload["corrections_applied_fr"] == AUDIT["corrections_applied_fr"]
    candidates = wrc.get_weekly_review_memory_candidates(db, current_user=user, session_id=session.id).candidates
    assert [(c.kind, c.content) for c in candidates] == [
        ("behavior_pattern", "Rouler après 22 h fait rater les missions du matin."),
        ("weekly_commitment", "Tu arrêtes le VTC à 22 h la veille d'une mission du matin.")]
    assert [c.confidence for c in candidates] == [0.7, 0.9]
    assert exit_audit.run(db, session=session) is False  # plus en attente : rien à refaire


def test_quota_during_the_audit_lets_the_user_retry(db, fakes) -> None:
    user, session = _conversation_ready(db, fakes)
    _finish(db, user, session)
    fakes.cloud = [cloud.CloudQuotaError("Subscription quota reached", "09:00")]
    assert exit_audit.run(db, session=session) is False
    last = db.scalars(select(ImperiumWeeklyReviewMessage).where(ImperiumWeeklyReviewMessage.session_id == session.id)
                      .order_by(ImperiumWeeklyReviewMessage.created_at.desc())).first()
    assert last.content.startswith("Le quota de ton abonnement cloud est atteint (retour annoncé : 09:00)")
    assert "Rédiger le rapport" in last.content and session.status == "conversation_active"
    assert _finish(db, user, session).status == "integrating_answers"
    fakes.cloud = [AUDIT]
    assert exit_audit.run(db, session=session) is True and session.status == "draft_ready"


REVISED = {**AUDIT, "report_md": "## Ce que la semaine a montré\nUne panne de clim mercredi.",
           "corrections_applied_fr": ["La rupture vient de la clim."]}


def _last(db, session) -> ImperiumWeeklyReviewMessage:
    return db.scalars(select(ImperiumWeeklyReviewMessage).where(ImperiumWeeklyReviewMessage.session_id == session.id)
                      .order_by(ImperiumWeeklyReviewMessage.created_at.desc())).first()


def _drafted(db, fakes):
    user, session = _conversation_ready(db, fakes)
    _finish(db, user, session)
    fakes.cloud = [AUDIT]
    assert exit_audit.run(db, session=session) is True
    return user, session


def _changes(db, user, session, content):
    return wrc.request_draft_changes(db, session_id=session.id, current_user=user,
                                     payload=WeeklyReviewAnswerRequest(content=content), idempotency_key=str(uuid4()),
                                     request_method="POST", request_path="/changes")[0]


def _flags(db, user, session):
    return wrc.get_weekly_review_conversation(db, current_user=user, session_id=session.id).flags


def test_the_report_asks_no_question_and_is_rewritten_once(db, fakes, monkeypatch) -> None:
    user, session = _conversation_ready(db, fakes)
    calls = []
    original = fakes.cli
    monkeypatch.setattr(cloud, "_run", lambda args, stdin, timeout, cwd: calls.append((args, stdin))
                        or original(args, stdin, timeout, cwd))
    _finish(db, user, session)
    fakes.cloud = [AUDIT]
    exit_audit.run(db, session=session)
    system = calls[-1][0][calls[-1][0].index("--system-prompt") + 1]
    assert "## À reprendre à la prochaine revue" in system and "ne pose AUCUNE question" in system
    flags = _flags(db, user, session)
    assert (flags.phase, flags.can_request_changes, flags.can_revise_report) == ("report", True, False)

    _changes(db, user, session, "La rupture vient de la clim, pas de la fatigue.")
    _changes(db, user, session, "Et j'ai roulé jeudi.")
    assert session.status == "draft_ready" and "Mettre à jour le rapport" in _last(db, session).content
    assert _flags(db, user, session).can_revise_report and _flags(db, user, session).can_approve
    wrc.revise_weekly_review_report(db, session_id=session.id, current_user=user)
    assert session.status == "integrating_answers"
    fakes.cloud = [REVISED]
    assert exit_audit.revise(db, session=session) is True
    prompt = calls[-1][1]
    assert "Rapport actuel :\n## Ce que la semaine a montré\nUne rupture mercredi." in prompt
    assert "- La rupture vient de la clim, pas de la fatigue.\n- Et j'ai roulé jeudi." in prompt
    conversation = wrc.get_weekly_review_conversation(db, current_user=user, session_id=session.id)
    drafts = [item for item in conversation.chat_timeline if item.type == "final_draft"]
    assert [d.display_payload.get("superseded", False) for d in drafts] == [True, False]
    assert drafts[-1].content == REVISED["report_md"] and conversation.flags.can_approve
    assert not conversation.flags.can_request_changes and not conversation.flags.can_revise_report  # une seule fois
    with pytest.raises(wrc.WeeklyReviewStateConflictError):
        _changes(db, user, session, "Encore un détail.")


def test_revision_uses_the_light_slot_when_it_is_live(db, fakes, monkeypatch) -> None:
    user, session = _drafted(db, fakes)
    set_parameter(db, code="ai.cloud_slot_modes", value={"wr.hypothesis_pass": "live", "wr.exit_audit": "live",
                                                         "wr.report_revision": "live"}, origin="user", rationale_fr="Test.")
    db.commit()
    slots = []
    original = cloud.structured
    monkeypatch.setattr(cloud, "structured", lambda db, **kw: slots.append(kw["slot_code"]) or original(db, **kw))
    _changes(db, user, session, "Corrige la date.")
    wrc.revise_weekly_review_report(db, session_id=session.id, current_user=user)
    fakes.cloud = [cloud.CloudQuotaError("Subscription quota reached", None)]
    assert exit_audit.revise(db, session=session) is False and slots == ["wr.report_revision"]
    assert session.status == "draft_ready" and "Mettre à jour le rapport" in _last(db, session).content
    assert _flags(db, user, session).can_revise_report  # la correction attend toujours


def _approved(db, fakes):
    user, session = _drafted(db, fakes)
    wrc.approve_latest_draft_report(db, session_id=session.id, current_user=user, idempotency_key=str(uuid4()),
                                    request_method="POST", request_path="/approve")
    return user, session


def test_learnings_are_sorted_in_conversation_then_confirmed(db, fakes) -> None:
    user, session = _approved(db, fakes)
    listing = _last(db, session)
    assert listing.payload["source"] == "wr_learnings_list"
    assert "1. Rouler après 22 h fait rater les missions du matin. (confiance 70 %)" in listing.content
    flags = _flags(db, user, session)
    assert (flags.phase, flags.can_send_message, flags.can_store, flags.can_confirm_learnings) == (
        "learnings", True, False, False)

    unclear = _chat(db, user, session, "Hmm.")  # sans modèle, le code ne comprend que « tout » et « sauf N »
    assert unclear.payload["source"] == "wr_learnings_note" and "tout sauf le 3" in unclear.content
    recap = _chat(db, user, session, "Tout est bon sauf le 2.")
    assert recap.payload["source"] == "wr_learnings_recap"
    assert recap.content.startswith("Je retiens : 1.\nJ'écarte : 2.")
    assert _flags(db, user, session).can_confirm_learnings
    wrc.confirm_weekly_review_learnings(db, session_id=session.id, current_user=user)
    assert session.status == "stored" and _last(db, session).content.startswith("C'est noté : 1 retenu, 1 écarté.")
    decided = {c.content: c.decision_status for c in
               wrc.get_weekly_review_memory_candidates(db, current_user=user, session_id=session.id).candidates}
    assert decided == {AUDIT["learning_facts"][0]["statement_fr"]: "approved",
                       AUDIT["learning_facts"][1]["statement_fr"]: "rejected"}
    flags = _flags(db, user, session)
    assert not flags.can_send_message and not flags.can_confirm_learnings and flags.is_closed
    with pytest.raises(wrc.WeeklyReviewStateConflictError):
        wrc.confirm_weekly_review_learnings(db, session_id=session.id, current_user=user)


def test_local_model_reads_corrections_and_a_new_answer_replaces_the_recap(db, fakes) -> None:
    user, session = _approved(db, fakes)
    set_parameter(db, code="ai.local_slot_modes", value={"wr.conversation": "live"}, origin="user", rationale_fr="Test.")
    db.commit()
    fakes.local = [
        {"decisions": [{"number": "1", "decision": "approve", "edited_text": None}],
         "reply_fr": "Et le 2, tu le gardes ?"},
        {"decisions": [{"number": "1", "decision": "approve", "edited_text": None},
                       {"number": "2", "decision": "edit", "edited_text": "Tu arrêtes le VTC à 23 h."}],
         "reply_fr": None},
        {"decisions": [{"number": "1", "decision": "reject", "edited_text": None},
                       {"number": "2", "decision": "edit", "edited_text": "Tu arrêtes le VTC à 23 h."}],
         "reply_fr": None},
    ]
    ask = _chat(db, user, session, "Le 1 oui.")
    assert ask.content == "Et le 2, tu le gardes ?" and not _flags(db, user, session).can_confirm_learnings
    recap = _chat(db, user, session, "Le 2 c'est plutôt 23 h.")
    assert "Je corrige le 2 : « Tu arrêtes le VTC à 23 h. »" in recap.content
    assert "Apprentissages à trier :\n1. Rouler après 22 h" in fakes.prompts[1] and "Le 1 oui." in fakes.prompts[1]
    _chat(db, user, session, "Finalement, oublie le 1.")
    wrc.confirm_weekly_review_learnings(db, session_id=session.id, current_user=user)
    candidates = wrc.get_weekly_review_memory_candidates(db, current_user=user, session_id=session.id).candidates
    assert [c.decision_status for c in candidates] == ["rejected", "edited"]
    assert candidates[1].effective_candidate["content"] == "Tu arrêtes le VTC à 23 h."
