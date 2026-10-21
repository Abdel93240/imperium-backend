"""PostgreSQL : la conversation du WR marche l'agenda de la passe d'hypothèses (spec WR §9 P1-P2).
CLI cloud et exécuteur local simulés : aucun appel réel."""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("WR conductor DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models.auth import User  # noqa: E402
from app.models.imperium import (  # noqa: E402
    ImperiumWeeklyReviewMessage,
    ImperiumWeeklyReviewSession,
    ImperiumWeeklyReviewState,
)
from app.models.wr import WrHypothesis  # noqa: E402
from app.schemas.weekly_review import WeeklyReviewAnswerRequest  # noqa: E402
from app.services.ai import cloud, local_executor  # noqa: E402
from app.services.imperium import weekly_review_conversation as wrc  # noqa: E402
from app.services.params import set_parameter  # noqa: E402
from app.services.wr import conductor, docket  # noqa: E402

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
    set_parameter(db, code="ai.cloud_slot_modes", value={"wr.hypothesis_pass": "live"}, origin="user",
                  rationale_fr="Test.")
    db.commit()


def _chat(db, user, session, content: str) -> ImperiumWeeklyReviewMessage:
    wrc.add_weekly_review_chat_message(db, session_id=session.id, current_user=user,
                                       payload=WeeklyReviewAnswerRequest(content=content),
                                       idempotency_key=str(uuid4()), request_method="POST", request_path="/chat")
    return db.scalars(select(ImperiumWeeklyReviewMessage).where(ImperiumWeeklyReviewMessage.session_id == session.id)
                      .order_by(ImperiumWeeklyReviewMessage.created_at.desc())).first()


def test_launch_marks_the_week_and_preparation_waits_for_the_cloud_slot(db, fakes) -> None:
    user = _user(db)
    session = _launch(db, user)
    state = db.scalar(select(ImperiumWeeklyReviewState).where(ImperiumWeeklyReviewState.user_id == user.id))
    assert state.launched and state.launched_at is not None
    assert conductor.prepare(db, session=session) is None and fakes.cloud == []
    assert session.status == "preparing_initial_summary"


def test_opening_then_the_code_walks_the_agenda(db, fakes) -> None:
    user = _user(db)
    session = _launch(db, user)
    _cloud_on(db)
    fakes.cloud = [PASS]
    opening = conductor.prepare(db, session=session)
    assert opening.message_type == "initial_summary" and opening.role == "backend"
    assert "La fatigue pèse sur le VTC. (confiance 55 %)" in opening.content
    assert "J'ai 3 questions pour toi. Première : Qu'est-ce qui a changé mercredi ?" in opening.content
    assert session.status == "initial_summary_ready" and opening.payload["agenda_index"] == 0
    assert db.scalar(select(WrHypothesis).where(WrHypothesis.user_id == user.id)) is not None
    assert conductor.prepare(db, session=session).id == opening.id  # une seule ouverture

    first = _chat(db, user, session, "Je me suis couché tard mardi.")
    assert first.content == "Noté. Pourquoi le carburant a-t-il monté ?" and first.payload["agenda_index"] == 1
    assert first.payload["mode"] == "deterministic" and first.role == "backend"
    _chat(db, user, session, "Des trajets à vide.")
    last = _chat(db, user, session, "Oui, 22 h.")
    assert last.payload["agenda_index"] is None and last.payload["final_confirmation_prompt"] == conductor.CLOSING_PROMPT
    conversation = wrc.get_weekly_review_conversation(db, current_user=user, session_id=session.id)
    assert conversation.flags.can_send_message and conversation.latest_assistant_prompt == conductor.CLOSING_PROMPT
    assert [item.role for item in conversation.chat_timeline][-2:] == ["user", "assistant"]


def test_local_conductor_picks_the_next_question(db, fakes) -> None:
    user = _user(db)
    session = _launch(db, user)
    _cloud_on(db)
    set_parameter(db, code="ai.local_slot_modes", value={"wr.conversation": "live"}, origin="user", rationale_fr="Test.")
    db.commit()
    fakes.cloud = [PASS]
    conductor.prepare(db, session=session)
    fakes.local = [
        {"comprehension": "Rupture mardi soir.", "reply_fr": "Je note : coucher tard. On garde l'heure limite ?",
         "next_index": 2, "open_question": None},
        {"comprehension": "Flou.", "reply_fr": "Tu veux dire quoi par « bof » ?", "next_index": -1,
         "open_question": "Pourquoi je dors mal ?"},
        {"comprehension": "Rien.", "reply_fr": f"Je note. {conductor.CLOSING_PROMPT}", "next_index": -1,
         "open_question": None},
        local_executor.LocalExecutorError("down"),
    ]
    reply = _chat(db, user, session, "Je me suis couché tard mardi.")
    assert reply.role == "qwen" and reply.payload == {"source": "wr_conductor", "mode": "live", "agenda_index": 2,
                                                      "open_question": None}
    prompt = fakes.prompts[0]
    assert "La fatigue pèse sur le VTC." in prompt and "0 : Qu'est-ce qui a changé mercredi ? (déjà posée)" in prompt
    assert "1 : Pourquoi le carburant a-t-il monté ? (à poser)" in prompt and "Carburant +60 %" in prompt
    relance = _chat(db, user, session, "bof")
    assert relance.payload["agenda_index"] is None and relance.payload["open_question"] == "Pourquoi je dors mal ?"
    assert "final_confirmation_prompt" not in relance.payload
    early = _chat(db, user, session, "Rien d'autre.")  # agenda pas fini : pas d'invitation à conclure
    assert early.content == "Je note. Pourquoi le carburant a-t-il monté ?" and early.payload["agenda_index"] == 1
    assert "final_confirmation_prompt" not in early.payload
    fallback = _chat(db, user, session, "Je sais pas.")  # modèle en panne, agenda fini : le code conclut
    assert fallback.payload["mode"] == "deterministic" and fallback.content == f"Noté. {conductor.CLOSING_PROMPT}"
    assert fallback.payload["final_confirmation_prompt"] == conductor.CLOSING_PROMPT


def test_cloud_failure_still_opens_the_conversation(db, fakes) -> None:
    user = _user(db)
    session = _launch(db, user)
    _cloud_on(db)
    fakes.cloud = [cloud.CloudError("Cloud CLI exited with 1.")]
    opening = conductor.prepare(db, session=session)
    assert "modèle cloud indisponible" in opening.content and opening.payload["agenda"] == []
    assert opening.payload["error"] and session.status == "initial_summary_ready"
    reply = _chat(db, user, session, "Semaine dure.")
    assert reply.content == f"Noté. {conductor.CLOSING_PROMPT}"


def test_quota_opening_then_retry_until_the_user_answers(db, fakes) -> None:
    user = _user(db)
    session = _launch(db, user)
    _cloud_on(db)
    fakes.cloud = [cloud.CloudQuotaError("Subscription quota reached", "17:00")]
    failed = conductor.prepare(db, session=session)
    assert failed.content.startswith("Le quota de ton abonnement cloud est atteint (retour annoncé : 17:00)")
    assert "Relancer l'analyse" in failed.content
    assert (failed.payload["error_kind"], failed.payload["retry_hint"]) == ("quota", "17:00")
    conversation = wrc.get_weekly_review_conversation(db, current_user=user, session_id=session.id)
    assert conversation.flags.can_retry_analysis and conversation.flags.can_send_message

    read = wrc.retry_weekly_review_analysis(db, session_id=session.id, current_user=user)
    assert read.status == "preparing_initial_summary" and failed.payload["source"] == conductor.FAILED_OPENING
    assert not wrc.get_weekly_review_conversation(db, current_user=user, session_id=session.id).flags.can_retry_analysis
    fakes.cloud = [PASS]
    opening = conductor.prepare(db, session=session)
    assert opening.id != failed.id and opening.payload["agenda_index"] == 0 and opening.payload["error"] is None
    assert session.status == "initial_summary_ready"
    with pytest.raises(wrc.WeeklyReviewStateConflictError):  # analyse réussie : rien à relancer
        wrc.retry_weekly_review_analysis(db, session_id=session.id, current_user=user)


def test_no_retry_once_the_user_has_answered(db, fakes) -> None:
    user = _user(db)
    session = _launch(db, user)
    _cloud_on(db)
    fakes.cloud = [cloud.CloudError("Cloud CLI exited with 1.")]
    failed = conductor.prepare(db, session=session)
    assert "modèle cloud indisponible" in failed.content and failed.payload["error_kind"] == "unavailable"
    assert conductor.can_retry(db, session)
    _chat(db, user, session, "Semaine dure.")
    assert not conductor.can_retry(db, session)
    with pytest.raises(wrc.WeeklyReviewStateConflictError):
        wrc.retry_weekly_review_analysis(db, session_id=session.id, current_user=user)
