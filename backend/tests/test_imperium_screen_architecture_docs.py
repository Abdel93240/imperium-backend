import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
DOCS_ROOT = REPO_ROOT / "docs_master"
DESIGN_SYSTEM_PATH = DOCS_ROOT / "59_DESIGN_SYSTEM_V1_DRAFT.md"
DESIGN_SYSTEM_TOKENS_KT_PATH = DOCS_ROOT / "60_DESIGN_SYSTEM_TOKENS_KT.md"
DESIGN_SYSTEM_COMPOSITE_COMPONENTS_PATH = DOCS_ROOT / "61_DESIGN_SYSTEM_COMPOSITE_COMPONENTS.md"
DESIGN_SYSTEM_COMPONENT_CATALOG_PATH = DOCS_ROOT / "62_DESIGN_SYSTEM_COMPONENT_CATALOG.md"
FRONTEND_ARCHITECTURE_PATH = DOCS_ROOT / "63_FRONTEND_ARCHITECTURE_V1.md"
APP_ROOT = BACKEND_ROOT / "app"

IMPERIUM_ROUTE_PREFIXES = {
    APP_ROOT / "api/v1/routes/imperium.py": "/api/imperium",
    APP_ROOT / "api/v1/routes/imperium_contracts.py": "/api/imperium",
    APP_ROOT / "api/v1/routes/imperium_daily_plan.py": "/api/imperium",
    APP_ROOT / "api/v1/routes/imperium_dashboard.py": "/api/imperium",
    APP_ROOT / "api/v1/routes/imperium_events.py": "/api/imperium",
    APP_ROOT / "api/v1/routes/imperium_frontend.py": "/api/imperium",
    APP_ROOT / "api/v1/routes/imperium_home.py": "/api/imperium",
}

IMPERIUM_ROUTE_IDS = [
    "IMP.DASH.MAIN",
    "IMP.OPERATIONS.MAIN",
    "IMP.HISTORY.MAIN",
    "IMP.CHECKIN.MORNING",
    "IMP.MISSION.OUTCOME",
    "IMP.DAY.FINISH",
    "IMP.REPLAN.VALIDATE",
    "IMP.MISSION.ADD_MANUAL",
    "IMP.PLAN.HISTORY",
    "IMP.CHAT.CONVERSATION",
    "IMP.DECISIONS.LOG",
    "IMP.WR.LIST",
    "IMP.WR.READ_ONLY",
    "IMP.WR.INTERACTIVE",
    "IMP.SETTINGS.PRIORITIES",
    "IMP.SETTINGS.CORE",
]
VAULT_SCREEN_IDS = [f"VAU-{number:02d}" for number in range(1, 13)]
VECTOR_SCREEN_IDS = [f"VEC-{number:02d}" for number in range(1, 12)]
PULSE_SCREEN_IDS = [f"PUL-{number:02d}" for number in range(1, 15)]
PATH_SCREEN_IDS = [f"PAT-{number:02d}" for number in range(1, 12)]
SOURCE_DOCS = [
    "07_ANDROID_APP_RESPONSIBILITIES.md",
    "24_DAY_FINISHED_WORKFLOW.md",
    "26_PRIORITY_RULES_WORKFLOW.md",
    "29_WEEKLY_REPORT_WORKFLOW.md",
    "32_WR_INTERACTIVE_WORKFLOW.md",
    "43_IMPERIUM_LOGIC_DETAIL.md",
]
VAULT_SOURCE_DOCS = [
    "01_SIGNAL_VARIABLES_DICTIONARY.md",
    "11_FINANCIAL_PRESSURE_FORMULA.md",
    "27_VAULT_TRANSACTIONS_WORKFLOW.md",
    "37_GEMINI_VISION_PROMPTS.md",
    "42_VAULT_LOGIC_DETAIL.md",
]
VECTOR_SOURCE_DOCS = [
    "01_SIGNAL_VARIABLES_DICTIONARY.md",
    "07_ANDROID_APP_RESPONSIBILITIES.md",
    "33_VECTOR_LOGIC_DETAIL.md",
    "37_GEMINI_VISION_PROMPTS.md",
]
PULSE_SOURCE_DOCS = [
    "01_SIGNAL_VARIABLES_DICTIONARY.md",
    "07_ANDROID_APP_RESPONSIBILITIES.md",
    "34_PULSE_MEDICAL_FEED_AI.md",
    "37_GEMINI_VISION_PROMPTS.md",
    "40_PULSE_LOGIC_DETAIL.md",
]
PATH_SOURCE_DOCS = [
    "01_SIGNAL_VARIABLES_DICTIONARY.md",
    "07_ANDROID_APP_RESPONSIBILITIES.md",
    "41_PATH_LOGIC_DETAIL.md",
    "42_VAULT_LOGIC_DETAIL.md",
    "43_IMPERIUM_LOGIC_DETAIL.md",
]


def _design_system_text() -> str:
    return DESIGN_SYSTEM_PATH.read_text(encoding="utf-8")


def _design_system_tokens_kt_text() -> str:
    return DESIGN_SYSTEM_TOKENS_KT_PATH.read_text(encoding="utf-8")


def _design_system_composite_components_text() -> str:
    return DESIGN_SYSTEM_COMPOSITE_COMPONENTS_PATH.read_text(encoding="utf-8")


def _design_system_component_catalog_text() -> str:
    return DESIGN_SYSTEM_COMPONENT_CATALOG_PATH.read_text(encoding="utf-8")


def _frontend_architecture_text() -> str:
    return FRONTEND_ARCHITECTURE_PATH.read_text(encoding="utf-8")


def _numbered_heading_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if re.match(r"^## \d+\. ", line)]


def _top_level_section(text: str, section_number: int) -> str:
    marker = next(line for line in text.splitlines() if line.startswith(f"## {section_number}. "))
    return text.split(marker, maxsplit=1)[1].split("\n## ", maxsplit=1)[0]


def _subsection(text: str, heading: str) -> str:
    marker = next(line for line in text.splitlines() if line.startswith(heading))
    return text.split(marker, maxsplit=1)[1].split("\n### ", maxsplit=1)[0]


def _named_section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    assert marker in text
    return text.split(marker, maxsplit=1)[1].split("\n## ", maxsplit=1)[0]


def _normalized_doc_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("**", "")).strip().lower()


def _assert_doc_contains(text: str, required: str) -> None:
    assert _normalized_doc_text(required) in _normalized_doc_text(text)


def _assert_doc_contains_terms(text: str, *terms: str) -> None:
    normalized_text = _normalized_doc_text(text)
    for term in terms:
        assert _normalized_doc_text(term) in normalized_text


def _screen_section(text: str, screen_id: str) -> str:
    marker_pattern = re.compile(rf"^### \d+\.\d+ .*`{re.escape(screen_id)}`.*$", re.MULTILINE)
    marker_match = marker_pattern.search(text)
    assert marker_match is not None, f"Missing screen section for {screen_id}"

    section_start = marker_match.end()
    next_marker = re.search(r"^### \d+\.\d+ ", text[section_start:], re.MULTILINE)
    section_end = section_start + next_marker.start() if next_marker else len(text)
    return text[section_start:section_end]


def _vault_screen_section(text: str, screen_id: str) -> str:
    return _screen_section(text, screen_id)


def _vector_screen_section(text: str, screen_id: str) -> str:
    return _screen_section(text, screen_id)


def _pulse_screen_section(text: str, screen_id: str) -> str:
    return _screen_section(text, screen_id)


def _path_screen_section(text: str, screen_id: str) -> str:
    return _screen_section(text, screen_id)


def _imperium_backend_routes() -> set[str]:
    route_pattern = re.compile(
        r"@router\.(get|post|patch|put|delete)\(\s*\"([^\"]+)\"",
        re.MULTILINE,
    )
    endpoints = set()
    for route_file, prefix in IMPERIUM_ROUTE_PREFIXES.items():
        route_text = route_file.read_text(encoding="utf-8")
        for method, route_path in route_pattern.findall(route_text):
            endpoints.add(f"{method.upper()} {prefix}{route_path}")
    return endpoints


def _imperium_endpoint_matrix_real_endpoints(text: str) -> set[str]:
    matrix = _subsection(text, "### 12.17 Imperium Endpoint Matrix V1")
    rows = [line for line in matrix.splitlines() if line.startswith("| IMP-")]
    real_endpoints = set()
    for row in rows:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        real_cell = cells[1]
        real_endpoints.update(
            f"{method} {path}"
            for method, path in re.findall(r"`(GET|POST|PATCH|PUT|DELETE) (/api/imperium[^`]+)`", real_cell)
        )
    return real_endpoints


def test_design_system_has_table_of_contents_for_canonical_sections() -> None:
    text = _design_system_text()
    toc = text.split("## Table des matières", maxsplit=1)[1].split("\n---", maxsplit=1)[0]

    for required in (
        "[Sources de vérité V1]",
        "[V1 Scope Lock]",
        "[0. Principe fondateur]",
        "[1. Color System]",
        "[7. Compose Foundation Components]",
        "[8. Responsive Strategy]",
        "[10. Implementation Guardrail]",
        "[Design Token Extraction Contract]",
        "[Component Catalog Extraction Contract]",
        "[12. Imperium Screen Architecture Mapping V1]",
        "[16. Path Screen Architecture Mapping V1]",
    ):
        assert required in toc


def test_design_system_declares_reproducible_sources_and_scope_lock() -> None:
    text = _design_system_text()
    sources = _named_section(text, "Sources de vérité V1")
    scope = _named_section(text, "V1 Scope Lock")

    assert "**Statut :** CANONICAL V1" in text
    assert "docs réellement présents" in sources
    assert "docs importés" in sources
    assert "audits utilisés" in sources
    assert "documents archivés/non canoniques" in sources

    for source_doc in (
        "01_SIGNAL_VARIABLES_DICTIONARY.md",
        "07_ANDROID_APP_RESPONSIBILITIES.md",
        "33_VECTOR_LOGIC_DETAIL.md",
        "40_PULSE_LOGIC_DETAIL.md",
        "41_PATH_LOGIC_DETAIL.md",
        "42_VAULT_LOGIC_DETAIL.md",
        "43_IMPERIUM_LOGIC_DETAIL.md",
    ):
        assert source_doc in sources

    for audit_doc in (
        "audits/2026-06-02_0519_audit.md",
        "audits/2026-06-02_1233_audit.md",
        "score 7.5/10",
    ):
        assert audit_doc in sources

    for excluded_surface in (
        "Bolt OCR",
        "Smart Fuel UI",
        "Mon OS Personnel",
        "Body Photo Review",
        "Sunnah",
        "Witr",
        "Duha",
        "Tahajjud",
        "toute autre surface V2/V3",
    ):
        assert excluded_surface in scope

    assert "peuvent apparaitre dans des docs historiques" in scope
    assert "ne font pas partie du périmètre V1" in scope


def test_design_system_defines_extraction_contracts_for_tokens_and_components() -> None:
    text = _design_system_text()
    token_contract = _named_section(text, "Design Token Extraction Contract")
    component_contract = _named_section(text, "Component Catalog Extraction Contract")

    for token_family in ("Colors", "Typography", "Spacing", "Radius", "Elevation", "Icons", "States"):
        assert token_family in token_contract

    for kotlin_name in (
        "ImperiumColor.Primary",
        "ImperiumSpacing.MD",
        "ImperiumElevation.L2",
        "ImperiumRadius.Card",
        "ImperiumState.Syncing",
    ):
        assert kotlin_name in token_contract

    for component_family in (
        "Button",
        "Input",
        "Selection",
        "Navigation",
        "Feedback",
        "Containers",
        "States",
    ):
        assert component_family in component_contract

    assert "préparer `61_DESIGN_SYSTEM_COMPONENTS_CATALOG.md`" in component_contract


def test_design_system_tokens_kt_spec_exists_and_covers_required_token_families() -> None:
    text = _design_system_tokens_kt_text()

    assert DESIGN_SYSTEM_TOKENS_KT_PATH.exists()
    assert "docs_master/59_DESIGN_SYSTEM_V1_DRAFT.md" in text
    assert "033277a" in text

    for token_family in (
        "Color Tokens",
        "Typography Tokens",
        "Spacing Tokens",
        "Radius Tokens",
        "Elevation Tokens",
        "Icon Size Tokens",
        "State Tokens",
        "Kotlin naming conventions",
        "Non-goals",
    ):
        assert token_family in text

    for color_object in (
        "ImperiumColors",
        "VaultColors",
        "VectorColors",
        "PulseColors",
        "PathColors",
        "SemanticStateColors",
        "VectorHaloColors",
    ):
        assert color_object in text

    for app_name in ("Imperium", "Vault", "Vector", "Pulse", "Path"):
        assert app_name in text


def test_design_system_tokens_kt_spec_keeps_semantic_states_and_vector_halo_separate() -> None:
    text = _design_system_tokens_kt_text()

    semantic_section = _subsection(text, "### 1.6 SemanticStateColors")
    halo_section = _subsection(text, "### 1.7 VectorHaloColors")

    assert "Success | `#34C759`" in semantic_section
    assert "Warning | `#F5A524`" in semantic_section
    assert "Error | `#E5484D`" in semantic_section
    assert "Info | `#0091FF`" in semantic_section
    assert "Halo" not in semantic_section

    assert "HaloSuccess | `#22D673`" in halo_section
    assert "HaloWarning | `#F5C842`" in halo_section
    assert "HaloError | `#FF4A4A`" in halo_section
    assert "HaloAnalyzing | `#FFFFFF` @ 80%" in halo_section
    assert "SemanticStateColors" in halo_section


def test_design_system_tokens_kt_spec_does_not_create_frontend_or_kotlin_runtime() -> None:
    text = _design_system_tokens_kt_text()

    assert not (BACKEND_ROOT / "android").exists()
    assert not (BACKEND_ROOT / "frontend").exists()
    assert list(BACKEND_ROOT.rglob("*.kt")) == []

    for non_goal in (
        "No Android frontend creation",
        "No Kotlin runtime implementation yet",
        "No asset import",
        "No screen implementation",
    ):
        assert non_goal in text


def test_design_system_composite_components_spec_exists_and_locks_dynamic_data_rule() -> None:
    text = _design_system_composite_components_text()

    assert DESIGN_SYSTEM_COMPOSITE_COMPONENTS_PATH.exists()
    assert "docs_master/59_DESIGN_SYSTEM_V1_DRAFT.md" in text
    assert "docs_master/60_DESIGN_SYSTEM_TOKENS_KT.md" in text
    assert "premium asset must not contain dynamic data" in text
    assert "Un asset premium ne doit jamais contenir une donnée dynamique figée." in text

    for taxonomy_item in (
        "Static Asset",
        "Decorative Shell",
        "Dynamic Compose Component",
        "Composite Component",
        "Interactive Component",
        "Animated Component",
    ):
        assert taxonomy_item in text


def test_design_system_composite_components_spec_declares_required_rendering_rules() -> None:
    text = _design_system_composite_components_text()
    rules = _top_level_section(text, 3)

    for required_rule in (
        "Les textes sont rendus par Compose",
        "Les montants sont rendus par Compose",
        "Les dates, horaires et durées sont rendus par Compose",
        "Les progress, rings, bars, gauges, remplissages et waveforms fonctionnelles sont rendus par Compose",
        "Les boutons interactifs, sliders, toggles, menus, chips et actions sont rendus par Compose",
        "Les états métier et sync",
        "Accessibility is mandatory",
    ):
        assert required_rule in rules


def test_design_system_composite_components_catalog_includes_required_dynamic_components() -> None:
    text = _design_system_composite_components_text()

    for component in (
        "MissionFocusCard",
        "DailyPlanCard",
        "WeeklyReviewCard",
        "AIRecommendationCard",
        "KPIBlock",
        "ChatMessageBubble",
        "FinancialPressureCard",
        "TransactionRow",
        "ReceiptReviewCard",
        "WalletBalanceCard",
        "SavingsProgressRing",
        "MonthlyReviewCard",
        "VectorHalo",
        "DemandRing",
        "RecommendationCard",
        "ZonePriorityCard",
        "TrafficAlertPanel",
        "SessionStatusCard",
        "HydrationDrop",
        "MacroProgressCard",
        "WorkoutActivityCard",
        "RecoveryRing",
        "SleepScoreCard",
        "BodyStatusWidget",
    ):
        assert component in text


def test_design_system_composite_components_catalog_includes_path_components() -> None:
    text = _design_system_composite_components_text()
    path_catalog = _top_level_section(text, 8)

    for component in (
        "HijriDateCard",
        "QuranAudioPlayer",
        "TasbihCounter",
        "PrayerStatusCard",
        "FastingProgressCard",
        "SadaqaProgressCard",
    ):
        assert component in path_catalog

    assert "Prayer times" in path_catalog
    assert "Vault weekly profit" in path_catalog


def test_design_system_composite_components_spec_does_not_create_frontend_or_kotlin_runtime() -> None:
    text = _design_system_composite_components_text()

    assert not (BACKEND_ROOT / "android").exists()
    assert not (BACKEND_ROOT / "frontend").exists()
    assert list(BACKEND_ROOT.rglob("*.kt")) == []

    for non_goal in (
        "Ne pas créer Kotlin",
        "Ne pas créer Android",
        "Ne pas importer assets",
        "Ne pas créer de frontend",
        "Ne pas créer de vrai `.kt`",
    ):
        assert non_goal in text


def test_design_system_component_catalog_spec_exists_and_references_sources() -> None:
    text = _design_system_component_catalog_text()

    assert DESIGN_SYSTEM_COMPONENT_CATALOG_PATH.exists()
    assert "docs_master/59_DESIGN_SYSTEM_V1_DRAFT.md" in text
    assert "docs_master/60_DESIGN_SYSTEM_TOKENS_KT.md" in text
    assert "docs_master/61_DESIGN_SYSTEM_COMPOSITE_COMPONENTS.md" in text
    assert "Foundation Component Catalog V1" in text


def test_design_system_component_catalog_includes_required_families() -> None:
    text = _design_system_component_catalog_text()

    for family_heading in (
        "## 3. Buttons",
        "## 4. Inputs",
        "## 5. Selection",
        "## 6. Navigation",
        "## 7. Feedback",
        "## 8. Containers",
        "## 9. States",
        "## 10. Data Display",
    ):
        assert family_heading in text

    for required_column in (
        "Purpose",
        "Compose responsibility",
        "Tokens used",
        "Variants",
        "States",
        "Accessibility rules",
        "Responsive behavior Tab S10 Ultra",
        "When to use",
        "When not to use",
    ):
        assert required_column in text


def test_design_system_component_catalog_includes_main_foundation_components() -> None:
    text = _design_system_component_catalog_text()

    for component in (
        "ImperiumPrimaryButton",
        "ImperiumSecondaryButton",
        "ImperiumGhostButton",
        "ImperiumDestructiveButton",
        "ImperiumTextField",
        "ImperiumNumberField",
        "ImperiumSearchField",
        "ImperiumVoiceInput",
        "ImperiumToggle",
        "ImperiumCheckbox",
        "ImperiumRadio",
        "ImperiumSegmentedControl",
        "ImperiumTopBar",
        "ImperiumSidebar",
        "ImperiumBottomNavigation",
        "ImperiumTabBar",
        "ImperiumDrawer",
        "ImperiumSnackbar",
        "ImperiumToast",
        "ImperiumBanner",
        "ImperiumAlertDialog",
        "SyncStateChip",
        "ImperiumCard",
        "ImperiumInteractiveCard",
        "ImperiumBottomSheet",
        "ImperiumDialog",
        "ImperiumModalFrame",
        "ImperiumSectionHeader",
        "ImperiumLoadingState",
        "ImperiumEmptyState",
        "ImperiumErrorState",
        "ImperiumOfflineState",
        "ImperiumConflictState",
        "ImperiumSkeleton",
        "ImperiumMetricCard",
        "ImperiumKpiBlock",
        "ImperiumProgressBar",
        "ImperiumProgressRing",
        "ImperiumTimeline",
        "ImperiumListItem",
        "ImperiumTransactionRow",
        "ImperiumStatusChip",
    ):
        assert component in text


def test_design_system_component_catalog_documents_theme_awareness() -> None:
    text = _design_system_component_catalog_text()
    theme_awareness = _top_level_section(text, 2)

    assert "Theme Awareness" in text
    for app_name in ("Imperium", "Vault", "Vector", "Pulse", "Path"):
        assert app_name in theme_awareness

    for token_object in (
        "ImperiumColors",
        "VaultColors",
        "VectorColors",
        "PulseColors",
        "PathColors",
        "SemanticStateColors",
        "VectorHaloColors",
    ):
        assert token_object in theme_awareness

    assert "seul le theme, le copy et les donnees changent" in theme_awareness


def test_design_system_component_catalog_non_goals_prevent_runtime_creation() -> None:
    text = _design_system_component_catalog_text()
    non_goals = _top_level_section(text, 11)

    assert not (BACKEND_ROOT / "android").exists()
    assert not (BACKEND_ROOT / "frontend").exists()
    assert list(BACKEND_ROOT.rglob("*.kt")) == []

    for non_goal in (
        "Ne pas creer Kotlin",
        "Ne pas creer Android",
        "Ne pas creer `android/`",
        "Ne pas creer `frontend/`",
        "Ne pas creer de vrai `.kt`",
        "Ne pas modifier le backend runtime",
    ):
        assert non_goal in non_goals


def test_design_system_keeps_foundation_and_guardrails_before_app_architectures() -> None:
    text = _design_system_text()
    headings = _numbered_heading_lines(text)

    assert headings[:17] == [
        "## 0. Principe fondateur",
        "## 1. COLOR SYSTEM",
        "## 2. TYPOGRAPHY SYSTEM",
        "## 3. SPACING SYSTEM",
        "## 4. RADIUS SYSTEM",
        "## 5. ELEVATION SYSTEM",
        "## 6. ICONOGRAPHY SYSTEM",
        "## 7. COMPOSE FOUNDATION COMPONENTS",
        "## 8. RESPONSIVE STRATEGY",
        "## 9. DESIGN RULES (synthèse non-négociables)",
        "## 10. Implementation Guardrail (Compose)",
        "## 11. Annexes (à produire post-V1)",
        "## 12. IMPERIUM SCREEN ARCHITECTURE MAPPING V1",
        "## 13. VAULT SCREEN ARCHITECTURE MAPPING V1",
        "## 14. VECTOR SCREEN ARCHITECTURE MAPPING V1",
        "## 15. PULSE SCREEN ARCHITECTURE MAPPING V1",
        "## 16. PATH SCREEN ARCHITECTURE MAPPING V1",
    ]


def test_design_system_foundation_declares_palettes_typography_spacing_and_elevation() -> None:
    text = _design_system_text()

    for app_heading in (
        "### 1.2 IMPERIUM",
        "### 1.3 VAULT",
        "### 1.4 VECTOR",
        "### 1.5 PULSE",
        "### 1.6 PATH",
    ):
        assert app_heading in text

    for style in ("**Display**", "**H1**", "**H2**", "**Body Large**", "**Caption**", "**Label**"):
        assert style in text

    spacing_section = _top_level_section(text, 3)
    assert "### 3.1 Base 8dp" in spacing_section
    for token in ("**SM** | 8", "**MD** | 16", "**LG** | 24", "**XL** | 32"):
        assert token in spacing_section

    elevation_section = _top_level_section(text, 5)
    for level in ("**L0**", "**L1**", "**L2**", "**L3**", "**L4**"):
        assert level in elevation_section


def test_design_system_defines_responsive_tab_s10_ultra_as_default_surface() -> None:
    text = _design_system_text()
    responsive_section = _top_level_section(text, 8)

    assert "### 8.2 Priorité Tab S10 Ultra Landscape" in responsive_section
    assert "le device par défaut V1" in responsive_section
    assert "Sidebar Rail étendu 240dp" in responsive_section
    assert "contenu central max-width 1280dp" in responsive_section
    assert "panneau contextuel persistant" in responsive_section


def test_vector_semantic_state_colors_and_halo_colors_are_non_contradictory() -> None:
    text = _design_system_text()
    semantic_section = _subsection(text, "### 1.1 Semantic state colors")
    vector_palette = _subsection(text, "### 1.4 VECTOR")

    assert "Success | `#34C759`" in semantic_section
    assert "Error | `#E5484D`" in semantic_section
    assert "Halo" not in semantic_section

    assert "**Halo Success (green)** | `#22D673`" in vector_palette
    assert "**Halo Warning (yellow)** | `#F5C842`" in vector_palette
    assert "**Halo Error (red)** | `#FF4A4A`" in vector_palette
    assert "ne remplacent pas les semantic state colors cross-app" in vector_palette
    assert "états UI génériques restent `Success|Warning|Error|Info`" in vector_palette

    assert "halo Vector vert" not in text
    assert "Halo states (Success/Warning/Error/Info)" not in text


def test_app_specific_composed_patterns_are_not_in_foundation() -> None:
    text = _design_system_text()
    foundation_section = _top_level_section(text, 7)

    assert "Vault-specific composed patterns" not in foundation_section
    assert "Vector-specific composed patterns" not in foundation_section
    assert "Pulse-specific composed patterns" not in foundation_section
    assert "Path-specific composed patterns" not in foundation_section

    assert "### 13.15 Vault-specific composed patterns" in text
    assert "### 14.15 Vector-specific composed patterns" in text
    assert "### 15.17 Pulse-specific composed patterns" in text
    assert "### 16.14 Path-specific composed patterns" in text


def test_frontend_architecture_63_exists_references_design_docs_and_has_all_sections() -> None:
    text = _frontend_architecture_text()

    assert FRONTEND_ARCHITECTURE_PATH.exists()

    for source_doc in (
        "59_DESIGN_SYSTEM_V1_DRAFT.md",
        "60_DESIGN_SYSTEM_TOKENS_KT.md",
        "61_DESIGN_SYSTEM_COMPOSITE_COMPONENTS.md",
        "62_DESIGN_SYSTEM_COMPONENT_CATALOG.md",
    ):
        assert source_doc in text

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
        "## 13. Security",
        "## 14. Performance",
        "## 15. Non Goals",
        "## 16. Frontend Generation Readiness",
    ]

    positions = [text.index(heading) for heading in expected_headings]
    assert positions == sorted(positions)


def test_frontend_architecture_63_declares_feature_modules_tablet_and_sync_states() -> None:
    text = _frontend_architecture_text()
    structure = _top_level_section(text, 2)
    features = _top_level_section(text, 9)
    sync = _top_level_section(text, 8)
    tablet = _top_level_section(text, 11)

    for feature_module in (
        "feature_imperium/",
        "feature_vault/",
        "feature_vector/",
        "feature_pulse/",
        "feature_path/",
    ):
        assert feature_module in structure
        assert feature_module.rstrip("/") in features

    for sync_state in ("pending", "syncing", "synced", "failed", "conflict", "cached", "stale"):
        assert f"`{sync_state}`" in sync

    for required in (
        "Galaxy Tab S10 Ultra",
        "Sidebar | Content | Context Panel",
        "240dp",
        "max 1280dp",
        "320-480dp",
        "Téléphone",
    ):
        assert required in tablet


def test_frontend_architecture_63_defines_security_performance_and_non_goals() -> None:
    text = _frontend_architecture_text()
    security = _top_level_section(text, 13)
    performance = _top_level_section(text, 14)
    non_goals = _top_level_section(text, 15)

    for required in (
        "JWT",
        "Secure storage",
        "Encrypted preferences",
        "No secrets in UI",
        "Android Keystore",
        "aucune API key Gemini, OpenAI, Claude, n8n",
    ):
        assert required in security

    for required in (
        "LazyColumn",
        "Image loading",
        "Pagination",
        "Memory rules",
        "clés stables obligatoires",
        "pas de liste infinie gardée intégralement en mémoire",
    ):
        assert required in performance

    for excluded_surface in (
        "iOS",
        "Web",
        "Desktop",
        "Compose Multiplatform",
        "Wear OS",
        "Android Auto",
        "OCR runtime V1",
        "AI runtime local frontend",
    ):
        assert excluded_surface in non_goals

    for forbidden_artifact in ("android/", "frontend/", "fichier Kotlin"):
        assert forbidden_artifact in non_goals


def test_frontend_architecture_63_declares_ready_for_compose_scaffold_gate() -> None:
    readiness = _top_level_section(_frontend_architecture_text(), 16)

    assert "READY_FOR_COMPOSE_SCAFFOLD = YES" in readiness

    for condition in (
        "DS canonique",
        "Tokens",
        "Components",
        "Composite Components",
        "Screen Architecture",
    ):
        assert condition in readiness

    for source_doc in (
        "docs_master/59_DESIGN_SYSTEM_V1_DRAFT.md",
        "docs_master/60_DESIGN_SYSTEM_TOKENS_KT.md",
        "docs_master/61_DESIGN_SYSTEM_COMPOSITE_COMPONENTS.md",
        "docs_master/62_DESIGN_SYSTEM_COMPONENT_CATALOG.md",
        "docs_master/63_FRONTEND_ARCHITECTURE_V1.md",
    ):
        assert source_doc in readiness

    assert "cinq modules feature V1 seulement" in readiness
    assert "non goals de la section 15" in readiness


def test_imperium_screen_source_docs_are_available_in_audited_docs_master() -> None:
    missing = [doc_name for doc_name in SOURCE_DOCS if not (DOCS_ROOT / doc_name).exists()]

    assert missing == []


def test_vault_screen_source_docs_are_available_in_audited_docs_master() -> None:
    missing = [doc_name for doc_name in VAULT_SOURCE_DOCS if not (DOCS_ROOT / doc_name).exists()]

    assert missing == []


def test_vector_screen_source_docs_are_available_in_audited_docs_master() -> None:
    missing = [doc_name for doc_name in VECTOR_SOURCE_DOCS if not (DOCS_ROOT / doc_name).exists()]

    assert missing == []


def test_pulse_screen_source_docs_are_available_in_audited_docs_master() -> None:
    missing = [doc_name for doc_name in PULSE_SOURCE_DOCS if not (DOCS_ROOT / doc_name).exists()]

    assert missing == []


def test_path_screen_source_docs_are_available_in_audited_docs_master() -> None:
    missing = [doc_name for doc_name in PATH_SOURCE_DOCS if not (DOCS_ROOT / doc_name).exists()]

    assert missing == []


def test_design_system_maps_imperium_surfaces_with_route_ids() -> None:
    text = _design_system_text()

    assert "## 12. IMPERIUM SCREEN ARCHITECTURE MAPPING V1" in text
    assert "### 12.0 Imperium Product Decisions V1" in text
    assert "### 12.16 Imperium Navigation Graph V1" in text
    assert "### 12.17 Imperium Endpoint Matrix V1" in text

    for route_id in IMPERIUM_ROUTE_IDS:
        assert "### 12." in text
        assert route_id in text
        assert f"`{route_id}`" in text

    assert "Weekly Review List (`IMP.WR.LIST`)" in text
    assert "Weekly Review Read-only View (`IMP.WR.READ_ONLY`)" in text
    assert "Weekly Review Interactive Popup (`IMP.WR.INTERACTIVE`)" in text
    assert "IMP-" not in text


def test_design_system_declares_screen_types_navigation_and_backend_dependencies() -> None:
    text = _design_system_text()

    for required in (
        "## 12. IMPERIUM SCREEN ARCHITECTURE MAPPING V1",
        "### 12.1 Canonical Routing Typology",
        "### 12.16 Imperium Navigation Graph V1",
        "### 12.17 Imperium Endpoint Matrix V1",
        "route",
        "tab",
        "dialog",
        "bottom_sheet",
        "deep_link",
        "/api/imperium/dashboard",
        "/api/imperium/day/finish",
        "/api/imperium/day/plan",
        "/api/imperium/day/plan/{plan_id}/activate",
        "/api/imperium/missions/backlog",
        "/api/imperium/missions/history",
        "/api/imperium/weekly-review/history",
        "/api/imperium/weekly-review/current",
        "/api/imperium/decision-framework/priorities",
        "/api/imperium/frontend/app-manifest",
    ):
        assert required in text

    assert "`IMP.CHECKIN.MORNING` --> `IMP.REPLAN.VALIDATE`" in text
    assert "`IMP.MISSION.OUTCOME` --> `IMP.REPLAN.VALIDATE`" in text
    assert "`IMP.WR.INTERACTIVE` --> `IMP.WR.READ_ONLY`" in text


def test_design_system_instantiates_states_widgets_assets_and_tablet_layout_per_screen() -> None:
    text = _design_system_text()

    surface_route_ids = [
        route_id
        for route_id in IMPERIUM_ROUTE_IDS
        if route_id not in {"IMP.OPERATIONS.MAIN", "IMP.HISTORY.MAIN", "IMP.MISSION.ACTIVE"}
    ]
    for route_id in surface_route_ids:
        section = _screen_section(text, route_id)
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
    imperium_decisions = _subsection(text, "### 12.0 Imperium Product Decisions V1")

    assert "Mon OS personnel" in imperium_decisions
    assert "V3" in imperium_decisions
    assert "is explicitly excluded from V1 navigation" in imperium_decisions
    assert "Top-level V1" in imperium_decisions
    assert "`IMP.DASH.MAIN`, `IMP.OPERATIONS.MAIN`, `IMP.HISTORY.MAIN`, `IMP.SETTINGS.CORE`" in imperium_decisions
    assert "IMP.MISSION.DETAIL" in imperium_decisions
    assert "non une entrée top-level navigation" in imperium_decisions


def test_design_system_adds_imperium_product_decisions_and_endpoint_matrix() -> None:
    text = _design_system_text()
    endpoint_matrix = _subsection(text, "### 12.17 Imperium Endpoint Matrix V1")

    for required in (
        "One active mission",
        "Mon OS personnel V3",
        "Mission detail V1",
        "Backend ownership",
    ):
        assert required in text

    for required in (
        "IMP.DASH.MAIN",
        "`GET /api/imperium/dashboard`",
        "IMP.REPLAN.VALIDATE",
        "`POST /api/imperium/day/plan/{plan_id}/activate`",
        "IMP.WR.INTERACTIVE",
        "`GET /api/imperium/weekly-review/current`",
        "IMP.SETTINGS.CORE",
        "`GET /api/imperium/frontend/app-manifest`",
    ):
        assert required in endpoint_matrix


def test_imperium_endpoint_matrix_only_marks_real_backend_routes_as_real() -> None:
    text = _design_system_text()
    matrix = _subsection(text, "### 12.17 Imperium Endpoint Matrix V1")
    backend_routes = _imperium_backend_routes()
    documented_real_endpoints = _imperium_endpoint_matrix_real_endpoints(text)

    assert "/api/imperium/daily-plans" not in matrix
    assert "`GET /api/imperium/day/plan/today`" in matrix
    assert "`GET /api/imperium/day/plan`" in matrix
    assert "`POST /api/imperium/day/plan/{plan_id}/activate`" in matrix
    assert "TBD daily plan history read endpoint" in matrix

    missing_from_backend = documented_real_endpoints - backend_routes
    assert missing_from_backend == set()


def test_design_system_maps_all_12_vault_screens_with_stable_ids() -> None:
    text = _design_system_text()

    assert "## 13. VAULT SCREEN ARCHITECTURE MAPPING V1" in text
    assert "### 13.0 Vault Product Decisions V1" in text
    assert "### 13.13 Vault Navigation Graph V1" in text

    for screen_id in VAULT_SCREEN_IDS:
        assert "### 13." in text
        assert screen_id in text
        assert f"`{screen_id}`" in text

    for stable_id in (
        "VAU.DASH.MAIN",
        "VAU.TX.ADD_INCOME",
        "VAU.TX.ADD_EXPENSE",
        "VAU.TX.SCAN_CAPTURE",
        "VAU.TX.RECEIPT_REVIEW",
        "VAU.PRESSURE.EXPLAIN",
        "VAU.TX.LIST",
        "VAU.TX.EDIT",
        "VAU.CATEGORIES.LIST",
        "VAU.WALLET.UPDATE",
        "VAU.UPCOMING.MANAGE",
        "VAU.SETTINGS.CORE",
    ):
        assert stable_id in text


def test_design_system_instantiates_vault_screen_contracts_and_high_risk_decisions() -> None:
    text = _design_system_text()

    for screen_id in VAULT_SCREEN_IDS:
        section = _vault_screen_section(text, screen_id)
        for required_label in (
            "**Composants :**",
            "**Données affichées :**",
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

    for required in (
        "Camera Capture Surface",
        "Draft Transaction Card",
        "Pressure Gauge",
        "Money Display Hierarchy",
        "Money Input",
        "/api/imperium/vault/summary",
        "/api/imperium/vault/transactions/{transaction_id}/reverse",
        "TBD POST /api/vault/receipt-extractions",
        "VAU-04 --> VAU-05",
        "VAU-05 --> PULSE_HANDOFF",
        "VAU-12 --> PATH_SETTINGS",
        "Financial pressure UI renders doc 11 raw 0-100",
        "sadaqa percentage is owned by Path",
        "transaction removal uses reversal",
    ):
        assert required in text


def test_design_system_maps_all_11_vector_screens_with_stable_ids() -> None:
    text = _design_system_text()

    assert "## 14. VECTOR SCREEN ARCHITECTURE MAPPING V1" in text
    assert "### 14.0 Vector Product Decisions V1" in text
    assert "### 14.12 Vector Navigation Graph V1" in text
    assert "### 14.13 Vector Endpoint Matrix V1" in text
    assert "### 14.14 Vector Driving Mode Rules V1" in text

    for screen_id in VECTOR_SCREEN_IDS:
        assert "### 14." in text
        assert screen_id in text
        assert f"`{screen_id}`" in text

    for stable_id in (
        "VEC.DASH.MAIN",
        "VEC.SESSION.START",
        "VEC.SESSION.ACTIVE",
        "VEC.REVENUE.MANUAL",
        "VEC.EXPENSE.MANUAL",
        "VEC.SCREENSHOT.UPLOAD",
        "VEC.RECO.REQUEST",
        "VEC.RECO.DETAIL",
        "VEC.RECO.FEEDBACK",
        "VEC.DROP.CONFIRM",
        "VEC.SESSION.REVIEW",
    ):
        assert stable_id in text


def test_design_system_instantiates_vector_contracts_and_driving_decisions() -> None:
    text = _design_system_text()

    for screen_id in VECTOR_SCREEN_IDS:
        section = _vector_screen_section(text, screen_id)
        for required_label in (
            "**Composants :**",
            "**Données affichées :**",
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

    for required in (
        "VEC-06 Screenshot Upload is V1 upload-only",
        "Bolt OCR remains V2",
        "Recommendation cache TTL is 15 minutes",
        "stale after 30 minutes",
        "Driving mode activates when GPS speed is > 5 km/h",
        "Manual revenue and expense are Vector shortcuts to Vault transactions",
        "Last drop zone is user-triggered from VEC-03",
        "smart fuel is V2 in UI",
        "Rail/event/traffic banners are hosted by VEC-01 and VEC-03",
        "Vector Halo Emblem",
        "Driving Mode Indicator",
        "Cached Recommendation Card",
        "Confidence Breakdown Component",
        "Screenshot Upload Surface",
        "/api/vector/sessions/current",
        "TBD POST /api/vector/sessions",
        "TBD POST /api/vector/recommendations",
        "VEC-03 --> VEC-07",
        "VEC-11 --> IMPERIUM_REPLAN",
    ):
        assert required in text


def test_vector_halo_dictionary_matches_design_system_states() -> None:
    dictionary_text = (DOCS_ROOT / "01_SIGNAL_VARIABLES_DICTIONARY.md").read_text(encoding="utf-8")
    halo_line = next(line for line in dictionary_text.splitlines() if line.startswith("| recommendation_halo_state |"))

    for halo_state in ("white", "green", "yellow", "red"):
        assert halo_state in halo_line


def test_design_system_maps_all_14_pulse_screens_with_stable_ids() -> None:
    text = _design_system_text()

    assert "## 15. PULSE SCREEN ARCHITECTURE MAPPING V1" in text
    assert "### 15.0 Pulse Product Decisions V1" in text
    assert "### 15.15 Pulse Navigation Graph V1" in text
    assert "### 15.16 Pulse Endpoint Matrix V1" in text
    assert "### 15.17 Pulse-specific composed patterns" in text
    assert "### 15.18 Health Data Privacy Policy V1" in text

    for screen_id in PULSE_SCREEN_IDS:
        assert "### 15." in text
        assert screen_id in text
        assert f"`{screen_id}`" in text

    for stable_id in (
        "PUL.DASH.MAIN",
        "PUL.MEAL.ADD",
        "PUL.MEAL.CONFIRM",
        "PUL.HYDRATION.QUICK_LOG",
        "PUL.WORKOUT.PLAN",
        "PUL.WORKOUT.LOG",
        "PUL.WORKOUT.ADAPT",
        "PUL.BODY.SNAPSHOT",
        "PUL.PAIN.LOG",
        "PUL.MEALS.LIST",
        "PUL.WORKOUTS.LIST",
        "PUL.STOCK.LIST",
        "PUL.STOCK.SCAN",
        "PUL.MEDICAL.LIST",
    ):
        assert stable_id in text


def test_design_system_instantiates_pulse_contracts_and_health_guardrails() -> None:
    text = _design_system_text()

    for screen_id in PULSE_SCREEN_IDS:
        section = _pulse_screen_section(text, screen_id)
        for required_label in (
            "**Composants :**",
            "**Données affichées :**",
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

    for required in (
        "PUL-03 is independent from VAU-05",
        "Meal macros V1 source is backend AI estimation",
        "Stock decrement is user-confirmed and idempotent",
        "Body photo upload is disabled in V1",
        "Medical documents require explicit consent",
        "Health score must never render without explanation",
        "Hydration logs merge by idempotency key",
        "Pain severity 8-10 opens an Imperium replan prompt",
        "Macros Estimation Card",
        "Stock Item Row",
        "Hydration Progress Ring",
        "Workout Live Tracker",
        "Adaptation Proposal Card",
        "Pain Body Diagram",
        "Medical Document Row",
        "Active Medical Rule Banner",
        "TBD POST /api/pulse/meals/estimate",
        "TBD POST /api/pulse/meals/{meal_draft_id}/confirm",
        "TBD POST /api/pulse/hydration-logs",
        "TBD POST /api/pulse/workouts/{workout_id}/adaptation/accept",
        "TBD POST /api/pulse/medical-documents",
        "PUL-12 --> PUL-13",
        "PUL-14 --> IMPERIUM_REPLAN",
    ):
        assert required in text


def test_pulse_medical_and_logic_docs_define_required_v1_contracts() -> None:
    logic_text = (DOCS_ROOT / "40_PULSE_LOGIC_DETAIL.md").read_text(encoding="utf-8")
    medical_text = (DOCS_ROOT / "34_PULSE_MEDICAL_FEED_AI.md").read_text(encoding="utf-8")

    for required in (
        "Meal Tracking",
        "Food Stock",
        "Hydration",
        "Workouts",
        "Body Snapshot",
        "Pain Log",
        "Pulse UI Surface",
        "Idempotency-Key",
        "hydration sum merge",
        "stock_decrement_applied",
    ):
        _assert_doc_contains(logic_text, required)

    _assert_doc_contains_terms(logic_text, "meal", "macros")

    for required in (
        "GPT-5.5 static override",
        "explicit consent",
        "no diagnosis",
        "raw medical document retention",
        "pulse.medical_rule.activated",
        "RGPD article 9",
    ):
        _assert_doc_contains(medical_text, required)

    _assert_doc_contains_terms(medical_text, "user validation", "activation")


def test_design_system_maps_all_11_path_screens_with_stable_ids() -> None:
    text = _design_system_text()

    assert "## 16. PATH SCREEN ARCHITECTURE MAPPING V1" in text
    assert "### 16.0 Path Product Decisions V1" in text
    assert "### 16.12 Path Navigation Graph V1" in text
    assert "### 16.13 Path Endpoint Matrix V1" in text
    assert "### 16.14 Path-specific composed patterns" in text
    assert "### 16.15 Religious Data Privacy Policy V1" in text

    for screen_id in PATH_SCREEN_IDS:
        assert "### 16." in text
        assert screen_id in text
        assert f"`{screen_id}`" in text

    for stable_id in (
        "PAT.DASH.MAIN",
        "PAT.PRAYER.MARK",
        "PAT.SADAQA.DONATE",
        "PAT.GHUSL.REQUIRED",
        "PAT.FASTING.ACTION",
        "PAT.ADHKAR.COUNTER",
        "PAT.QURAN.PROGRESS",
        "PAT.MOSQUE.DETAIL",
        "PAT.MOSQUES.MANAGE",
        "PAT.GHUSL.ADDRESSES",
        "PAT.SETTINGS.CORE",
    ):
        assert stable_id in text


def test_path_top_level_navigation_is_consistent_with_mermaid_graph() -> None:
    text = _design_system_text()
    path_decisions = _subsection(text, "### 16.0 Path Product Decisions V1")
    path_graph = _subsection(text, "### 16.12 Path Navigation Graph V1")

    assert "Surfaces principales Path V1" in path_decisions
    assert "Vraies entrées top-level navigation Path V1" in path_decisions
    assert "alignées avec le graph Mermaid" in path_decisions
    assert "Top-level Path V1 : Dashboard (`PAT-01`), Prayers" not in text

    nav_targets = set(re.findall(r"NAV(?:\[[^\]]+\])? --> (PAT\d+)", path_graph))
    assert nav_targets == {"PAT01", "PAT09", "PAT10", "PAT11"}

    for contextual_surface in ("PAT02", "PAT03", "PAT04", "PAT05", "PAT06", "PAT07", "PAT08"):
        assert f"NAV --> {contextual_surface}" not in path_graph


def test_design_system_instantiates_path_contracts_and_religious_guardrails() -> None:
    text = _design_system_text()

    for screen_id in PATH_SCREEN_IDS:
        section = _path_screen_section(text, screen_id)
        for required_label in (
            "**Composants :**",
            "**Données affichées :**",
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

    for required in (
        "V1 tracks the five obligatory prayers only",
        "Mosque reality first",
        "cache 30 days",
        "default `MuslimWorldLeague`",
        "default Asr rule `Shafi`",
        "PAT-05 user confirmation is mandatory",
        "sadaqa percentage is Path-owned",
        "Partial donations roll remaining carry forward",
        "Vault personal expense handoff category `Sadaqa`",
        "Religious data privacy policy cites RGPD article 9",
        "Prayer uses explicit conflict review",
        "adhkar increments merge sum by idempotency key",
        "PAT-06b, PAT-07b, PAT-09b, PAT-10b, PAT-11b/c/d/e/f",
        "Next Prayer Countdown Card",
        "Prayer Mark Action Card",
        "Sadaqa Target Card",
        "Ghusl Required Toggle Card",
        "Fasting Start/End Card",
        "Adhkar Counter Widget",
        "Quran Progress Card",
        "Mosque MAWAQIT Detail",
        "Registered Mosque Row",
        "Qibla Direction Compass",
        "Sadaqa% Stepper",
        "TBD POST /api/path/prayers/{prayer_slug}/mark",
        "TBD POST /api/path/sadaqa/donations",
        "TBD POST /api/path/ghusl/activate",
        "TBD POST /api/path/fasting/start",
        "TBD POST /api/path/adhkar/routines/{routine_id}/increment",
        "TBD POST /api/path/quran/progress",
        "TBD GET /api/path/mawaqit/search",
        "VAU-12 --> PAT-11d",
        "PAT-04 --> IMPERIUM_REPLAN",
        "PAT-05 --> PULSE_FASTING",
    ):
        assert required in text


def test_path_logic_doc_defines_required_v1_contracts_and_privacy_rules() -> None:
    logic_text = (DOCS_ROOT / "41_PATH_LOGIC_DETAIL.md").read_text(encoding="utf-8")

    for required in (
        "Prayer Times, MAWAQIT, And Calculation Engine",
        "Prayer Marking Logic",
        "Fasting Logic",
        "Sadaqa Logic",
        "Ghusl",
        "Adhkar Routines",
        "Quran Progress",
        "Religious Data Privacy Policy",
        "UI Surface",
        "Fajr, Dhuhr, Asr, Maghrib, Isha",
        "All mutation endpoints require `Idempotency-Key`",
        "MuslimWorldLeague",
        "Shafi",
        "Partial donation leaves remaining carry",
        "Vault personal expense handoff with category `Sadaqa`",
        "Ghusl requirement is never inferred",
        "A fast starts only when the user confirms PAT-05",
        "Distinct increment keys use merge sum",
        "A lower page than the last validated point requires confirmation",
        "privacy gate",
        "PAT-06b Adhkar Routine Configuration",
        "PAT-11f City / Location Selector",
    ):
        _assert_doc_contains(logic_text, required)

    _assert_doc_contains_terms(
        logic_text,
        "sadaqa_weekly_target",
        "max(",
        "business_profit",
        "sadaqa_percentage",
    )
