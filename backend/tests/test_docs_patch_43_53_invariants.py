from pathlib import Path


DOCS_ROOT = Path(__file__).resolve().parents[2] / "docs_master"
REPO_ROOT = DOCS_ROOT.parent


def _doc(name: str) -> str:
    return (DOCS_ROOT / name).read_text(encoding="utf-8")


def _day_start_decision() -> str:
    return (REPO_ROOT / "gap_analysis_v1" / "DECISION_demarrage_journee.md").read_text(
        encoding="utf-8"
    )


def test_doc_43_chatbot_decisions_are_challenged_before_recording() -> None:
    text = _doc("43_IMPERIUM_LOGIC_DETAIL.md")
    section = text.split("### 8.3 Decision-to-action flow", maxsplit=1)[1].split("---", maxsplit=1)[0]

    assert "CONSTRUCTIVE CRITIC" in section
    assert "Before recording\nor applying a decision, it CHALLENGES it" in section
    assert 'backend creates a "user_decision" record (the INFORMED decision)' in section
    assert "OK. Veux-tu que je note cette décision et l'applique ?" not in section


def test_doc_43_morning_popup_and_parallel_mission_rules_match_canonical_model() -> None:
    text = _doc("43_IMPERIUM_LOGIC_DETAIL.md")
    decision = _day_start_decision()

    assert 'Triggered when the user presses "commencer la journée" (start day).' in text
    assert "NOT a clock-\ntime/wake-time trigger and NOT merely first app open" in text
    assert '"Comment tu te sens aujourd\'hui ?"' in text
    assert "ressenti subjectif: échelle courte" in text
    assert "The morning check-in is not a replan by default." in text
    assert "sleep_hours: number input" not in text
    assert "pain or limitation: optional text" not in text
    assert "mood: optional emoji" not in text
    assert "special context: optional text" not in text
    assert "Pain or health changes are not\nasked here" in text
    assert "declared during the day through the chatbot" in text
    assert "only\ncause a proposed replan after user agreement" in text
    assert "health.entry.logged" in decision
    assert "Jamais de réorganisation sans accord." in decision
    assert "Check-in : UNE seule question, le ressenti subjectif" in decision
    assert "Pas de question au check-in." in decision
    assert 'Clic explicite "Démarrer la journée".' in decision
    assert "Chatbot: explicit user request (re-plan, or a decision raised in chat)" in text
    assert "mission_type (urgente | importante | secondaire)   -- PRIORITY level" in text
    assert "### 5.3 Main mission + parallel annex missions (see doc 53)" in text
    assert 'Front-end (FR): "mission principale" / "mission annexe".' in text
    assert "très_importante" not in text
