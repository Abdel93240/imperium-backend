from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = BACKEND_ROOT / "docs_master"
STATE_MATRIX_PATH = DOCS_ROOT / "67_FRONTEND_STATE_MATRIX_V1.md"


def _state_matrix_text() -> str:
    return STATE_MATRIX_PATH.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    assert marker in text
    return text.split(marker, maxsplit=1)[1].split("\n## ", maxsplit=1)[0]


def test_imperium_frontend_state_matrix_v1_doc_exists_and_declares_doc_only_scope() -> None:
    text = _state_matrix_text()

    assert STATE_MATRIX_PATH.exists()
    assert "**Statut :** CANONICAL IMPERIUM FRONTEND STATE MATRIX V1" in text
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
    ):
        assert source_doc in text

    assert "07_ANDROID_APP" in text


def test_imperium_frontend_state_matrix_v1_has_required_sections_in_order() -> None:
    text = _state_matrix_text()

    expected_headings = [
        "## 1. Scope",
        "## 2. Screen Routing Canonical IDs",
        "## 3. Dashboard",
        "## 4. Mission Active",
        "## 5. Inbox",
        "## 6. Weekly Review",
        "## 7. History",
        "## 8. Settings",
        "## 9. Global State Rules",
        "## 10. State Validation Checklist",
        "## 11. Readiness Matrix",
    ]

    positions = [text.index(heading) for heading in expected_headings]
    assert positions == sorted(positions)


def test_imperium_frontend_state_matrix_v1_locks_canonical_top_level_routes() -> None:
    routes = _section(_state_matrix_text(), "2. Screen Routing Canonical IDs")

    for screen, screen_id, route_id, path in (
        ("Dashboard", "IMP-01", "IMP.DASH.MAIN", "imperium/dashboard"),
        ("Mission Active", "IMP-02", "IMP.MISSION.ACTIVE", "imperium/missions/active"),
        ("Inbox", "IMP-03", "IMP.INBOX.MAIN", "imperium/inbox"),
        ("Weekly Review", "IMP-04", "IMP.WR.SUMMARY", "imperium/weekly-review"),
        ("History", "IMP-05", "IMP.HISTORY.MAIN", "imperium/history"),
        ("Settings", "IMP-06", "IMP.SETTINGS.CORE", "imperium/settings"),
    ):
        assert f"| {screen} | `{screen_id}` | `{route_id}` | `{path}` | Yes |" in routes

    assert "IMP.MISSION.DETAIL" not in routes


@pytest.mark.parametrize(
    (
        "heading",
        "route_id",
        "title",
        "screen_id",
        "required_components",
        "required_message",
    ),
    [
        (
            "3. Dashboard",
            "IMP.DASH.MAIN",
            "Imperium",
            "IMP-01",
            (
                "Daily Focus card",
                "Active Mission card",
                "Priority card",
                "Quick Actions",
                "Weekly Progress",
                "SyncStateChip",
            ),
            "Tu dois savoir quoi faire maintenant.",
        ),
        (
            "4. Mission Active",
            "IMP.MISSION.ACTIVE",
            "Mission Active",
            "IMP-02",
            (
                "Mission header",
                "description",
                "progress block",
                "decision buttons",
                "notes area",
                "sync chip",
            ),
            "Une seule mission active doit rester visible.",
        ),
        (
            "5. Inbox",
            "IMP.INBOX.MAIN",
            "Inbox",
            "IMP-03",
            (
                "Search field",
                "filter chips",
                "list items",
                "preview panel",
                "sync chip",
            ),
            "Capture rapide, tri rapide, lecture rapide.",
        ),
        (
            "6. Weekly Review",
            "IMP.WR.SUMMARY",
            "Weekly Review",
            "IMP-04",
            (
                "Summary card",
                "wins block",
                "failures block",
                "recommendation card",
                "statistics panel",
                "sync chip",
            ),
            "La semaine est lisible et exploitable.",
        ),
        (
            "7. History",
            "IMP.HISTORY.MAIN",
            "History",
            "IMP-05",
            (
                "Timeline",
                "filters",
                "search field",
                "detail panel",
                "sync chip",
            ),
            "L historique est pret.",
        ),
        (
            "8. Settings",
            "IMP.SETTINGS.CORE",
            "Settings",
            "IMP-06",
            (
                "Section list",
                "preference cards",
                "sync chip",
            ),
            "Les preferences sont disponibles.",
        ),
    ],
)
def test_imperium_frontend_state_matrix_v1_locks_each_screen_state_matrix(
    heading: str,
    route_id: str,
    title: str,
    screen_id: str,
    required_components: tuple[str, ...],
    required_message: str,
) -> None:
    screen = _section(_state_matrix_text(), heading)

    assert f"Screen ID | `{screen_id}`" in screen
    assert f"Route ID | `{route_id}`" in screen
    assert f"Title | `{title}`" in screen

    for state_label in (
        "Ready state",
        "Loading state",
        "Empty state",
        "Error state",
        "Offline state",
        "Partial sync state",
    ):
        assert state_label in screen

    for required_column in (
        "User actions allowed",
        "Visible components",
        "Expected user message",
        "Transition vers autres etats",
    ):
        assert required_column in screen

    for required_component in required_components:
        assert required_component in screen

    assert required_message in screen


def test_imperium_frontend_state_matrix_v1_locks_global_state_rules() -> None:
    rules = _section(_state_matrix_text(), "9. Global State Rules")

    for required in (
        "Loading jamais vide",
        "Error toujours actionnable",
        "Empty state toujours explicatif",
        "Offline state toujours visible",
        "Aucune action destructive sans confirmation",
        "Aucune ecran ne doit inventer une mission active locale",
        "Aucune mission active concurrente",
        "Un cache ne doit jamais etre presente comme une verite live",
        "Un etat partiellement sync doit montrer ce qui est deja valide",
    ):
        assert required in rules


def test_imperium_frontend_state_matrix_v1_locks_empty_state_ctas() -> None:
    weekly = _section(_state_matrix_text(), "6. Weekly Review")
    settings = _section(_state_matrix_text(), "8. Settings")

    assert "CTA `Back to Dashboard`" in weekly
    assert "CTA `Use mock defaults`" in settings


def test_imperium_frontend_state_matrix_v1_locks_checklist_and_readiness_matrix() -> None:
    checklist = _section(_state_matrix_text(), "10. State Validation Checklist")
    readiness = _section(_state_matrix_text(), "11. Readiness Matrix")

    for required in (
        "Les 6 ecrans sont decrits",
        "Chaque ecran declare Ready state",
        "Chaque ecran declare Loading state",
        "Chaque ecran declare Empty state",
        "Chaque ecran declare Error state",
        "Chaque ecran declare Offline state",
        "Partial sync state est documente quand utile",
        "Aucun backend branche",
        "Aucun endpoint ajoute",
        "Aucun Kotlin",
        "Aucun Android runtime",
        "Cohérence preservee avec 63, 64, 65 et 66",
    ):
        assert required in checklist or required.lower() in checklist.lower()

    for readiness_row in (
        "| Dashboard | READY |",
        "| Mission Active | READY |",
        "| Inbox | READY |",
        "| Weekly Review | READY |",
        "| History | READY |",
        "| Settings | READY |",
    ):
        assert readiness_row in readiness
