from pathlib import Path
import json
import re

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = BACKEND_ROOT / "docs_master"
MOCK_CATALOG_PATH = DOCS_ROOT / "68_FRONTEND_MOCK_DATA_CATALOG_V1.md"


def _mock_catalog_text() -> str:
    return MOCK_CATALOG_PATH.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    assert marker in text
    return text.split(marker, maxsplit=1)[1].split("\n## ", maxsplit=1)[0]


def _json_block(section: str) -> dict:
    match = re.search(r"```json\n(.*?)\n```", section, flags=re.S)
    assert match is not None
    return json.loads(match.group(1))


def test_imperium_frontend_mock_data_catalog_v1_doc_exists_and_declares_doc_only_scope() -> None:
    text = _mock_catalog_text()

    assert MOCK_CATALOG_PATH.exists()
    assert "**Statut :** CANONICAL IMPERIUM FRONTEND MOCK DATA CATALOG V1" in text
    assert "documentation only" in text
    assert "aucune API reelle" in text
    assert "aucune donnee utilisateur reelle" in text
    assert "aucun backend branche" in text
    assert "aucun Kotlin" in text
    assert "aucun Android runtime" in text

    for source_doc in (
        "65_IMPERIUM_FRONTEND_SCREEN_SPEC_V1.md",
        "67_FRONTEND_STATE_MATRIX_V1.md",
        "64_FRONTEND_GENERATION_PLAN_V1.md",
        "07_ANDROID_APP_RESPONSIBILITIES.md",
    ):
        assert source_doc in text


def test_imperium_frontend_mock_data_catalog_v1_has_required_sections_in_order() -> None:
    text = _mock_catalog_text()

    expected_headings = [
        "## 1. Global Mock Rules",
        "## 2. Screen Mock Catalog",
        "## 3. Empty/Error/Offline Variants",
        "## 4. Mock Validation Checklist",
        "## 5. Readiness Matrix",
    ]
    positions = [text.index(heading) for heading in expected_headings]
    assert positions == sorted(positions)


@pytest.mark.parametrize(
    ("heading", "mock_object_name", "screen_id", "route_id", "screen_name", "linked_widget"),
    [
        ("2.1 Dashboard", "dashboard_mock_v1", "IMP-01", "IMP.DASH.MAIN", "Dashboard", "Daily Focus Card"),
        ("2.2 Mission Active", "mission_active_mock_v1", "IMP-02", "IMP.MISSION.ACTIVE", "Mission Active", "Mission Header"),
        ("2.3 Inbox", "inbox_mock_v1", "IMP-03", "IMP.INBOX.MAIN", "Inbox", "Conversation List"),
        ("2.4 Weekly Review", "weekly_review_mock_v1", "IMP-04", "IMP.WR.SUMMARY", "Weekly Review", "Weekly Summary"),
        ("2.5 History", "history_mock_v1", "IMP-05", "IMP.HISTORY.MAIN", "History", "Timeline"),
        ("2.6 Settings", "settings_mock_v1", "IMP-06", "IMP.SETTINGS.CORE", "Settings", "User"),
    ],
)
def test_imperium_frontend_mock_data_catalog_v1_locks_each_screen_catalog_entry(
    heading: str,
    mock_object_name: str,
    screen_id: str,
    route_id: str,
    screen_name: str,
    linked_widget: str,
) -> None:
    screen = _section(_mock_catalog_text(), heading)

    assert f"Mock object name | `{mock_object_name}`" in screen
    assert f'"screen_id": "{screen_id}"' in screen
    assert f'"route_id": "{route_id}"' in screen
    assert f'"screen": "{screen_name}"' in screen
    assert linked_widget in screen
    assert "Linked states (67)" in screen
    assert "Linked widgets (65)" in screen
    assert "Required fields" in screen
    assert "Optional fields" in screen
    assert "Variant links" in screen

    payload = _json_block(screen)
    assert payload["screen_id"] == screen_id
    assert payload["route_id"] == route_id
    assert payload["screen"] == screen_name
    assert payload["mock_object_name"] == mock_object_name
    assert payload["sync_state"] == "mock"
    assert "generated_at" in payload


def test_imperium_frontend_mock_data_catalog_v1_locks_json_examples_and_global_rules() -> None:
    text = _mock_catalog_text()
    rules = _section(text, "1. Global Mock Rules")

    for required in (
        "Aucune API reelle",
        "Aucune donnee utilisateur reelle",
        "Chaque mock a un `mock_object_name` stable",
        "Chaque item identifiable utilise un ID stable qui commence par `mock-`",
        "Les dates sont ISO uniquement",
        "Les textes restent courts et mobiles",
        "Les nombres restent coherents entre eux",
        "Aucun email reel",
        "Aucun token",
        "Aucun secret",
        "`sync_state` vaut toujours `mock`",
        "Le dashboard ne montre jamais plus d une mission active",
        "Settings ne montre jamais les internals d authentification",
    ):
        assert required in rules

    for heading in (
        "2.1 Dashboard",
        "2.2 Mission Active",
        "2.3 Inbox",
        "2.4 Weekly Review",
        "2.5 History",
        "2.6 Settings",
    ):
        payload = _json_block(_section(text, heading))
        assert isinstance(payload, dict)
        assert payload["sync_state"] == "mock"
        assert payload["screen_id"].startswith("IMP-0")
        assert payload["route_id"].startswith("IMP.")
        assert payload["mock_object_name"].endswith("_v1")
        assert re.fullmatch(r"20\d{2}-\d{2}-\d{2}T.*Z", payload["generated_at"]) is not None


def test_imperium_frontend_mock_data_catalog_v1_locks_required_mock_fields() -> None:
    text = _mock_catalog_text()

    dashboard = _json_block(_section(text, "2.1 Dashboard"))
    assert dashboard["screen_id"] == "IMP-01"
    assert dashboard["route_id"] == "IMP.DASH.MAIN"
    assert dashboard["mock_object_name"] == "dashboard_mock_v1"
    assert dashboard["quick_actions"]
    for action in dashboard["quick_actions"]:
        assert {"id", "label", "target_route", "style"}.issubset(action)
        assert action["id"].startswith("mock-")

    mission = _json_block(_section(text, "2.2 Mission Active"))
    assert mission["mission"]["description"]
    assert mission["mission"]["expected_outcome"]
    assert {"status", "last_saved_at", "pending_note_id"} == set(mission["note_save_state"])

    weekly = _json_block(_section(text, "2.4 Weekly Review"))
    for suggestion in weekly["improvement_suggestions"]:
        assert suggestion["rationale"]

    history = _json_block(_section(text, "2.5 History"))
    for event in history["events"]:
        assert event["source"]
        assert event["linked_route"]

    for required_field in (
        "`mission.description`",
        "`mission.expected_outcome`",
        "`note_save_state.status`",
        "`improvement_suggestions[].rationale`",
        "`events[].source`",
        "`events[].linked_route`",
    ):
        assert required_field in text


def test_imperium_frontend_mock_data_catalog_v1_locks_variants_and_readiness() -> None:
    variants = _section(_mock_catalog_text(), "3. Empty/Error/Offline Variants")
    checklist = _section(_mock_catalog_text(), "4. Mock Validation Checklist")
    readiness = _section(_mock_catalog_text(), "5. Readiness Matrix")

    for required in (
        "dashboard_empty_v1",
        "dashboard_error_v1",
        "dashboard_offline_v1",
        "mission_active_empty_v1",
        "mission_active_error_v1",
        "mission_active_offline_v1",
        "inbox_empty_v1",
        "inbox_error_v1",
        "inbox_offline_v1",
        "weekly_review_empty_v1",
        "weekly_review_error_v1",
        "weekly_review_offline_v1",
        "history_empty_v1",
        "history_error_v1",
        "history_offline_v1",
        "settings_empty_v1",
        "settings_error_v1",
        "settings_offline_v1",
        "Empty variant",
        "Error variant",
        "Offline variant",
    ):
        assert required in variants

    for required in (
        "The 6 screens are present",
        "Every screen has a stable `mock_object_name`",
        "Every screen has a JSON example",
        "Every screen links to the `67` states",
        "Every screen links to the `65` widgets",
        "Empty, error and offline variants are documented",
        "Readiness is `READY` for every screen",
        "The document stays documentation only",
    ):
        assert required in checklist

    for row in (
        "| Dashboard | READY |",
        "| Mission Active | READY |",
        "| Inbox | READY |",
        "| Weekly Review | READY |",
        "| History | READY |",
        "| Settings | READY |",
    ):
        assert row in readiness
