from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs_master"


def _doc(name: str) -> str:
    return (DOCS_ROOT / name).read_text(encoding="utf-8")


def test_design_system_removes_gamified_assets_without_removing_ui_badges() -> None:
    design_system = _doc("59_DESIGN_SYSTEM_V1_DRAFT.md")

    assert "badges de succès rares" not in design_system
    assert "Lottie autorisé uniquement pour milestones" not in design_system
    assert "end-of-day Bilan, milestones" not in design_system
    assert (
        "Emblèmes app, hero d'écrans clés (Morning Check-In, Weekly Review intro, "
        "end-of-day Bilan). Réservés aux moments à charge émotionnelle."
    ) in design_system
    assert (
        "Lottie autorisé uniquement pour les hero d'écrans clés (≤2 par écran)."
    ) in design_system

    assert "**Badge numérique**" in design_system


def test_frontend_widgets_no_longer_document_streak_rewards() -> None:
    design_system = _doc("59_DESIGN_SYSTEM_V1_DRAFT.md")
    composite_components = _doc("61_DESIGN_SYSTEM_COMPOSITE_COMPONENTS.md")

    for removed_phrase in (
        "Discipline streak",
        "weekly streak count",
        "history streak",
        "Count, target, progress, dhikr label, streak.",
    ):
        assert removed_phrase not in design_system
        assert removed_phrase not in composite_components

    assert "- **Widgets :** Next prayer countdown, Pressure score." in design_system
    assert "- **Widgets :** latest WR status chip." in design_system
    assert (
        "- **Widgets :** workout du jour, recovery display, adaptation proposal entry."
    ) in design_system
    assert "Count, target, progress, dhikr label." in composite_components


def test_weekly_review_keeps_ledger_and_removes_trophy_ornament() -> None:
    composite_components = _doc("61_DESIGN_SYSTEM_COMPOSITE_COMPONENTS.md")

    assert "trophy/ledger ornament" not in composite_components
    assert "Premium review frame, ledger ornament." in composite_components


def test_quran_progression_schema_has_no_current_streak_days() -> None:
    path_logic = _doc("41_PATH_LOGIC_DETAIL.md")

    assert "current_streak_days" not in path_logic
    assert (
        "quran_progression table:\n"
        "  user_id (unique), last_validated_page, last_validated_at,\n"
        "  daily_objective"
    ) in path_logic
    assert (
        "  last_validated_page   INTEGER,\n"
        "  last_validated_at     TIMESTAMPTZ,\n"
        "  daily_objective       VARCHAR(64)\n"
        ");"
    ) in path_logic
