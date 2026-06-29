from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "gap_analysis_v1" / "00_INDEX.md"


def test_gap_analysis_index_marks_vector_vtc_as_suspended_and_redirects_to_dedicated_discussion() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")

    assert DOC_PATH.exists()
    assert "Vector / VTC : SUSPENDU" in text
    assert "matrice des variables métier (récurrence × impact)" in text
    assert "gap_analysis_v1/DECISIONS_vector_discussion.md" in text
    assert "classement V1/V2 des features est à refaire sur le bon critère" in text
