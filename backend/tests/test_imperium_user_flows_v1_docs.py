from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = BACKEND_ROOT / "docs_master"
USER_FLOWS_PATH = DOCS_ROOT / "66_IMPERIUM_USER_FLOWS_V1.md"


def _user_flows_text() -> str:
    return USER_FLOWS_PATH.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    assert marker in text
    return text.split(marker, maxsplit=1)[1].split("\n## ", maxsplit=1)[0]


def test_imperium_user_flows_v1_doc_exists_and_declares_doc_only_scope() -> None:
    text = _user_flows_text()

    assert USER_FLOWS_PATH.exists()
    assert "**Statut :** CANONICAL IMPERIUM USER FLOWS V1" in text
    assert "documentation only" in text
    assert "aucun runtime" in text
    assert "aucun backend" in text
    assert "aucun Android" in text
    assert "65_IMPERIUM_FRONTEND_SCREEN_SPEC_V1.md" in text


def test_imperium_user_flows_v1_has_required_sections_in_order() -> None:
    text = _user_flows_text()

    expected_headings = [
        "## 1. Scope",
        "## 2. Dashboard Flows",
        "## 3. Mission Active Flows",
        "## 4. Inbox Flows",
        "## 5. Weekly Review Flows",
        "## 6. History Flows",
        "## 7. Settings Flows",
        "## 8. Navigation Contract",
        "## 9. Forbidden Flows",
        "## 10. Flow Validation Checklist",
        "## 11. Readiness",
    ]

    positions = [text.index(heading) for heading in expected_headings]
    assert positions == sorted(positions)


def test_imperium_user_flows_v1_locks_dashboard_and_mission_transitions() -> None:
    dashboard = _section(_user_flows_text(), "2. Dashboard Flows")
    mission = _section(_user_flows_text(), "3. Mission Active Flows")

    for required in (
        "Open app",
        "Consult active mission",
        "Access inbox",
        "Access history",
        "Access settings",
        "Access weekly review",
        "APP_LAUNCH",
        "IMP.DASH.MAIN",
        "IMP.MISSION.ACTIVE",
        "IMP.INBOX.MAIN",
        "IMP.HISTORY.MAIN",
        "IMP.SETTINGS.CORE",
        "IMP.WR.SUMMARY",
        "Une seule mission active",
    ):
        assert required in dashboard

    for required in (
        "See mission",
        "Modify status",
        "Add note",
        "Return dashboard",
        "complete, fail, replan",
        "seule mission active",
    ):
        assert required in mission

    assert "IMP.MISSION.DETAIL" not in mission


def test_imperium_user_flows_v1_locks_inbox_weekly_history_and_settings_flows() -> None:
    inbox = _section(_user_flows_text(), "4. Inbox Flows")
    weekly = _section(_user_flows_text(), "5. Weekly Review Flows")
    history = _section(_user_flows_text(), "6. History Flows")
    settings = _section(_user_flows_text(), "7. Settings Flows")

    for required in (
        "Open conversation",
        "Search",
        "Filter",
        "Return dashboard",
        "IMP.INBOX.MAIN",
        "ne cree jamais une mission active",
    ):
        assert required in inbox or required.lower() in inbox.lower()

    for required in (
        "Consult review",
        "View statistics",
        "View recommendations",
        "Return dashboard",
        "IMP.WR.SUMMARY",
        "backend/WR workflow",
    ):
        assert required in weekly

    for required in (
        "Search",
        "Filter",
        "Consultation detail",
        "Return dashboard",
        "read-only",
        "IMP.HISTORY.MAIN",
    ):
        assert required in history

    for required in (
        "Navigation sections",
        "Modification preferences",
        "Return dashboard",
        "IMP.SETTINGS.CORE",
        "ne doit jamais exposer de secrets",
    ):
        assert required in settings or required.lower() in settings.lower()


def test_imperium_user_flows_v1_navigation_contract_locks_routes_and_transitions() -> None:
    contract = _section(_user_flows_text(), "8. Navigation Contract")

    for required in (
        "Start Route",
        "Target Route",
        "Allowed Actions",
        "Exit Conditions",
        "| Open app | `APP_LAUNCH` | `IMP.DASH.MAIN` |",
        "| Consult active mission | `IMP.DASH.MAIN` | `IMP.MISSION.ACTIVE` |",
        "| Access inbox | `IMP.DASH.MAIN` | `IMP.INBOX.MAIN` |",
        "| Access history | `IMP.DASH.MAIN` | `IMP.HISTORY.MAIN` |",
        "| Access settings | `IMP.DASH.MAIN` | `IMP.SETTINGS.CORE` |",
        "| Access weekly review | `IMP.DASH.MAIN` | `IMP.WR.SUMMARY` |",
        "`IMP.WR.READ_ONLY`",
        "`IMP.WR.INTERACTIVE`",
        "`IMP.PLAN.HISTORY`",
        "`IMP.SETTINGS.PRIORITIES`",
    ):
        assert required in contract

    assert "IMP.MISSION.DETAIL" not in contract


def test_imperium_user_flows_v1_locks_forbidden_flows_checklist_and_readiness() -> None:
    forbidden = _section(_user_flows_text(), "9. Forbidden Flows")
    checklist = _section(_user_flows_text(), "10. Flow Validation Checklist")
    readiness = _section(_user_flows_text(), "11. Readiness")

    for required in (
        "Aucune navigation inconnue",
        "Aucun ecran hors spec",
        "Aucun deep link non documente",
        "Aucune destination top-level non declaree dans 65",
        "Aucune creation de mission active concurrente",
    ):
        assert required in forbidden

    for required in (
        "✓ depart defini",
        "✓ arrivee definie",
        "✓ action utilisateur definie",
        "✓ retour defini",
        "✓ coherent avec 65",
    ):
        assert required in checklist

    for required in (
        "| Dashboard | READY |",
        "| Mission | READY |",
        "| Inbox | READY |",
        "| Weekly Review | READY |",
        "| History | READY |",
        "| Settings | READY |",
    ):
        assert required in readiness
