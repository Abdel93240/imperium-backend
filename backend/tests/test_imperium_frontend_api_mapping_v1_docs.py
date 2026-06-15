from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = BACKEND_ROOT.parent / "docs_master"
API_MAPPING_PATH = DOCS_ROOT / "69_FRONTEND_API_MAPPING_V1.md"


def _api_mapping_text() -> str:
    return API_MAPPING_PATH.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    assert marker in text
    return text.split(marker, maxsplit=1)[1].split("\n## ", maxsplit=1)[0]


def _subsection(text: str, heading: str) -> str:
    marker = f"### {heading}"
    assert marker in text
    return marker + text.split(marker, maxsplit=1)[1].split("\n### ", maxsplit=1)[0]


def test_imperium_frontend_api_mapping_v1_doc_exists_and_declares_doc_only_scope() -> None:
    text = _api_mapping_text()

    assert API_MAPPING_PATH.exists()
    assert "**Statut :** CANONICAL IMPERIUM FRONTEND API MAPPING V1" in text
    assert "documentation only" in text
    assert "aucun backend branche" in text
    assert "aucun endpoint ajoute" in text
    assert "aucun Kotlin" in text
    assert "aucun Android runtime" in text

    for source_doc in (
        "63_FRONTEND_ARCHITECTURE_V1.md",
        "64_FRONTEND_GENERATION_PLAN_V1.md",
        "65_IMPERIUM_FRONTEND_SCREEN_SPEC_V1.md",
        "66_IMPERIUM_USER_FLOWS_V1.md",
        "67_FRONTEND_STATE_MATRIX_V1.md",
        "68_FRONTEND_MOCK_DATA_CATALOG_V1.md",
        "07_ANDROID_APP_RESPONSIBILITIES.md",
    ):
        assert source_doc in text


def test_imperium_frontend_api_mapping_v1_has_required_sections_in_order() -> None:
    text = _api_mapping_text()

    expected_headings = [
        "## 1. Scope",
        "## 2. Global API Mapping Rules",
        "## 3. Screen to API Mapping",
        "## 4. Widget to Data Contract",
        "## 5. Missing Backend Contracts",
        "## 6. Wiring Preconditions",
        "## 7. Validation Checklist",
        "## 8. Readiness Matrix",
    ]

    positions = [text.index(heading) for heading in expected_headings]
    assert positions == sorted(positions)


@pytest.mark.parametrize(
    (
        "heading",
        "screen_id",
        "route_id",
        "mock_source",
        "required_widget",
        "required_endpoint",
    ),
    [
        (
            "3.1 Dashboard",
            "IMP-01",
            "IMP.DASH.MAIN",
            "dashboard_mock_v1",
            "Daily Focus Card",
            "GET /api/imperium/dashboard",
        ),
        (
            "3.2 Mission Active",
            "IMP-02",
            "IMP.MISSION.ACTIVE",
            "mission_active_mock_v1",
            "Mission Header",
            "GET /api/imperium/missions/active",
        ),
        (
            "3.3 Inbox",
            "IMP-03",
            "IMP.INBOX.MAIN",
            "inbox_mock_v1",
            "Conversation List",
            "FUTURE TBD GET /api/imperium/inbox/items",
        ),
        (
            "3.4 Weekly Review",
            "IMP-04",
            "IMP.WR.SUMMARY",
            "weekly_review_mock_v1",
            "Weekly Summary",
            "GET /api/imperium/weekly-review/state",
        ),
        (
            "3.5 History",
            "IMP-05",
            "IMP.HISTORY.MAIN",
            "history_mock_v1",
            "Timeline",
            "GET /api/imperium/missions/history",
        ),
        (
            "3.6 Settings",
            "IMP-06",
            "IMP.SETTINGS.CORE",
            "settings_mock_v1",
            "User",
            "GET /api/imperium/frontend/app-manifest",
        ),
    ],
)
def test_imperium_frontend_api_mapping_v1_locks_each_screen_mapping(
    heading: str,
    screen_id: str,
    route_id: str,
    mock_source: str,
    required_widget: str,
    required_endpoint: str,
) -> None:
    screen = _subsection(_section(_api_mapping_text(), "3. Screen to API Mapping"), heading)

    assert f"Screen ID | `{screen_id}`" in screen
    assert f"Route ID | `{route_id}`" in screen
    assert mock_source in screen
    assert required_widget in screen
    assert required_endpoint in screen
    assert "Ready state" in screen
    assert "No branch now" in screen


def test_imperium_frontend_api_mapping_v1_locks_widget_to_data_contracts() -> None:
    contracts = _section(_api_mapping_text(), "4. Widget to Data Contract")

    for required in (
        "Daily Focus Card",
        "Active Mission Card",
        "Priority Card",
        "Quick Actions",
        "Weekly Progress",
        "Imperium Status",
        "Mission Header",
        "Mission Description",
        "Progress Block",
        "Notes Area",
        "Conversation List",
        "Message Preview",
        "Weekly Summary",
        "Wins",
        "Failures",
        "Improvement Suggestions",
        "Statistics",
        "Timeline",
        "History Detail Card",
        "Settings",
    ):
        assert required in contracts

    for required_field in (
        "daily_focus.label",
        "active_mission.id",
        "priority.label",
        "weekly_progress.completion_percent",
        "quick_actions[].target_route",
        "mission.description",
        "mission.expected_outcome",
        "note_save_state.status",
        "progress.current_step",
        "filters.query",
        "conversations[].latest_message",
        "week.start",
        "wins[].title",
        "improvement_suggestions[].rationale",
        "events[].occurred_at",
        "events[].linked_route",
        "user.display_name",
        "theme.accent",
        "security.auth_state",
        "advanced.priority_rules_link",
    ):
        assert required_field in contracts

    for legacy_mock_name in (
        "dashboard_with_active_mission",
        "mission_active_with_progress",
        "inbox_with_conversations",
        "weekly_review_ready",
        "history_with_timeline",
        "settings_default_mock",
    ):
        assert legacy_mock_name not in contracts


def test_imperium_frontend_api_mapping_v1_locks_missing_backend_contracts_and_no_wiring() -> None:
    missing = _section(_api_mapping_text(), "5. Missing Backend Contracts")
    wiring = _section(_api_mapping_text(), "6. Wiring Preconditions")

    for required in (
        "FUTURE TBD POST /api/imperium/missions/{mission_id}/notes",
        "FUTURE TBD POST /api/imperium/replans/request",
        "FUTURE TBD GET /api/imperium/inbox/items",
        "FUTURE TBD POST /api/imperium/inbox/items",
        "FUTURE TBD GET /api/imperium/inbox/conversations/{conversation_id}",
        "FUTURE TBD POST /api/imperium/inbox/items/{item_id}/convert-to-mission-proposal",
        "FUTURE TBD POST /api/imperium/voice/transcriptions",
        "FUTURE TBD GET /api/imperium/history/events",
        "FUTURE TBD PATCH /api/imperium/settings",
    ):
        assert required in missing

    assert "FUTURE" in missing

    for required in (
        "Aucune mutation canonique ne doit etre branchee",
        "Aucune action `FUTURE` ne doit etre active maintenant",
        "Aucun endpoint ne doit etre cree ou modifie",
        "one active mission",
        "read-only",
    ):
        assert required in wiring


def test_imperium_frontend_api_mapping_v1_locks_readiness_matrix() -> None:
    readiness = _section(_api_mapping_text(), "8. Readiness Matrix")

    for row in (
        "| Dashboard | READY |",
        "| Mission Active | READY |",
        "| Inbox | READY |",
        "| Weekly Review | READY |",
        "| History | READY |",
        "| Settings | READY |",
    ):
        assert row in readiness
