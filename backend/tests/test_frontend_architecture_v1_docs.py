from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = BACKEND_ROOT.parent / "docs_master"
FRONTEND_ARCHITECTURE_PATH = DOCS_ROOT / "63_FRONTEND_ARCHITECTURE_V1.md"


def _architecture_text() -> str:
    return FRONTEND_ARCHITECTURE_PATH.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    assert marker in text
    return text.split(marker, maxsplit=1)[1].split("\n## ", maxsplit=1)[0]


def test_frontend_architecture_v1_doc_exists_and_declares_sources() -> None:
    text = _architecture_text()

    assert "**Statut :** CANONICAL FRONTEND ARCHITECTURE V1" in text
    assert "specification only" in text
    assert "aucun Kotlin runtime ou scaffold Android" in text

    for source_doc in (
        "59_DESIGN_SYSTEM_V1_DRAFT.md",
        "60_DESIGN_SYSTEM_TOKENS_KT.md",
        "61_DESIGN_SYSTEM_COMPOSITE_COMPONENTS.md",
        "62_DESIGN_SYSTEM_COMPONENT_CATALOG.md",
        "07_ANDROID_APP_RESPONSIBILITIES.md",
    ):
        assert source_doc in text


def test_frontend_architecture_v1_has_required_sections_in_order() -> None:
    text = _architecture_text()

    expected_headings = [
        "## 1. Principes",
        "## 2. Repository Structure",
        "## 3. Design System Integration",
        "## 4. Navigation Architecture",
        "## 5. State Management",
        "## 6. Network Layer",
        "## 7. Local Cache",
        "## 8. Sync Layer",
        "## 9. Feature Modules",
        "## 10. Widgets",
        "## 11. Tablet Strategy",
        "## 12. Offline Strategy",
    ]

    positions = [text.index(heading) for heading in expected_headings]
    assert positions == sorted(positions)


def test_frontend_architecture_principles_keep_backend_authority() -> None:
    principles = _section(_architecture_text(), "1. Principes")

    for required in (
        "Backend is source of truth",
        "UI state only",
        "Unidirectional data flow",
        "Compose first",
        "Offline aware",
        "Theme driven",
        "Feature modularity",
        "Screen\n→ UiEvent\n→ ViewModel\n→ Repository\n→ API",
        "Une seule mission active",
        "Le frontend maintient uniquement de l'état UI",
        "Il ne maintient pas",
    ):
        assert required in principles


def test_frontend_architecture_defines_target_repository_structure_and_module_roles() -> None:
    structure = _section(_architecture_text(), "2. Repository Structure")

    for module_path in (
        "app/",
        "core/",
        "designsystem/",
        "navigation/",
        "network/",
        "database/",
        "sync/",
        "widgets/",
        "feature_imperium/",
        "feature_vault/",
        "feature_vector/",
        "feature_pulse/",
        "feature_path/",
    ):
        assert module_path in structure

    for required_role in (
        "`app/` ne contient pas de logique métier",
        "Le cache local n'est jamais source de vérité",
        "machine d'état sync",
        "Android home widgets",
        "Chaque feature module contient",
    ):
        assert required_role in structure


def test_frontend_architecture_design_system_integration_maps_docs_to_compose_layers() -> None:
    design_system = _section(_architecture_text(), "3. Design System Integration")

    for required in (
        "`59_DESIGN_SYSTEM_V1_DRAFT.md`",
        "`60_DESIGN_SYSTEM_TOKENS_KT.md`",
        "`61_DESIGN_SYSTEM_COMPOSITE_COMPONENTS.md`",
        "`62_DESIGN_SYSTEM_COMPONENT_CATALOG.md`",
        "ImperiumTheme",
        "Foundation Components",
        "Composite Components",
        "premium asset must not contain dynamic data",
        "Vector halo séparé",
        "JetBrains Mono",
        "Noto Naskh Arabic",
    ):
        assert required in design_system


def test_frontend_architecture_navigation_uses_v1_routes_stable_ids_and_surface_types() -> None:
    navigation = _section(_architecture_text(), "4. Navigation Architecture")

    for required in (
        "`Imperium`",
        "`Vault`",
        "`Vector`",
        "`Pulse`",
        "`Path`",
        "`IMP.DASH.MAIN`",
        "`VAU.DASH.MAIN`",
        "`VEC.DASH.MAIN`",
        "`PUL.DASH.MAIN`",
        "`PAT.DASH.MAIN`",
        "Dialogs",
        "Bottom sheets",
        "Deep links",
        "`IMP.MISSION.ACTIVE` pour la mission active unique",
        "Navigation Imperium V1 permanente",
    ):
        assert required in navigation

    for screen_id in (
        "IMP-01",
        "IMP-02",
        "IMP-03",
        "IMP-04",
        "IMP-05",
        "IMP-06",
        "VAU-01",
        "VAU-12",
        "VEC-03",
        "PUL-14",
        "PAT-11",
    ):
        assert screen_id in navigation

    assert "IMP.MISSION.DETAIL" not in navigation


def test_frontend_architecture_state_network_cache_and_sync_are_offline_aware() -> None:
    text = _architecture_text()
    state_management = _section(text, "5. State Management")
    network = _section(text, "6. Network Layer")
    cache = _section(text, "7. Local Cache")
    sync = _section(text, "8. Sync Layer")

    for required in (
        "Screen\n→ ViewModel\n→ Repository\n→ API",
        "UiState",
        "UiEvent",
        "UiEffect",
        "Compose ne contient pas de logique métier",
    ):
        assert required in state_management

    for required in (
        "Retrofit",
        "Kotlinx Serialization",
        "OkHttp interceptors",
        "auth bearer token",
        "idempotency key",
        "Timeouts",
        "Retries",
        "Stale data",
    ):
        assert required in network

    for required in (
        "Room",
        "cache local != source de vérité",
        "Le backend reste canonique",
        "pending writes",
    ):
        assert required in cache

    for sync_state in ("pending", "syncing", "synced", "failed", "conflict", "cached", "stale"):
        assert f"`{sync_state}`" in sync

    for required in ("SyncBanner", "SyncStateChip", "Conflict Handling", "block fake success"):
        assert required in sync


def test_frontend_architecture_lists_feature_modules_with_screens_viewmodels_repositories_navigation() -> None:
    features = _section(_architecture_text(), "9. Feature Modules")

    expected_screen_ranges = {
        "feature_imperium": [f"IMP-{number:02d}" for number in range(1, 7)],
        "feature_vault": [f"VAU-{number:02d}" for number in range(1, 13)],
        "feature_vector": [f"VEC-{number:02d}" for number in range(1, 12)],
        "feature_pulse": [f"PUL-{number:02d}" for number in range(1, 15)],
        "feature_path": [f"PAT-{number:02d}" for number in range(1, 12)],
    }

    for feature_name, screen_ids in expected_screen_ranges.items():
        assert feature_name in features
        for screen_id in screen_ids:
            assert screen_id in features

    for required in (
        "ViewModels",
        "Repositories",
        "Navigation",
        "Mission Active",
        "Inbox",
        "Weekly Review",
        "History",
        "Settings",
        "no Bolt automation path",
        "Vault settings deep link to `PAT-11d`",
        "Path fasting constraints",
        "sadaqa creates Vault handoff through backend",
    ):
        assert required in features


def test_frontend_architecture_widgets_tablet_and_offline_strategy_are_canonical_v1() -> None:
    text = _architecture_text()
    widgets = _section(text, "10. Widgets")
    tablet = _section(text, "11. Tablet Strategy")
    offline = _section(text, "12. Offline Strategy")

    for required in (
        "Prayer countdown",
        "Current mission",
        "Hydration",
        "Vault summary",
        "Widget UI\n→ WidgetStateRepository\n→ Room widget snapshot",
        "pas de success local sans confirmation backend",
    ):
        assert required in widgets

    for required in (
        "Galaxy Tab S10 Ultra",
        "Sidebar | Content | Context Panel",
        "240dp",
        "max 1280dp",
        "320-480dp",
        "Téléphone",
        "bottom navigation",
    ):
        assert required in tablet

    for required in (
        "Lecture offline",
        "Write queue",
        "Sync retry",
        "Conflict",
        "idempotency key",
        "ne jamais marquer `synced` avant confirmation backend",
        "créer mission active officielle",
        "présenter recommandation VTC comme live",
    ):
        assert required in offline
