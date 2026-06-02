from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = BACKEND_ROOT / "docs_master"
DESIGN_SYSTEM_PATH = DOCS_ROOT / "59_DESIGN_SYSTEM_V1_DRAFT.md"

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


def _vault_screen_section(text: str, screen_id: str) -> str:
    marker = next(line for line in text.splitlines() if line.startswith("### 13.") and f"`{screen_id}`" in line)
    return text.split(marker, maxsplit=1)[1].split("\n### 13.", maxsplit=1)[0]


def _vector_screen_section(text: str, screen_id: str) -> str:
    marker = next(line for line in text.splitlines() if line.startswith("### 14.") and f"`{screen_id}`" in line)
    return text.split(marker, maxsplit=1)[1].split("\n### 14.", maxsplit=1)[0]


def _pulse_screen_section(text: str, screen_id: str) -> str:
    marker = next(line for line in text.splitlines() if line.startswith("### 15.") and f"`{screen_id}`" in line)
    return text.split(marker, maxsplit=1)[1].split("\n### 15.", maxsplit=1)[0]


def _path_screen_section(text: str, screen_id: str) -> str:
    marker = next(line for line in text.splitlines() if line.startswith("### 16.") and f"`{screen_id}`" in line)
    return text.split(marker, maxsplit=1)[1].split("\n### 16.", maxsplit=1)[0]


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
