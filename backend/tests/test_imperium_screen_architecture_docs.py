import re
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = BACKEND_ROOT / "docs_master"
DESIGN_SYSTEM_PATH = DOCS_ROOT / "59_DESIGN_SYSTEM_V1_DRAFT.md"
DESIGN_SYSTEM_TOKENS_KT_PATH = DOCS_ROOT / "60_DESIGN_SYSTEM_TOKENS_KT.md"
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

IMPERIUM_SCREEN_IDS = [f"IMP-{number:02d}" for number in range(1, 15)]
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


def test_design_system_maps_all_14_imperium_screens_with_stable_ids() -> None:
    text = _design_system_text()

    assert "## 12. IMPERIUM SCREEN ARCHITECTURE MAPPING V1" in text
    assert "### 12.0 Imperium Product Decisions V1" in text
    assert "### 12.16 Imperium Navigation Graph V1" in text
    assert "### 12.17 Imperium Endpoint Matrix V1" in text

    for screen_id in IMPERIUM_SCREEN_IDS:
        assert "### 12." in text
        assert screen_id in text
        assert f"`{screen_id}`" in text

    assert "IMP-10 Weekly Review List" in text
    assert "IMP-11 Weekly Review Read-only View" in text
    assert "IMP-12 Weekly Review Interactive Popup" in text


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

    assert "IMP-02 --> IMP-05" in text
    assert "IMP-03 --> IMP-05" in text
    assert "IMP-12 --> IMP-11" in text


def test_design_system_instantiates_states_widgets_assets_and_tablet_layout_per_screen() -> None:
    text = _design_system_text()

    for screen_id in IMPERIUM_SCREEN_IDS:
        section = _screen_section(text, screen_id)
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
    assert "Mission detail is not IMP-15 in V1" in imperium_decisions
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
        "IMP-01",
        "`GET /api/imperium/dashboard`",
        "IMP-05",
        "`POST /api/imperium/day/plan/{plan_id}/activate`",
        "IMP-12",
        "`GET /api/imperium/weekly-review/current`",
        "IMP-14",
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
        "## 6. Meals And Macros",
        "## 7. Food Stock",
        "## 8. Hydration",
        "## 9. Workouts",
        "## 10. Body Snapshot",
        "## 14. Pain Log",
        "## 15. Pulse UI Surface",
        "Idempotency-Key",
        "hydration sum merge",
        "stock_decrement_applied",
    ):
        assert required in logic_text

    for required in (
        "GPT-5.5 static override",
        "explicit consent",
        "no diagnosis",
        "raw medical document retention",
        "user validation before activation",
        "pulse.medical_rule.activated",
        "RGPD article 9",
    ):
        assert required in medical_text


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
        "## 4. Prayer Times, MAWAQIT, And Calculation Engine",
        "## 5. Prayer Marking Logic",
        "## 6. Fasting Logic",
        "## 7. Sadaqa Logic",
        "## 8. Ghusl Logic",
        "## 9. Adhkar Routines",
        "## 10. Quran Progress",
        "## 13. Religious Data Privacy Policy",
        "## 15. UI Surface",
        "Fajr, Dhuhr, Asr, Maghrib, Isha",
        "All mutation endpoints require `Idempotency-Key`",
        "MuslimWorldLeague",
        "Shafi",
        "sadaqa_weekly_target = max(vault_weekly_business_profit, 0) * sadaqa_percentage",
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
        assert required in logic_text
