from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.router import api_router


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = BACKEND_ROOT.parent / "docs_master"


class FakeDb:
    def __init__(self) -> None:
        self.added = []
        self.flushed = False
        self.committed = False

    def add(self, obj) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed = True

    def commit(self) -> None:
        self.committed = True


def _client(db: FakeDb, current_user: SimpleNamespace) -> TestClient:
    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4())


def test_frontend_asset_registry_endpoint_present_and_jwt_scoped() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/asset-registry")
    assert response.status_code == 200


def test_frontend_asset_registry_get_only_no_idempotency_key_required() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/asset-registry")
    assert response.status_code == 200


def test_frontend_asset_registry_response_shape_and_deterministic_registry() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/asset-registry")
    assert response.status_code == 200
    body = response.json()

    assert set(body) == {
        "asset_registry_version",
        "read_only",
        "asset_base_path",
        "placeholder_policy",
        "groups",
        "safe_explanation",
    }
    assert body["asset_registry_version"] == "v1"
    assert body["read_only"] is True
    assert body["asset_base_path"] == "/assets/imperium"
    assert body["placeholder_policy"] == {
        "placeholder_allowed": True,
        "placeholder_style": "semantic_luxury_placeholder",
        "safe_explanation": "Final PNG/SVG assets may be provided later; placeholders are allowed during UI assembly.",
    }
    assert body["safe_explanation"] == "Frontend asset registry metadata for Imperium V1."

    assert [group["key"] for group in body["groups"]] == [
        "core",
        "navigation",
        "dashboard",
        "modules",
        "vault",
        "path",
        "pulse",
        "vector",
        "weekly_review",
        "states",
        "backgrounds",
        "overlays",
    ]

    expected_group_base_paths = {
        "core": "/assets/imperium/core",
        "navigation": "/assets/imperium/navigation",
        "dashboard": "/assets/imperium/dashboard",
        "modules": "/assets/imperium/modules",
        "vault": "/assets/imperium/vault",
        "path": "/assets/imperium/path",
        "pulse": "/assets/imperium/pulse",
        "vector": "/assets/imperium/vector",
        "weekly_review": "/assets/imperium/weekly-review",
        "states": "/assets/imperium/states",
        "backgrounds": "/assets/imperium/backgrounds",
        "overlays": "/assets/imperium/overlays",
    }
    expected_group_item_keys = {
        "core": [
            "imperium_emblem",
            "imperium_wordmark",
            "imperium_symbol_mini",
            "premium_divider",
            "gold_frame",
            "corner_ornament",
        ],
        "navigation": [
            "nav_home",
            "nav_dashboard",
            "nav_daily_plan",
            "nav_missions",
            "nav_vault",
            "nav_path",
            "nav_pulse",
            "nav_vector",
            "nav_settings",
        ],
        "dashboard": [
            "dashboard_hero_frame",
            "dashboard_focus_card",
            "dashboard_kpi_card",
            "dashboard_readiness_ring",
        ],
        "modules": [
            "module_card_frame",
            "module_card_active_glow",
            "module_card_empty_state",
            "module_card_locked_state",
        ],
        "vault": [
            "vault_emblem",
            "vault_income",
            "vault_expense",
            "vault_ledger",
            "vault_pressure",
            "vault_receipt_scan",
        ],
        "path": [
            "path_arch_emblem",
            "path_wordmark",
            "path_habit",
            "path_check",
            "path_reflection",
            "path_spiritual_divider",
        ],
        "pulse": [
            "pulse_emblem",
            "pulse_sleep",
            "pulse_energy",
            "pulse_fatigue",
            "pulse_workout",
            "pulse_weight",
        ],
        "vector": [
            "vector_emblem",
            "vector_car",
            "vector_zone",
            "vector_demand",
            "vector_traffic",
            "vector_train",
            "vector_event",
        ],
        "weekly_review": [
            "wr_emblem",
            "wr_report",
            "wr_timeline",
            "wr_summary",
            "wr_reflection",
        ],
        "states": [
            "state_loading",
            "state_empty",
            "state_locked",
            "state_error",
        ],
        "backgrounds": [
            "background_dashboard_gradient",
            "background_daily_plan_gradient",
            "background_vault_texture",
            "background_path_light",
            "background_pulse_light",
        ],
        "overlays": [
            "overlay_gold_noise",
            "overlay_corner_vignette",
            "overlay_glass_blur",
            "overlay_focus_rim",
        ],
    }
    expected_asset_types = {
        "core": "svg",
        "navigation": "svg",
        "dashboard": "svg",
        "modules": "svg",
        "vault": "svg",
        "path": "svg",
        "pulse": "svg",
        "vector": "svg",
        "weekly_review": "svg",
        "states": "svg",
        "backgrounds": "png",
        "overlays": "png",
    }

    assert [group["label"] for group in body["groups"]] == [
        "Core Brand Assets",
        "Navigation Icons",
        "Dashboard Assets",
        "Module Card Assets",
        "Vault Assets",
        "Path Assets",
        "Pulse Assets",
        "Vector Assets",
        "Weekly Review Assets",
        "State Assets",
        "Background Assets",
        "Overlay Assets",
    ]

    for group in body["groups"]:
        assert group["base_path"] == expected_group_base_paths[group["key"]]
        assert [item["key"] for item in group["items"]] == expected_group_item_keys[group["key"]]
        assert all(item["status"] == "expected" for item in group["items"])
        assert all(item["placeholder_allowed"] is True for item in group["items"])
        assert all(item["asset_type"] == expected_asset_types[group["key"]] for item in group["items"])
        assert all(
            item["expected_filename"] == f'{item["key"]}.{expected_asset_types[group["key"]]}'
            for item in group["items"]
        )
        assert all(set(item) == {"key", "label", "asset_type", "expected_filename", "usage", "status", "placeholder_allowed"} for item in group["items"])

    payload_text = str(body).lower()
    for forbidden in (
        "user_id",
        "secret",
        "provider",
        "infra",
        "database",
        "postgres",
        "pgvector",
        "n8n",
        "openai",
        "anthropic",
        "gemini",
        "claude",
        "health",
        "runtime audit",
        "dynamic discovery",
        "filesystem",
        "ocr",
        "scoring",
        "coaching",
        "recommendation",
    ):
        assert forbidden not in payload_text


def test_frontend_asset_registry_read_only_no_db_write() -> None:
    db = FakeDb()
    response = _client(db, _user()).get("/api/imperium/frontend/asset-registry")
    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_frontend_asset_registry_docs_metadata_only_static_v1_placeholder_policy_and_no_filesystem_checks() -> None:
    contracts_docs = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8").lower()
    schema_docs = (DOCS_ROOT / "05_DATABASE_SCHEMA.md").read_text(encoding="utf-8").lower()

    for text in (contracts_docs, schema_docs):
        assert "/api/imperium/frontend/asset-registry" in text
        assert "asset registry metadata" in text
        assert "metadata only" in text
        assert "static deterministic v1" in text
        assert "placeholder policy" in text
        assert "placeholder_allowed" in text
        assert "semantic_luxury_placeholder" in text
        assert "no filesystem check" in text
        assert "not a health check" in text
        assert "not dynamic discovery" in text
        assert "no business data read" in text
        assert "no secrets/providers/infra metadata" in text
