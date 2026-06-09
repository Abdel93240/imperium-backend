from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs_master"
SCREEN_SPEC_PATH = DOCS_ROOT / "65_IMPERIUM_FRONTEND_SCREEN_SPEC_V1.md"
COMPONENT_CATALOG_PATH = DOCS_ROOT / "62_DESIGN_SYSTEM_COMPONENT_CATALOG.md"


def _screen_spec_text() -> str:
    return SCREEN_SPEC_PATH.read_text(encoding="utf-8")


def _component_catalog_text() -> str:
    return COMPONENT_CATALOG_PATH.read_text(encoding="utf-8")


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
        "## 4. Mission Active Dashboard Module",
        "## 5. Weekly Review Dashboard Event Surfaces",
        "## 6. Operations Screen",
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
        "ImperiumOfflineState",
        "ImperiumKpiBlock",
    ):
        assert required in rules

    assert "KPIBlock" not in rules


def test_imperium_frontend_screen_spec_v1_allowed_foundation_components_exist_in_62() -> None:
    rules = _section(_screen_spec_text(), "2. Regles globales")
    catalog = _component_catalog_text()

    allowed_block = rules.split("### 2.3 Composants autorises", maxsplit=1)[1].split(
        "### 2.4 Layout global",
        maxsplit=1,
    )[0]
    component_names = set()
    for raw_line in allowed_block.splitlines():
        if not raw_line.startswith("|") or "`" not in raw_line:
            continue
        component_names.update(part for index, part in enumerate(raw_line.split("`")) if index % 2 == 1)

    composite_components = {"MissionFocusCard", "ChatMessageBubble"}
    for component_name in sorted(component_names - composite_components):
        assert component_name in catalog


@pytest.mark.parametrize(
    ("heading", "route_id", "route_path", "required_widgets"),
    [
        (
            "3. Dashboard Screen",
            "IMP.DASH.MAIN",
            "imperium/dashboard",
            (
                "Daily Focus Card",
                "Active Mission Card",
                "Priority Card",
                "Quick Actions",
                "Weekly Progress",
                "Imperium Status",
            ),
        ),
        (
            "6. Operations Screen",
            "IMP.OPERATIONS.MAIN",
            "imperium/operations",
            (
                "71_IMPERIUM_OPERATIONS_TAB.md",
                "projets + routines",
            ),
        ),
        (
            "7. History Screen",
            "IMP.HISTORY.MAIN",
            "imperium/history",
            (
                "Timeline",
                "Search",
                "Filters",
                "History Detail Card",
            ),
        ),
        (
            "8. Settings Screen",
            "IMP.SETTINGS.CORE",
            "imperium/settings",
            (
                "User",
                "Theme",
                "Notifications",
                "Integrations",
                "Security",
                "Advanced",
            ),
        ),
    ],
)
def test_imperium_frontend_screen_spec_v1_locks_each_screen_route_and_widgets(
    heading: str,
    route_id: str,
    route_path: str,
    required_widgets: tuple[str, ...],
) -> None:
    screen = _screen_section(_screen_spec_text(), heading)

    assert f"Route ID | `{route_id}`" in screen
    assert f"Route path | `{route_path}`" in screen
    if route_id != "IMP.OPERATIONS.MAIN":
        assert "Loading" in screen
        assert "Empty" in screen
        assert "Error" in screen

    for widget in required_widgets:
        assert widget in screen


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
        '"fixture_name": "dashboard_mock_v1"',
        '"route_id": "IMP.DASH.MAIN"',
        '"quick_actions"',
        '"target_route": "IMP.CHAT.CONVERSATION"',
        "Loading state",
        "Empty state",
        "Error state",
        "GET /api/imperium/dashboard",
        "Definition of Done",
    ):
        assert required in dashboard


def test_imperium_frontend_screen_spec_v1_mission_active_module_is_fully_specified() -> None:
    mission = _screen_section(_screen_spec_text(), "4. Mission Active Dashboard Module")

    for required in (
        "Route ID | `IMP.MISSION.ACTIVE`",
        "Type | Dashboard module + quick access surface, not top-level route",
        "Ce choix applique l'audit 99",
        "Mission Header",
        "Mission Description",
        "Progress Block",
        "Decision Buttons",
        "Notes Area",
        '"fixture_name": "mission_active_mock_v1"',
        '"route_id": "IMP.MISSION.ACTIVE"',
        "note_save_state",
        "GET /api/imperium/missions/active",
        "POST /api/imperium/missions/{mission_id}/complete",
        "POST /api/imperium/missions/{mission_id}/fail",
        "FUTURE TBD POST /api/imperium/replans/request",
        "DoD",
    ):
        assert required in mission

    assert "IMP.MISSION.DETAIL" not in mission


def test_imperium_frontend_screen_spec_v1_weekly_review_is_dashboard_event_surface() -> None:
    weekly = _screen_section(_screen_spec_text(), "5. Weekly Review Dashboard Event Surfaces")

    for required in (
        "La Weekly Review n'est pas un ecran top-level Imperium V1",
        "`IMP.WR.LIST`",
        "`IMP.WR.READ_ONLY`",
        "`IMP.WR.INTERACTIVE`",
        "ne doit pas etre invente ici",
    ):
        assert required in weekly

    assert "IMP.WR.SUMMARY" not in weekly


def test_imperium_frontend_screen_spec_v1_operations_top_level_is_registered_by_reference() -> None:
    operations = _screen_section(_screen_spec_text(), "6. Operations Screen")

    for required in (
        "Route ID | `IMP.OPERATIONS.MAIN`",
        "Route path | `imperium/operations`",
        "Titre visible | `Operations`",
        "Type | Top-level route",
        "Nom provisoire",
        "71_IMPERIUM_OPERATIONS_TAB.md",
        "ne la recopie pas",
    ):
        assert required in operations


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
        '"fixture_name": "history_mock_v1"',
        '"source"',
        '"linked_route"',
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
        '"fixture_name": "settings_mock_v1"',
        "GET /api/imperium/frontend/app-manifest",
        "TBD PATCH /api/imperium/settings",
        "DoD",
    ):
        assert required in settings


def test_imperium_frontend_screen_spec_v1_locks_navigation_contract() -> None:
    navigation = _section(_screen_spec_text(), "9. Navigation Contract")

    expected_routes = (
        "`IMP.DASH.MAIN`",
        "`IMP.OPERATIONS.MAIN`",
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
        "Telephone GO 65 bottom navigation contains exactly four visible top-level items",
        "Tablet GO 65 sidebar contains exactly four visible top-level items",
        "| 2 | Operations | `IMP.OPERATIONS.MAIN` |",
        "No other deep link is allowed in GO 65",
    ):
        assert required in navigation

    assert "IMP.MISSION.DETAIL" not in navigation
    assert "IMP.INBOX.MAIN" not in navigation
    assert "IMP.WR.SUMMARY" not in navigation


def test_imperium_frontend_screen_spec_v1_locks_route_ids_and_four_item_nav() -> None:
    text = _screen_spec_text()
    expected = (
        ("3. Dashboard Screen", "IMP.DASH.MAIN"),
        ("4. Mission Active Dashboard Module", "IMP.MISSION.ACTIVE"),
        ("6. Operations Screen", "IMP.OPERATIONS.MAIN"),
        ("7. History Screen", "IMP.HISTORY.MAIN"),
        ("8. Settings Screen", "IMP.SETTINGS.CORE"),
    )

    for heading_name, route_id in expected:
        screen = _screen_section(text, heading_name)
        assert f"Route ID | `{route_id}`" in screen
        assert "Screen ID source" not in screen

    navigation = _section(text, "9. Navigation Contract")
    for label, route_id in (
        ("Dashboard", "IMP.DASH.MAIN"),
        ("Operations", "IMP.OPERATIONS.MAIN"),
        ("History", "IMP.HISTORY.MAIN"),
        ("Settings", "IMP.SETTINGS.CORE"),
    ):
        assert f"| {label} | `{route_id}` |" in navigation

    for order, label, route_id in (
        (1, "Dashboard", "IMP.DASH.MAIN"),
        (2, "Operations", "IMP.OPERATIONS.MAIN"),
        (3, "History", "IMP.HISTORY.MAIN"),
        (4, "Settings", "IMP.SETTINGS.CORE"),
    ):
        assert f"| {order} | {label} | `{route_id}`" in navigation

    assert "IMP-" not in text
    assert "IMP.INBOX.MAIN" not in text
    assert "IMP.WR.SUMMARY" not in text


def test_frontend_foundation_docs_v1_remove_mission_detail_and_legacy_fixture_names() -> None:
    forbidden_terms = (
        "IMP.MISSION.DETAIL",
        "dashboard_with_active_mission",
        "mission_active_with_progress",
        "inbox_with_conversations",
        "weekly_review_ready",
        "history_with_timeline",
        "settings_default_mock",
    )

    for doc_number in range(62, 70):
        matches = sorted(DOCS_ROOT.glob(f"{doc_number}_*.md"))
        assert matches, f"missing docs_master/{doc_number}_*.md"
        for path in matches:
            text = path.read_text(encoding="utf-8")
            for forbidden_term in forbidden_terms:
                assert forbidden_term not in text, f"{forbidden_term} found in {path.name}"


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
        '"screen": "IMP.OPERATIONS.MAIN"',
        '"screen": "IMP.MISSION.ACTIVE"',
        '"screen": "IMP.HISTORY.MAIN"',
        '"screen": "IMP.SETTINGS.CORE"',
        '"sync_state": "mock"',
    ):
        assert fixture in mocks

    assert '"screen_id"' not in mocks
    assert "IMP.INBOX.MAIN" not in mocks
    assert "IMP.WR.SUMMARY" not in mocks


def test_imperium_frontend_screen_spec_v1_locks_screen_validation_checklist() -> None:
    checklist = _section(_screen_spec_text(), "11. Screen Validation Checklist")

    for required in (
        "Detailed Screen Checklist",
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
        "Mission Active must remain a Dashboard module or quick access surface",
        "Chatbot must remain `IMP.CHAT.CONVERSATION`, docked from Dashboard",
        "Weekly Review must remain a Dashboard banner/event window and must never finalize locally",
        "Operations must remain the provisional top-level route `IMP.OPERATIONS.MAIN`",
        "History must remain read-only",
        "Settings must never expose secrets",
        "Canonical Definition of Done Checklist",
        "UI validée",
        "Navigation validée",
        "Responsive validé",
        "Loading validé",
        "Empty validé",
        "Error validé",
        "Mock data validée",
        "does not authorize Kotlin generation",
        "Android runtime setup",
        "backend wiring",
        "endpoint creation",
        "model changes",
        "schema changes",
        "API contract changes",
    ):
        assert required in checklist
