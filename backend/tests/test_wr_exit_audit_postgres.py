"""PostgreSQL : audit de sortie du WR (spec WR §9 P5) — le rapport de la revue et ses apprentissages, rédigés
par le rôle cloud après « J'ai fini ». CLI cloud simulée : aucun appel réel."""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
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
    return date.today() - timedelta(days=date.today().weekday())


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
    assert "J'ai fini" in last.content and session.status == "conversation_active"
    assert _finish(db, user, session).status == "integrating_answers"
    fakes.cloud = [AUDIT]
    assert exit_audit.run(db, session=session) is True and session.status == "draft_ready"
