from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = BACKEND_ROOT / "docs_master"
SCREEN_SPEC_PATH = DOCS_ROOT / "65_IMPERIUM_FRONTEND_SCREEN_SPEC_V1.md"


def _screen_spec_text() -> str:
    return SCREEN_SPEC_PATH.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    assert marker in text
    return text.split(marker, maxsplit=1)[1].split("\n## ", maxsplit=1)[0]


def _screen_section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    assert marker in text
    return text.split(marker, maxsplit=1)[1].split("\n## ", maxsplit=1)[0]


def test_imperium_frontend_screen_spec_v1_doc_exists_and_declares_doc_only_scope() -> None:
    text = _screen_spec_text()

    assert SCREEN_SPEC_PATH.exists()
    assert "**Statut :** CANONICAL IMPERIUM FRONTEND SCREEN SPEC V1" in text
    assert "documentation only" in text
    assert "aucun Kotlin" in text
    assert "aucun dossier `android/`" in text
    assert "aucun runtime frontend" in text
    assert "aucun backend branche" in text
    assert "aucune API reelle" in text

    for source_doc in (
        "59_DESIGN_SYSTEM_V1_DRAFT.md",
        "60_DESIGN_SYSTEM_TOKENS_KT.md",
        "61_DESIGN_SYSTEM_COMPOSITE_COMPONENTS.md",
        "62_DESIGN_SYSTEM_COMPONENT_CATALOG.md",
        "63_FRONTEND_ARCHITECTURE_V1.md",
        "64_FRONTEND_GENERATION_PLAN_V1.md",
    ):
        assert source_doc in text


def test_imperium_frontend_screen_spec_v1_has_required_sections_in_order() -> None:
    text = _screen_spec_text()

    expected_headings = [
        "## 1. Mission du document",
        "## 2. Regles globales",
        "## 3. Dashboard Screen",
        "## 4. Mission Active Screen",
        "## 5. Inbox Screen",
        "## 6. Weekly Review Screen",
        "## 7. History Screen",
        "## 8. Settings Screen",
        "## 9. Navigation Contract",
        "## 10. Mock Data Contract",
        "## 11. Screen Validation Checklist",
    ]

    positions = [text.index(heading) for heading in expected_headings]
    assert positions == sorted(positions)


def test_imperium_frontend_screen_spec_v1_locks_global_rules_and_allowed_components() -> None:
    rules = _section(_screen_spec_text(), "2. Regles globales")

    for required in (
        "Respecter strictement",
        "Aucun ecran invente",
        "Aucun widget invente",
        "Aucune navigation inventee",
        "Aucun backend branche",
        "Aucune logique metier inventee",
        "Aucune decision locale canonique",
        "Aucune deuxieme mission active",
        "ImperiumTopBar",
        "ImperiumSidebar",
        "ImperiumBottomNavigation",
        "MissionFocusCard",
        "ChatMessageBubble",
        "ImperiumTimeline",
    ):
        assert required in rules


def test_imperium_frontend_screen_spec_v1_dashboard_screen_is_fully_specified() -> None:
    dashboard = _screen_section(_screen_spec_text(), "3. Dashboard Screen")

    for required in (
        "Route ID | `IMP.DASH.MAIN`",
        "Titre visible | `Imperium`",
        "Objectif metier",
        "Layout tablette",
        "Layout telephone",
        "Daily Focus Card",
        "Active Mission Card",
        "Priority Card",
        "Quick Actions",
        "Weekly Progress",
        "Imperium Status",
        '"fixture_name": "dashboard_with_active_mission"',
        "Loading state",
        "Empty state",
        "Error state",
        "GET /api/imperium/dashboard",
        "Definition of Done",
    ):
        assert required in dashboard


def test_imperium_frontend_screen_spec_v1_mission_active_screen_is_fully_specified() -> None:
    mission = _screen_section(_screen_spec_text(), "4. Mission Active Screen")

    for required in (
        "Route ID | `IMP.MISSION.ACTIVE`",
        "Related canonical deep link | `IMP.MISSION.DETAIL`",
        "not top-level navigation",
        "Mission Header",
        "Mission Description",
        "Progress Block",
        "Decision Buttons",
        "Notes Area",
        '"fixture_name": "mission_active_with_progress"',
        "GET /api/imperium/missions/active",
        "POST /api/imperium/missions/{mission_id}/complete",
        "POST /api/imperium/missions/{mission_id}/fail",
        "DoD",
    ):
        assert required in mission


def test_imperium_frontend_screen_spec_v1_inbox_screen_is_fully_specified() -> None:
    inbox = _screen_section(_screen_spec_text(), "5. Inbox Screen")

    for required in (
        "Route ID | `IMP.INBOX.MAIN`",
        "Conversation List",
        "Message Preview",
        "Filters",
        "Search",
        "Convert to mission",
        "never active directly",
        '"fixture_name": "inbox_with_conversations"',
        "TBD GET /api/imperium/inbox/items",
        "TBD POST /api/imperium/inbox/items/{item_id}/convert-to-mission-proposal",
        "DoD",
    ):
        assert required in inbox


def test_imperium_frontend_screen_spec_v1_weekly_review_screen_is_fully_specified() -> None:
    weekly = _screen_section(_screen_spec_text(), "6. Weekly Review Screen")

    for required in (
        "Route ID | `IMP.WR.SUMMARY`",
        "Weekly Summary",
        "Wins",
        "Failures",
        "Improvement Suggestions",
        "Statistics",
        "Start interactive review",
        "never locale",
        '"fixture_name": "weekly_review_ready"',
        "GET /api/imperium/weekly-review/state",
        "POST /api/imperium/weekly-review/launch",
        "DoD",
    ):
        assert required in weekly


def test_imperium_frontend_screen_spec_v1_history_screen_is_fully_specified() -> None:
    history = _screen_section(_screen_spec_text(), "7. History Screen")

    for required in (
        "Route ID | `IMP.HISTORY.MAIN`",
        "Related canonical route | `IMP.PLAN.HISTORY`",
        "Timeline",
        "Search",
        "Filters",
        "History Detail Card",
        "read-only",
        '"fixture_name": "history_with_timeline"',
        "GET /api/imperium/missions/history",
        "TBD GET /api/imperium/history/events",
        "DoD",
    ):
        assert required in history


def test_imperium_frontend_screen_spec_v1_settings_screen_is_fully_specified() -> None:
    settings = _screen_section(_screen_spec_text(), "8. Settings Screen")

    for required in (
        "Route ID | `IMP.SETTINGS.CORE`",
        "User",
        "Theme",
        "Notifications",
        "Integrations",
        "Security",
        "Advanced",
        "Security ne montre aucun token",
        '"fixture_name": "settings_default_mock"',
        "GET /api/imperium/frontend/app-manifest",
        "TBD PATCH /api/imperium/settings",
        "DoD",
    ):
        assert required in settings


def test_imperium_frontend_screen_spec_v1_locks_navigation_contract() -> None:
    navigation = _section(_screen_spec_text(), "9. Navigation Contract")

    expected_routes = (
        "`IMP.DASH.MAIN`",
        "`IMP.MISSION.ACTIVE`",
        "`IMP.INBOX.MAIN`",
        "`IMP.WR.SUMMARY`",
        "`IMP.HISTORY.MAIN`",
        "`IMP.SETTINGS.CORE`",
    )
    for route_id in expected_routes:
        assert route_id in navigation

    for required in (
        "Bottom Navigation",
        "Top Bar",
        "Back Navigation",
        "Deep Links",
        "Stable Route IDs",
        "Telephone GO 65 bottom navigation contains exactly five visible items",
        "Tablet GO 65 sidebar contains exactly six visible items",
        "`IMP.MISSION.ACTIVE` is never shown as a bottom navigation item",
        "No other deep link is allowed in GO 65",
    ):
        assert required in navigation


def test_imperium_frontend_screen_spec_v1_locks_mock_data_contract_for_all_screens() -> None:
    mocks = _section(_screen_spec_text(), "10. Mock Data Contract")

    for forbidden_backend_use in (
        "no real API",
        "no backend",
        "no n8n",
        "no PostgreSQL",
        "no pgvector",
        "no canonical AI decision",
    ):
        assert forbidden_backend_use in mocks

    for fixture in (
        '"screen": "IMP.DASH.MAIN"',
        '"screen": "IMP.MISSION.ACTIVE"',
        '"screen": "IMP.INBOX.MAIN"',
        '"screen": "IMP.WR.SUMMARY"',
        '"screen": "IMP.HISTORY.MAIN"',
        '"screen": "IMP.SETTINGS.CORE"',
        '"sync_state": "mock"',
    ):
        assert fixture in mocks


def test_imperium_frontend_screen_spec_v1_locks_screen_validation_checklist() -> None:
    checklist = _section(_screen_spec_text(), "11. Screen Validation Checklist")

    for required in (
        "Responsive tablette",
        "Responsive telephone",
        "Design System conforme",
        "Component Catalog conforme",
        "Navigation conforme",
        "Loading state",
        "Empty state",
        "Error state",
        "Mock data fonctionnelle",
        "Dashboard must show no more than one active mission",
        "Mission Active must never be top-level bottom navigation",
        "Inbox convert-to-mission action must remain backend-validated",
        "Weekly Review must never finalize locally",
        "History must remain read-only",
        "Settings must never expose secrets",
    ):
        assert required in checklist
