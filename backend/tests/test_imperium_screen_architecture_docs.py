from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = BACKEND_ROOT / "docs_master"
DESIGN_SYSTEM_PATH = DOCS_ROOT / "59_DESIGN_SYSTEM_V1_DRAFT.md"

IMPERIUM_SCREEN_IDS = [f"IMP-{number:02d}" for number in range(1, 15)]
VAULT_SCREEN_IDS = [f"VAU-{number:02d}" for number in range(1, 13)]
VECTOR_SCREEN_IDS = [f"VEC-{number:02d}" for number in range(1, 12)]
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


def _design_system_text() -> str:
    return DESIGN_SYSTEM_PATH.read_text(encoding="utf-8")


def _vault_screen_section(text: str, screen_id: str) -> str:
    marker = next(line for line in text.splitlines() if line.startswith("### 13.") and f"`{screen_id}`" in line)
    return text.split(marker, maxsplit=1)[1].split("\n### 13.", maxsplit=1)[0]


def _vector_screen_section(text: str, screen_id: str) -> str:
    marker = next(line for line in text.splitlines() if line.startswith("### 14.") and f"`{screen_id}`" in line)
    return text.split(marker, maxsplit=1)[1].split("\n### 14.", maxsplit=1)[0]


def test_imperium_screen_source_docs_are_available_in_audited_docs_master() -> None:
    missing = [doc_name for doc_name in SOURCE_DOCS if not (DOCS_ROOT / doc_name).exists()]

    assert missing == []


def test_vault_screen_source_docs_are_available_in_audited_docs_master() -> None:
    missing = [doc_name for doc_name in VAULT_SOURCE_DOCS if not (DOCS_ROOT / doc_name).exists()]

    assert missing == []


def test_vector_screen_source_docs_are_available_in_audited_docs_master() -> None:
    missing = [doc_name for doc_name in VECTOR_SOURCE_DOCS if not (DOCS_ROOT / doc_name).exists()]

    assert missing == []


def test_design_system_maps_all_14_imperium_screens_with_stable_ids() -> None:
    text = _design_system_text()

    for screen_id in IMPERIUM_SCREEN_IDS:
        assert "### 8." in text
        assert screen_id in text
        assert f"`{screen_id}`" in text

    assert "IMP-10 Weekly Review List" in text
    assert "IMP-11 Weekly Review Read-only View" in text
    assert "IMP-12 Weekly Review Interactive Popup" in text


def test_design_system_declares_screen_types_navigation_and_backend_dependencies() -> None:
    text = _design_system_text()

    for required in (
        "## 8. IMPERIUM SCREEN ARCHITECTURE MAPPING V1",
        "### 8.0 Canonical Routing Typology",
        "### 8.15 Imperium Navigation Graph V1",
        "route",
        "tab",
        "dialog",
        "bottom_sheet",
        "deep_link",
        "/api/imperium/dashboard",
        "/api/imperium/day/finish",
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
        section = text.split(f"`{screen_id}`", maxsplit=1)[1].split("\n### 8.", maxsplit=1)[0]
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

    assert "Mon OS personnel" in text
    assert "V3" in text
    assert "excluded from V1 navigation" in text
    assert "Mission detail is not IMP-15 in V1" in text
    assert "IMP.MISSION.DETAIL" in text


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
