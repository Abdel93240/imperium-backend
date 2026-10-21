"""PostgreSQL : la conversation du WR marche l'agenda de la passe d'hypothèses (spec WR §9 P1-P2).
CLI cloud et exécuteur local simulés : aucun appel réel."""
from __future__ import annotations

import json
from datetime import UTC, date, datetime
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
from app.services.imperium.weekly_review_state import week_start_on  # noqa: E402
from app.services.params import set_parameter  # noqa: E402
from app.services.wr import conductor, docket  # noqa: E402

AGENDA = [{"question_fr": "Qu'est-ce qui a changé mercredi ?", "stake_fr": "La rupture.", "refs": [], "relevance": 60},
          {"question_fr": "Pourquoi le carburant a-t-il monté ?", "stake_fr": "Le net.", "refs": [], "relevance": 90},
          {"question_fr": "Tu veux une couleur de thème ?", "stake_fr": "Rien.", "refs": [], "relevance": 20}]
CARBURANT, MERCREDI = AGENDA[1]["question_fr"], AGENDA[0]["question_fr"]
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


def _flags(db, user, session):
    return wrc.get_weekly_review_conversation(db, current_user=user, session_id=session.id).flags


def test_opening_then_the_code_walks_the_agenda_by_relevance(db, fakes) -> None:
    user = _user(db)
    session = _launch(db, user)
    _cloud_on(db)
    fakes.cloud = [PASS]
    opening = conductor.prepare(db, session=session)
    assert opening.message_type == "initial_summary" and opening.role == "backend"
    assert "La fatigue pèse sur le VTC. (confiance 55 %)" in opening.content
    assert "J'ai retenu 2 questions pour toi." in opening.content and "passe aux questions" in opening.content
    assert [item["question_fr"] for item in opening.payload["agenda"]] == [CARBURANT, MERCREDI]  # plus pertinente d'abord
    assert opening.payload["questions_dropped"] == 1 and opening.payload["phase"] == "analysis"
    assert session.status == "initial_summary_ready"
    assert db.scalar(select(WrHypothesis).where(WrHypothesis.user_id == user.id)) is not None
    assert conductor.prepare(db, session=session).id == opening.id  # une seule ouverture
    flags = _flags(db, user, session)
    assert (flags.phase, flags.next_step, flags.can_confirm_no_more_input) == ("analysis", "questions", False)

    remark = _chat(db, user, session, "L'analyse me parle.")  # réaction à l'analyse : pas encore de question
    assert remark.content == "Noté." and remark.payload["phase"] == "analysis"
    wrc.advance_weekly_review(db, session_id=session.id, current_user=user)
    first = db.scalars(select(ImperiumWeeklyReviewMessage).where(ImperiumWeeklyReviewMessage.session_id == session.id)
                       .order_by(ImperiumWeeklyReviewMessage.created_at.desc())).first()
    assert first.content == f"Question 1 sur 2 : {CARBURANT}" and first.payload["agenda_index"] == 0
    assert (_flags(db, user, session).phase, _flags(db, user, session).next_step) == ("questions", None)
    with pytest.raises(wrc.WeeklyReviewStateConflictError):
        wrc.advance_weekly_review(db, session_id=session.id, current_user=user)

    second = _chat(db, user, session, "Des trajets à vide.")
    assert second.content == f"Noté. Question 2 sur 2 : {MERCREDI}" and second.payload["agenda_index"] == 1
    assert second.payload["mode"] == "deterministic" and second.role == "backend"
    last = _chat(db, user, session, "Je me suis couché tard.")
    assert last.content == f"Noté. {conductor.READY_TEXT}" and last.payload["phase"] == "ready_for_report"
    flags = _flags(db, user, session)
    assert (flags.next_step, flags.can_confirm_no_more_input, flags.can_send_message) == ("report", True, True)
    conversation = wrc.get_weekly_review_conversation(db, current_user=user, session_id=session.id)
    assert [item.role for item in conversation.chat_timeline][-2:] == ["user", "assistant"]


def _turn(followup=None, value=0, index=-1, wants_report=False, beyond_me=False, open_question=None) -> dict:
    return {"comprehension": "Compris.", "ack_fr": "Je note.", "followup_fr": followup, "followup_value": value,
            "next_index": index, "wants_report": wants_report, "beyond_me": beyond_me, "open_question": open_question}


def test_local_conductor_follows_up_while_it_stays_relevant(db, fakes) -> None:
    user = _user(db)
    session = _launch(db, user)
    _cloud_on(db)
    set_parameter(db, code="ai.local_slot_modes", value={"wr.conversation": "live"}, origin="user", rationale_fr="Test.")
    set_parameter(db, code="wr.followups_max", value=2, origin="user", rationale_fr="Test.")
    db.commit()
    fakes.cloud = [PASS]
    conductor.prepare(db, session=session)
    wrc.advance_weekly_review(db, session_id=session.id, current_user=user)
    fakes.local = [
        _turn("Des trajets à vide, ou un plein plus cher ?", 80, open_question="Pourquoi je dors mal ?"),
        _turn("Combien de litres ?", 30, index=1),  # relance trop peu pertinente : question suivante
        _turn("Couché à quelle heure ?", 90, beyond_me=True),
        _turn("Et la veille ?", 90),
        _turn("Et l'avant-veille ?", 90),  # 2 relances déjà sur ce sujet : on passe, l'agenda est fini
        local_executor.LocalExecutorError("down"),
    ]
    relance = _chat(db, user, session, "Le carburant, bof.")
    assert relance.role == "qwen" and relance.content == "Je note. Des trajets à vide, ou un plein plus cher ?"
    assert relance.payload["agenda_index"] is None and relance.payload["open_question"] == "Pourquoi je dors mal ?"
    prompt = fakes.prompts[0]
    assert f"Semaine revue : du {session.week_start.isoformat()} au {session.week_end.isoformat()}." in prompt
    assert "Phase des questions" in prompt and "La fatigue pèse sur le VTC." in prompt
    assert f"0 : {CARBURANT} (déjà posée ou hors phase)" in prompt and f"1 : {MERCREDI} (à poser)" in prompt
    assert "Carburant +60 %" in prompt
    nxt = _chat(db, user, session, "Un plein plus cher.")
    assert nxt.content == f"Je note. Question 2 sur 2 : {MERCREDI}" and nxt.payload["agenda_index"] == 1
    hard = _chat(db, user, session, "Calcule ma dette de sommeil sur 6 mois.")
    assert hard.payload["needs_bigger_model"] is True and hard.content.endswith("Couché à quelle heure ?")
    _chat(db, user, session, "Tard.")
    done = _chat(db, user, session, "Vers 2 h.")
    assert done.content == f"Je note. {conductor.READY_TEXT}" and done.payload["phase"] == "ready_for_report"
    fallback = _chat(db, user, session, "Autre chose.")  # modèle en panne après les questions : le code accuse réception
    assert fallback.payload["mode"] == "deterministic" and fallback.content == "Noté."
    assert _flags(db, user, session).next_step == "report"


def test_the_user_can_ask_for_the_report_early(db, fakes) -> None:
    user = _user(db)
    session = _launch(db, user)
    _cloud_on(db)
    set_parameter(db, code="ai.local_slot_modes", value={"wr.conversation": "live"}, origin="user", rationale_fr="Test.")
    db.commit()
    fakes.cloud = [PASS]
    conductor.prepare(db, session=session)
    wrc.advance_weekly_review(db, session_id=session.id, current_user=user)
    fakes.local = [_turn("Tu saisis tes courses dans l'outil, ou le système reste vide ?", 80),
                   _turn("As-tu saisi tes courses dans l'outil, ou le système reste-t-il vide ?", 80, index=1),
                   {**_turn(wants_report=True), "ack_fr": "Je note : passage au rapport."}]
    _chat(db, user, session, "Bof.")
    repeated = _chat(db, user, session, "La clim est réparée.")  # relance déjà posée : question suivante
    assert repeated.content == f"Je note. Question 2 sur 2 : {MERCREDI}"
    stop = _chat(db, user, session, "On arrête là, fais le rapport.")
    assert stop.content == conductor.READY_TEXT and _flags(db, user, session).next_step == "report"


def test_cloud_failure_still_opens_the_conversation(db, fakes) -> None:
    user = _user(db)
    session = _launch(db, user)
    _cloud_on(db)
    fakes.cloud = [cloud.CloudError("Cloud CLI exited with 1.")]
    opening = conductor.prepare(db, session=session)
    assert "modèle cloud indisponible" in opening.content and opening.payload["agenda"] == []
    assert opening.payload["error"] and session.status == "initial_summary_ready"
    assert _flags(db, user, session).next_step is None  # rien à rédiger tant qu'il n'a rien dit
    reply = _chat(db, user, session, "Semaine dure.")
    assert reply.content == "Noté." and _flags(db, user, session).next_step == "report"


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
    assert opening.id != failed.id and opening.payload["phase"] == "analysis" and opening.payload["error"] is None
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
