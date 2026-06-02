from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = BACKEND_ROOT / "docs_master"
DESIGN_SYSTEM_PATH = DOCS_ROOT / "59_DESIGN_SYSTEM_V1_DRAFT.md"

IMPERIUM_SCREEN_IDS = [f"IMP-{number:02d}" for number in range(1, 15)]
SOURCE_DOCS = [
    "07_ANDROID_APP_RESPONSIBILITIES.md",
    "24_DAY_FINISHED_WORKFLOW.md",
    "26_PRIORITY_RULES_WORKFLOW.md",
    "29_WEEKLY_REPORT_WORKFLOW.md",
    "32_WR_INTERACTIVE_WORKFLOW.md",
    "43_IMPERIUM_LOGIC_DETAIL.md",
]


def _design_system_text() -> str:
    return DESIGN_SYSTEM_PATH.read_text(encoding="utf-8")


def test_imperium_screen_source_docs_are_available_in_audited_docs_master() -> None:
    missing = [doc_name for doc_name in SOURCE_DOCS if not (DOCS_ROOT / doc_name).exists()]

    assert missing == []


def test_design_system_maps_all_14_imperium_screens_with_stable_ids() -> None:
    text = _design_system_text()

    for screen_id in IMPERIUM_SCREEN_IDS:
        assert "### 8." in text
        assert screen_id in text
        assert f"`{screen_id}`" in text

    assert "IMP-10 Weekly Review List" in text
    assert "IMP-11 Weekly Review Read-only View" in text
    assert "IMP-12 Weekly Review Interactive Popup" in text


def test_design_system_declares_screen_types_navigation_and_backend_dependencies() -> None:
    text = _design_system_text()

    for required in (
        "## 8. IMPERIUM SCREEN ARCHITECTURE MAPPING V1",
        "### 8.0 Canonical Routing Typology",
        "### 8.15 Imperium Navigation Graph V1",
        "route",
        "tab",
        "dialog",
        "bottom_sheet",
        "deep_link",
        "/api/imperium/dashboard",
        "/api/imperium/day/finish",
        "/api/imperium/missions/backlog",
        "/api/imperium/missions/history",
        "/api/imperium/weekly-review/history",
        "/api/imperium/weekly-review/current",
        "/api/imperium/decision-framework/priorities",
        "/api/imperium/frontend/app-manifest",
    ):
        assert required in text

    assert "IMP-02 --> IMP-05" in text
    assert "IMP-03 --> IMP-05" in text
    assert "IMP-12 --> IMP-11" in text


def test_design_system_instantiates_states_widgets_assets_and_tablet_layout_per_screen() -> None:
    text = _design_system_text()

    for screen_id in IMPERIUM_SCREEN_IDS:
        section = text.split(f"`{screen_id}`", maxsplit=1)[1].split("\n### 8.", maxsplit=1)[0]
        for required_label in (
            "**Composants :**",
            "**Widgets :**",
            "**Assets :**",
            "**Etats :**",
            "**Backend deps :**",
            "**Navigation :**",
            "**Tab S10 Ultra :**",
        ):
            assert required_label in section

        for state in ("Loading", "Empty", "Error", "Offline", "Syncing", "Synced", "Conflict"):
            assert state in section


def test_design_system_resolves_audit_ambiguities_without_adding_os_personnel_v1() -> None:
    text = _design_system_text()

    assert "Mon OS personnel" in text
    assert "V3" in text
    assert "excluded from V1 navigation" in text
    assert "Mission detail is not IMP-15 in V1" in text
    assert "IMP.MISSION.DETAIL" in text
