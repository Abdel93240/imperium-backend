from pathlib import Path


DOCS_ROOT = Path(__file__).resolve().parents[2] / "docs_master"


def _doc(name: str) -> str:
    return (DOCS_ROOT / name).read_text(encoding="utf-8")


def test_imperium_and_path_missing_features_are_documented() -> None:
    imperium = _doc("43_IMPERIUM_LOGIC_DETAIL.md")
    path = _doc("41_PATH_LOGIC_DETAIL.md")

    assert "### 12.3 Daily AI advice (dashboard)" in imperium
    assert "MODE IA:" in imperium
    assert "Projets en cours" in imperium
    assert "History screen (read-only consultation)" in imperium
    assert "references the central Knowledge Inbox spec (doc 70)" in imperium

    assert "## 11-bis. Invocations Library, Daily Checklists, And Favorites" in path
    assert "Fixed situations:" in path
    assert "quotidien" in path and "peur_anxiete" in path
    assert "### 11-bis.2 Daily reminder banner" in path
    assert "### 11-bis.3 Invocations du jour" in path
    assert "| PAT-12 | Worship | `PAT.WORSHIP.MAIN` |" in path
    assert "quran_plans:" in path


def test_sadaqa_margin_and_feed_ia_file_policy_are_centralized() -> None:
    path = _doc("41_PATH_LOGIC_DETAIL.md")
    fuel = _doc("46_VECTOR_FUEL_SMART_TRACKING.md")
    inbox = _doc("70_KNOWLEDGE_INBOX.md")

    assert "### 9.5 Safety margin (per user wish)" in path
    assert "user.sadaqa_safety_margin_percent (default: 12.5%)" in path
    assert "## 11. Sadaqa Safety Margin → see doc 41 §9.5" in fuel
    assert "## 11. Sadaqa Safety Margin (Future)" not in fuel

    assert "V1 RULE: accept content files, including AUDIO and VIDEO" in inbox
    assert "Reject by SAFETY, not by media type" in inbox
    assert ".exe, .info" in inbox
    assert "everything EXCEPT video and audio" not in inbox


def test_carrier_engagement_and_expert_orchestration_are_documented() -> None:
    submissions = _doc("53_SUBMISSIONS_OVERLAY_TASKS.md")
    qwen = _doc("35_QWEN_SETUP_AND_PROMPTS.md")
    brain = _doc("44_BRAIN_UNIFIED_LOGIC.md")

    assert "Decisive criterion: ENGAGEMENT." in submissions
    assert "engagement_level VARCHAR(16) NULL" in submissions
    assert "### 12.2 Qwen carrier prompt template" in submissions
    assert "carrier_mission_id = NULL (done standalone)" in submissions
    assert "physical_demand" not in submissions
    assert "Actualiser" not in submissions

    assert "## 9. Carrier Classification Prompt (doc 53)" in qwen
    assert '"engagement_level": <"low" | "medium" | "high">' in qwen

    assert "## 6-bis. Expert-Call Orchestration During Qwen Dialogue" in brain
    assert "Models never call each other directly." in brain
    assert "RAG access to vectorized domain data" in brain
    assert "Qwen must not escalate ordinary low-risk questions" in brain
    assert "Future option: vectorize expert answers during dialogue" in brain


def test_vocab_hierarchy_and_numeric_targets_use_cible() -> None:
    vision = _doc("00_VISION_GLOBALE.md")
    brain = _doc("44_BRAIN_UNIFIED_LOGIC.md")
    f01 = _doc("F01_USER_OBJECTIVES.md")
    submissions = _doc("53_SUBMISSIONS_OVERLAY_TASKS.md")

    assert "Terminology cascade:" in vision
    assert "Projet (what the user wants to build" in vision
    assert "Routine = a recurring mission serving an objective/project." in vision
    assert "daily financial objectives" not in vision
    assert "daily objectives are advisory" not in vision

    assert "## 5-bis. Terminology & Hierarchy" in brain
    assert "PROJET = what the user wants to BUILD." in brain
    assert "OBJECTIF = the translation of a project into the RESULTS" in brain
    assert "ROUTINE = a recurring mission" in brain
    assert "The AI classifies each routine by the objective/project it serves." in brain
    assert "LAYER 1 — INTRINSIC project = ROLE / SYSTEM layer." in brain
    assert "LAYER 2 — EXPLICIT projects = personalized USER-CONTEXT layer." in brain

    assert f01.startswith("# F01 - User Projects Feature (V3)")
    assert "personal projects per\ndomain/category" in f01
    assert "user_projects" in f01
    assert "domain_target" in f01
    assert "objective" not in f01.lower()
    assert "app_target" not in f01

    assert "Cible: 350€" in submissions
    assert "Objectif: 350€" not in submissions
    assert "45_USER_OBJECTIVES_FEATURE" not in submissions
