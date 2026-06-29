from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "gap_analysis_v1" / "DECISIONS_vector_discussion.md"


def test_vector_discussion_decisions_doc_exists_and_locks_key_scope() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")

    assert DOC_PATH.exists()
    assert "Vector / VTC — Décisions de discussion" in text
    assert "Date : 2026-06-29" in text
    assert "Statut : décisions de fond AVANT gap analysis Vector" in text
    assert "CatBoost regression" in text
    assert "TOURNE SUR CPU" in text
    assert "TOUT sur le VPS" in text
    assert "Valhalla local sur VPS" in text
    assert "Trigger = son unique de l'appli VTC" in text
    assert "TEMPS 1 — CONTEXTE PERMANENT" in text
    assert "TEMPS 2 — EXTRACTION COURSE" in text
    assert "TEMPS 3 — CROISEMENT" in text
    assert "RÉCURRENCE × IMPACT" in text
    assert "confounding" in text


def test_vector_discussion_doc_keeps_gap_analysis_choice_and_excludes_wrong_versioning_rule() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")

    assert "Le gap classique a été\nÉCARTÉ pour Vector" in text
    assert "la DIFFICULTÉ TECHNIQUE" in text
    assert "Complexe mais vital = V1 malgré tout." in text
    assert "API Google/TomTom en temps réel = EXCLU" in text
    assert "Accessibility Service supposé bloqué (FLAG_SECURE)" in text
    assert "La Tour (GPU) ne porte QUE l'IA" in text
