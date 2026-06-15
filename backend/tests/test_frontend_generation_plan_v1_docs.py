from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = BACKEND_ROOT.parent / "docs_master"
FRONTEND_GENERATION_PLAN_PATH = DOCS_ROOT / "64_FRONTEND_GENERATION_PLAN_V1.md"


def _generation_plan_text() -> str:
    return FRONTEND_GENERATION_PLAN_PATH.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    assert marker in text
    return text.split(marker, maxsplit=1)[1].split("\n## ", maxsplit=1)[0]


def test_frontend_generation_plan_v1_doc_exists_and_declares_doc_only_scope() -> None:
    text = _generation_plan_text()

    assert FRONTEND_GENERATION_PLAN_PATH.exists()
    assert "**Statut :** CANONICAL FRONTEND GENERATION PLAN V1" in text
    assert "documentation only" in text
    assert "aucun Kotlin" in text
    assert "aucun dossier `android/`" in text
    assert "aucun runtime frontend" in text
    assert "aucun scaffold Android" in text
    assert "aucun backend modifié" in text

    for source_doc in (
        "59_DESIGN_SYSTEM_V1_DRAFT.md",
        "60_DESIGN_SYSTEM_TOKENS_KT.md",
        "61_DESIGN_SYSTEM_COMPOSITE_COMPONENTS.md",
        "62_DESIGN_SYSTEM_COMPONENT_CATALOG.md",
        "63_FRONTEND_ARCHITECTURE_V1.md",
        "07_ANDROID_APP_RESPONSIBILITIES.md",
    ):
        assert source_doc in text


def test_frontend_generation_plan_v1_has_required_sections_in_order() -> None:
    text = _generation_plan_text()

    expected_headings = [
        "## 1. Mission du document",
        "## 2. Règle fondamentale",
        "## 3. Ordre officiel des applications",
        "## 4. Ordre officiel des écrans Imperium",
        "## 5. Mock Data Strategy",
        "## 6. Design Validation Checklist",
        "## 7. Functional Validation Checklist",
        "## 8. Claude Design Pipeline",
        "## 9. Screen Completion Gate",
        "## 10. Global Frontend Foundation Readiness V1",
        "## 11. Constraints",
        "## 12. Definition of Done",
        "## 13. Frontend Generation Readiness",
    ]

    positions = [text.index(heading) for heading in expected_headings]
    assert positions == sorted(positions)


def test_frontend_generation_plan_v1_enforces_phase_order_and_backend_gate() -> None:
    rule = _section(_generation_plan_text(), "2. Règle fondamentale")

    for phase in (
        "Phase 1 | UI pure",
        "Phase 2 | Mock data",
        "Phase 3 | Backend wiring",
        "Phase 4 | Polish",
    ):
        assert phase in rule

    assert "Aucun branchement backend avant validation visuelle complète de l'écran" in rule
    assert "Le passage en Phase 3 est impossible sans validation humaine de la preview" in rule
    assert "API réelle" in rule
    assert "Connexion backend" in rule


def test_frontend_generation_plan_v1_locks_application_order_and_rationale() -> None:
    apps = _section(_generation_plan_text(), "3. Ordre officiel des applications")

    expected_order = [
        "| 1 | Imperium |",
        "| 2 | Vault |",
        "| 3 | Path |",
        "| 4 | Pulse |",
        "| 5 | Vector |",
    ]

    positions = [apps.index(item) for item in expected_order]
    assert positions == sorted(positions)

    for rationale in (
        "Command center prioritaire",
        "Réalité financière",
        "sadaqa",
        "Santé et nutrition",
        "platform-safe",
    ):
        assert rationale in apps


def test_frontend_generation_plan_v1_locks_imperium_screen_order_status_dependencies_and_validation() -> None:
    imperium = _section(_generation_plan_text(), "4. Ordre officiel des écrans Imperium")

    expected_screens = [
        "| 01 | Dashboard |",
        "| 02 | Mission Active |",
        "| 03 | Inbox |",
        "| 04 | Weekly Review |",
        "| 05 | History |",
        "| 06 | Settings |",
    ]

    positions = [imperium.index(screen) for screen in expected_screens]
    assert positions == sorted(positions)

    for required in (
        "Status",
        "Dependencies",
        "Validation Criteria",
        "READY FOR UI PURE",
        "UI VALIDATED",
        "MOCK DATA VALIDATED",
        "READY FOR BACKEND WIRING",
        "BACKEND WIRED",
        "DONE",
        "Une seule mission active",
        "aucune décision locale canonique",
    ):
        assert required in imperium


def test_frontend_generation_plan_v1_defines_mock_data_without_real_backend_connections() -> None:
    mocks = _section(_generation_plan_text(), "5. Mock Data Strategy")

    for forbidden_backend_use in (
        "aucune API réelle",
        "aucune connexion backend",
        "aucun appel n8n",
        "aucune lecture PostgreSQL",
        "aucune écriture PostgreSQL",
        "aucune mémoire vectorielle",
        "aucune décision AI canonique",
    ):
        assert forbidden_backend_use in mocks

    for json_fixture in (
        '"screen_id": "IMP-01"',
        '"route_id": "IMP.DASH.MAIN"',
        '"screen": "IMP.DASH.MAIN"',
        '"fixture_name": "dashboard_mock_v1"',
        '"screen_id": "IMP-02"',
        '"route_id": "IMP.MISSION.ACTIVE"',
        '"screen": "IMP.MISSION.ACTIVE"',
        '"fixture_name": "mission_active_empty_v1"',
        '"screen_id": "IMP-04"',
        '"route_id": "IMP.WR.SUMMARY"',
        '"screen": "IMP.WR.SUMMARY"',
        '"fixture_name": "weekly_review_error_v1"',
        '"sync_state": "mock"',
    ):
        assert json_fixture in mocks


def test_frontend_generation_plan_v1_locks_design_and_functional_validation_checklists() -> None:
    design = _section(_generation_plan_text(), "6. Design Validation Checklist")
    functional = _section(_generation_plan_text(), "7. Functional Validation Checklist")

    for required in (
        "✓ Responsive tablette",
        "✓ Respecte Design System",
        "✓ Respecte Component Catalog",
        "✓ Respecte Navigation",
        "✓ Respecte Spacing",
        "✓ Respecte Architecture V1",
        "✓ Aucun placeholder cassé",
    ):
        assert required in design

    for required in (
        "✓ UI validée",
        "✓ Endpoint existant",
        "✓ Endpoint documenté",
        "✓ Endpoint testé",
        "✓ Loading state",
        "✓ Empty state",
        "✓ Error state",
        "Screen → UiEvent → ViewModel → Repository → API",
    ):
        assert required in functional


def test_frontend_generation_plan_v1_locks_claude_pipeline_and_foundation_readiness() -> None:
    text = _generation_plan_text()
    pipeline = _section(text, "8. Claude Design Pipeline")
    foundation_readiness = _section(text, "10. Global Frontend Foundation Readiness V1")

    for required in (
        "Prompt",
        "Worktree",
        "Preview URL",
        "Validation humaine",
        "Correction éventuelle",
        "Merge",
    ):
        assert required in pipeline

    for readiness_row in (
        "| Design System | READY |",
        "| Component Catalog | READY |",
        "| Screen Architecture | READY |",
        "| Frontend Architecture | READY |",
        "| Generation Plan | READY |",
        "| Android Runtime | NOT STARTED |",
    ):
        assert readiness_row in foundation_readiness


def test_frontend_generation_plan_v1_locks_definition_of_done_without_backend_wiring() -> None:
    done = _section(_generation_plan_text(), "12. Definition of Done")

    for required in (
        "✓ UI validée",
        "✓ Navigation validée",
        "✓ Responsive validé",
        "✓ Loading validé",
        "✓ Empty validé",
        "✓ Error validé",
        "✓ Mock data validée",
    ):
        assert required in done

    for forbidden in (
        "✓ Backend branché",
        "Endpoint",
        "API réelle",
        "PostgreSQL",
    ):
        assert forbidden not in done


def test_frontend_generation_plan_v1_locks_mandatory_screen_readiness_flags() -> None:
    readiness = _section(_generation_plan_text(), "13. Frontend Generation Readiness")

    for readiness_row in (
        "| Dashboard | READY |",
        "| Mission Active | READY |",
        "| Inbox | READY |",
        "| Weekly Review | READY |",
        "| History | READY |",
        "| Settings | READY |",
    ):
        assert readiness_row in readiness

    assert "| Screen | Status |" in readiness


def test_frontend_generation_plan_v1_constraints_remain_documentation_only() -> None:
    constraints = _section(_generation_plan_text(), "11. Constraints")

    for required in (
        "Aucun code Kotlin",
        "Aucun dossier `android/`",
        "Aucun runtime frontend",
        "Aucun scaffold Android",
        "Aucun backend modifié",
        "Documentation uniquement",
        "Tests documentaires pytest verrouillant les sections clés",
    ):
        assert required in constraints
